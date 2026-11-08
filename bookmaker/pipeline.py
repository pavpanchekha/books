from __future__ import annotations

import json
import os
import re
import tomllib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from .models import (
    ArtDirectionReview,
    BookDraft,
    EditorialReview,
    ImageReviewReport,
    Translation,
    TranslationSet,
    VisualPlan,
)
from .prompts import (
    ART_REVIEW_SYSTEM,
    ART_SYSTEM,
    EDITOR_SYSTEM,
    IMAGE_REVIEW_SYSTEM,
    STYLE_PROMPT,
    TRANSLATOR_SYSTEM,
    WRITER_RULES,
    WRITER_SYSTEM,
)
from .providers import ModelProvider, make_provider
from .repository import (
    older_corpus_words,
    render_book,
    unique_casefolded,
    update_index,
    visible_words,
    words,
)

T = TypeVar("T", bound=BaseModel)


def slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not value:
        raise ValueError("slug must contain a letter or number")
    return value


class Pipeline:
    def __init__(self, root: Path, provider: ModelProvider | None = None) -> None:
        self.root = root.resolve()
        with (self.root / "bookmaker.toml").open("rb") as config_file:
            self.config: dict[str, Any] = tomllib.load(config_file)
        self._provider = provider

    @property
    def provider(self) -> ModelProvider:
        if self._provider is None:
            provider_name = self.config["models"]["provider"]
            self._provider = make_provider(provider_name)
        return self._provider

    def source_dir(self, slug: str) -> Path:
        return self.root / self.config["paths"]["source"] / slug

    def art_dir(self, slug: str) -> Path:
        return self.root / self.config["paths"]["art"] / slug

    def _path(self, slug: str, name: str) -> Path:
        return self.source_dir(slug) / name

    def _save(self, slug: str, name: str, value: BaseModel) -> None:
        path = self._path(slug, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value.model_dump_json(indent=2) + "\n")

    def _load(self, slug: str, name: str, schema: type[T]) -> T:
        path = self._path(slug, name)
        if not path.exists():
            raise RuntimeError(f"Missing {path}; run the preceding stage first")
        return schema.model_validate_json(path.read_text())

    def _model(self, role: str) -> str:
        return str(self.config["models"][role])

    def write(self, *, slug: str, idea: str, force: bool = False) -> BookDraft:
        destination = self._path(slug, "story.json")
        if destination.exists() and not force:
            return self._load(slug, "story.json", BookDraft)
        older = unique_casefolded(older_corpus_words(self.root, f"{slug}.html"))
        initial = self.provider.structured(
            model=self._model("writer"),
            schema=BookDraft,
            system=WRITER_SYSTEM,
            user=f"{WRITER_RULES}\n\nBook premise:\n{idea}\n\nOlder-book vocabulary (case-insensitive):\n{', '.join(older)}",
        )
        review = self.provider.structured(
            model=self._model("editor"),
            schema=EditorialReview,
            system=EDITOR_SYSTEM,
            user=(
                f"{WRITER_RULES}\n\nPremise:\n{idea}\n\nOlder vocabulary:\n{', '.join(older)}"
                f"\n\nDraft to review:\n{initial.model_dump_json(indent=2)}"
            ),
        )
        problems = validate_story(review.revised, set(word.lower() for word in older))
        errors = [problem for problem in problems if problem.startswith("ERROR:")]
        if errors:
            raise RuntimeError("Edited story still violates hard constraints:\n" + "\n".join(errors))
        if force:
            self._invalidate_after_story(slug)
        self._save(slug, "story.json", review.revised)
        self._path(slug, "editor-notes.json").write_text(json.dumps(review.notes, indent=2) + "\n")
        self._path(slug, "story-validation.json").write_text(json.dumps(problems, indent=2) + "\n")
        return review.revised

    def visuals(self, *, slug: str, force: bool = False) -> VisualPlan:
        destination = self._path(slug, "visual.json")
        if destination.exists() and not force:
            return self._load(slug, "visual.json", VisualPlan)
        draft = self._load(slug, "story.json", BookDraft)
        story = story_for_prompt(draft)
        initial = self.provider.structured(
            model=self._model("art_director"),
            schema=VisualPlan,
            system=ART_SYSTEM,
            user=(
                f"Create the fixed bible and scene plan from this source-of-truth book. "
                f"The cover scene may use only the title. Each later scene may use only the story prefix through its own exact page.\n\n{story}"
            ),
        )
        review = self.provider.structured(
            model=self._model("art_reviewer"),
            schema=ArtDirectionReview,
            system=ART_REVIEW_SYSTEM,
            user=f"Source-of-truth book:\n{story}\n\nPlan to review:\n{initial.model_dump_json(indent=2)}",
        )
        if force:
            self._invalidate_after_visuals(slug)
        self._save(slug, "visual.json", review.revised)
        self._path(slug, "art-review-notes.json").write_text(json.dumps(review.notes, indent=2) + "\n")
        self._write_prompts(slug, draft, review.revised)
        return review.revised

    def _unlink(self, path: Path) -> None:
        if path.exists() and path.is_file():
            path.unlink()

    def _invalidate_after_story(self, slug: str) -> None:
        old_visual_path = self._path(slug, "visual.json")
        if old_visual_path.exists():
            old_visual = VisualPlan.model_validate_json(old_visual_path.read_text())
            for scene in old_visual.scenes:
                self._unlink(self.art_dir(slug) / scene.filename)
        for name in [
            "visual.json",
            "story-validation.json",
            "art-review-notes.json",
            "prompts.md",
            "image-review.json",
            "translations.json",
        ]:
            self._unlink(self._path(slug, name))
        self._unlink(self.art_dir(slug) / "prompts.md")

    def _invalidate_after_visuals(self, slug: str) -> None:
        old_visual_path = self._path(slug, "visual.json")
        if old_visual_path.exists():
            old_visual = VisualPlan.model_validate_json(old_visual_path.read_text())
            for scene in old_visual.scenes:
                self._unlink(self.art_dir(slug) / scene.filename)
        self._unlink(self._path(slug, "image-review.json"))
        self._unlink(self._path(slug, "translations.json"))

    def _write_prompts(self, slug: str, draft: BookDraft, visual: VisualPlan) -> None:
        sections = [
            f"# {draft.title} image prompts",
            "## Fixed visual bible",
            visual.visual_bible,
            "## Fixed style prompt",
            STYLE_PROMPT,
        ]
        prefix: list[str] = []
        page_texts = [draft.title, *(page.text for page in draft.pages)]
        for scene, text in zip(visual.scenes, page_texts, strict=True):
            prefix.append(text)
            label = "Cover" if scene.page_number == 1 else f"Page {scene.page_number}"
            sections.extend(
                [
                    f"## {label}",
                    f"Story prefix and current page only: `{ ' '.join(prefix) }`",
                    f"Scene: {scene.scene}",
                ]
            )
        output = "\n\n".join(sections) + "\n"
        path = self._path(slug, "prompts.md")
        path.write_text(output)
        art_prompt = self.art_dir(slug) / "prompts.md"
        art_prompt.parent.mkdir(parents=True, exist_ok=True)
        art_prompt.write_text(output)

    def image_prompt(
        self,
        draft: BookDraft,
        visual: VisualPlan,
        page_number: int,
        correction: str = "",
    ) -> str:
        scene = visual.scenes[page_number - 1]
        texts = [draft.title, *(page.text for page in draft.pages)]
        prefix = " ".join(texts[:page_number])
        prompt = (
            f"{STYLE_PROMPT}\n\nFixed visual bible:\n{visual.visual_bible}\n\n"
            f"Story prefix through the current page only:\n{prefix}\n\n"
            f"Current page exact text:\n{texts[page_number - 1]}\n\nScene:\n{scene.scene}"
        )
        if correction:
            prompt += f"\n\nRegeneration correction from QA:\n{correction}"
        return prompt

    def images(
        self,
        *,
        slug: str,
        force: bool = False,
        page_numbers: list[int] | None = None,
        corrections: dict[int, str] | None = None,
    ) -> None:
        draft = self._load(slug, "story.json", BookDraft)
        visual = self._load(slug, "visual.json", VisualPlan)
        output_dir = self.art_dir(slug)
        output_dir.mkdir(parents=True, exist_ok=True)
        wanted = page_numbers or list(range(1, 8))
        corrections = corrections or {}

        def generate(page_number: int) -> tuple[int, Path, bytes] | None:
            scene = visual.scenes[page_number - 1]
            path = output_dir / scene.filename
            if path.exists() and not force and page_number not in corrections:
                return None
            data = self.provider.image(
                model=self._model("image"),
                prompt=self.image_prompt(draft, visual, page_number, corrections.get(page_number, "")),
                size=str(self.config["images"]["size"]),
                quality=str(self.config["images"]["quality"]),
                output_format=str(self.config["images"]["format"]),
            )
            return page_number, path, data

        parallelism = int(self.config["images"]["parallelism"])
        with ThreadPoolExecutor(max_workers=parallelism) as executor:
            futures = {executor.submit(generate, number): number for number in wanted}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    _, path, data = result
                    path.write_bytes(data)

    def review(self, *, slug: str) -> ImageReviewReport:
        draft = self._load(slug, "story.json", BookDraft)
        visual = self._load(slug, "visual.json", VisualPlan)
        image_paths = [self.art_dir(slug) / scene.filename for scene in visual.scenes]
        missing = [str(path) for path in image_paths if not path.exists()]
        if missing:
            raise RuntimeError("Missing images:\n" + "\n".join(missing))
        numbered_plan = "\n".join(
            f"Page {scene.page_number}: exact text={([draft.title, *(p.text for p in draft.pages)])[scene.page_number - 1]!r}; expected scene={scene.scene}"
            for scene in visual.scenes
        )
        report = self.provider.structured(
            model=self._model("image_reviewer"),
            schema=ImageReviewReport,
            system=IMAGE_REVIEW_SYSTEM,
            user=f"Fixed visual bible:\n{visual.visual_bible}\n\nThe attached images are pages 1-7 in order.\n{numbered_plan}",
            images=image_paths,
        )
        self._save(slug, "image-review.json", report)
        return report

    def review_and_repair(self, *, slug: str) -> ImageReviewReport:
        rounds = int(self.config["images"]["max_review_rounds"])
        report = self.review(slug=slug)
        for _ in range(rounds):
            failed = [page for page in report.pages if not page.passed]
            if not failed:
                return report
            corrections = {page.page_number: page.regeneration_instruction for page in failed}
            self.images(
                slug=slug,
                force=True,
                page_numbers=sorted(corrections),
                corrections=corrections,
            )
            report = self.review(slug=slug)
        return report

    def translate(self, *, slug: str, force: bool = False) -> TranslationSet:
        destination = self._path(slug, "translations.json")
        if destination.exists() and not force:
            return self._load(slug, "translations.json", TranslationSet)
        draft = self._load(slug, "story.json", BookDraft)
        tokens = unique_casefolded(
            words(" ".join([draft.title, draft.subtitle, *(page.text for page in draft.pages)]))
        )
        result = self.provider.structured(
            model=self._model("translator"),
            schema=TranslationSet,
            system=TRANSLATOR_SYSTEM,
            user=f"Book context:\n{story_for_prompt(draft)}\n\nWords, in required order:\n" + "\n".join(tokens),
        )
        expected = [token.lower() for token in tokens]
        actual = [item.word.lower() for item in result.translations]
        if actual != expected:
            raise RuntimeError("Translator did not return the exact requested word list in order")
        self._save(slug, "translations.json", result)
        return result

    def build(self, *, slug: str, allow_review_failures: bool = False) -> Path:
        draft = self._load(slug, "story.json", BookDraft)
        visual = self._load(slug, "visual.json", VisualPlan)
        translations = self._load(slug, "translations.json", TranslationSet)
        report = self._load(slug, "image-review.json", ImageReviewReport)
        failures = [page.page_number for page in report.pages if not page.passed]
        if failures and not allow_review_failures:
            raise RuntimeError(f"Image review still fails pages {failures}; refusing to publish")
        for scene in visual.scenes:
            if not (self.art_dir(slug) / scene.filename).exists():
                raise RuntimeError(f"Missing image {scene.filename}")
        destination = self.root / f"{slug}.html"
        destination.write_text(render_book(slug=slug, draft=draft, visual=visual, translations=translations))
        update_index(self.root, destination.name)
        return destination

    def run(self, *, slug: str, idea: str, force: bool = False) -> Path:
        self.write(slug=slug, idea=idea, force=force)
        self.visuals(slug=slug, force=force)
        self.images(slug=slug, force=force)
        report = self.review_and_repair(slug=slug)
        failures = [page.page_number for page in report.pages if not page.passed]
        if failures:
            raise RuntimeError(f"Image QA still fails pages {failures} after repair rounds")
        self.translate(slug=slug, force=force)
        return self.build(slug=slug)


