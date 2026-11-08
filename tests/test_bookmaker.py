import shutil
from pathlib import Path

from bookmaker.models import (
    BookDraft,
    ImageReview,
    ImageReviewReport,
    Palette,
    Scene,
    StoryPage,
    Translation,
    TranslationSet,
    VisualPlan,
)
from bookmaker.pipeline import Pipeline, validate_story
from bookmaker.repository import parse_book, render_book, visible_words, words


def sample_draft() -> BookDraft:
    return BookDraft(
        title="Nicholas Finds Mars",
        subtitle="A red rock tale",
        pages=[StoryPage(text=f"Nicholas sees Mars. He sees rock {number}.") for number in range(6)],
    )


def sample_visual() -> VisualPlan:
    palette = Palette(
        body_background="#ddeeff",
        ink="#223344",
        paper="#fffdf4",
        heading="#cc5544",
        accent="#228877",
        subtitle="#cc7744",
        active_dot="#cc5544",
        focus="#ffdd66",
        copy_backgrounds=["#fffdf4"] * 7,
    )
    return VisualPlan(
        visual_bible="Nicholas is a small boy on Mars.",
        palette=palette,
        scenes=[Scene(page_number=n, filename=f"{n:02d}-mars.png", scene="A Mars scene.") for n in range(1, 8)],
    )


def test_words_keep_contractions() -> None:
    assert words("I'm at Nicholas's house.") == ["I'm", "at", "Nicholas's", "house"]


def test_visible_words_exclude_subtitle() -> None:
    draft = sample_draft()
    assert "red" not in visible_words(draft)


def test_render_round_trip_excludes_subtitle(tmp_path: Path) -> None:
    draft = sample_draft()
    translations = TranslationSet(
        translations=[Translation(word=word, chinese="字") for word in dict.fromkeys(words(draft.title + " " + draft.subtitle + " " + " ".join(page.text for page in draft.pages)))]
    )
    output = tmp_path / "mars.html"
    output.write_text(render_book(slug="mars", draft=draft, visual=sample_visual(), translations=translations))
    title, stories = parse_book(output)
    assert title == draft.title
    assert stories == [page.text for page in draft.pages]


def test_validate_story_counts_quoted_sentences() -> None:
    draft = BookDraft(
        title="Nicholas Has A Fine Time",
        subtitle="A nice time tale",
        pages=[
            StoryPage(text="Nicholas can run in the sun. “I can run with Mia!”")
            for _ in range(6)
        ],
    )
    errors = [item for item in validate_story(draft, set()) if item.startswith("ERROR:")]
    assert not errors


def test_build_renders_book_and_updates_index_without_api_key(tmp_path: Path) -> None:
    shutil.copy(Path("bookmaker.toml"), tmp_path / "bookmaker.toml")
    (tmp_path / "index.html").write_text(
        '<!doctype html><ol class="book-list">\n</ol>'
    )
    pipeline = Pipeline(tmp_path)
    slug = "mars"
    source = pipeline.source_dir(slug)
    art = pipeline.art_dir(slug)
    source.mkdir(parents=True)
    art.mkdir(parents=True)
    draft = sample_draft()
    visual = sample_visual()
    translations = TranslationSet(
        translations=[
            Translation(word=word, chinese="字")
            for word in dict.fromkeys(
                words(
                    draft.title
                    + " "
                    + draft.subtitle
                    + " "
                    + " ".join(page.text for page in draft.pages)
                )
            )
        ]
    )
    review = ImageReviewReport(
        pages=[
            ImageReview(page_number=number, passed=True, issues=[], regeneration_instruction="")
            for number in range(1, 8)
        ]
    )
    (source / "story.json").write_text(draft.model_dump_json())
    (source / "visual.json").write_text(visual.model_dump_json())
    (source / "translations.json").write_text(translations.model_dump_json())
    (source / "image-review.json").write_text(review.model_dump_json())
    for scene in visual.scenes:
        (art / scene.filename).write_bytes(b"fake png")

    output = pipeline.build(slug=slug)

    assert output.exists()
    assert 'href="mars.html"' in (tmp_path / "index.html").read_text()
    assert f"{len(visible_words(draft))} English words" in (tmp_path / "index.html").read_text()