def story_for_prompt(draft: BookDraft) -> str:
    lines = [f"Title: {draft.title}", f"Subtitle: {draft.subtitle}"]
    lines.extend(f"Page {number}: {page.text}" for number, page in enumerate(draft.pages, start=2))
    return "\n".join(lines)


def validate_story(draft: BookDraft, older_words: set[str]) -> list[str]:
    problems: list[str] = []
    tokens = visible_words(draft)
    if not 70 <= len(tokens) <= 80:
        problems.append(f"ERROR: visible reading text has {len(tokens)} words; expected 70-80")
    for number, page in enumerate(draft.pages, start=2):
        sentence_count = len(re.findall(r"[.!?](?:[”’\"])?(?=\s|$)", page.text))
        if not 2 <= sentence_count <= 4:
            problems.append(f"ERROR: page {number} has {sentence_count} sentences; expected 2-4")
    new_words = unique_casefolded(token for token in tokens if token.lower() not in older_words)
    if not 10 <= len(new_words) <= 20:
        problems.append(f"WARNING: book has {len(new_words)} new words; target is 10-20")
    long_words = [token for token in tokens if len(token.replace("'", "")) >= 6]
    if len(long_words) > 10:
        problems.append(f"WARNING: book has {len(long_words)} long-word occurrences")
    return problems


def require_api_key() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")
