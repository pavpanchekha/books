# Bookmaker

`bookmaker` turns an idea into a reviewed seven-page early-reader book. It saves every intermediate artifact under `book-data/<slug>/`, puts illustrations under `art/<slug>/`, writes `<slug>.html`, and rebuilds the new-word data in `index.html`.

## Setup

```sh
uv sync
export OPENAI_API_KEY=...
```

Model assignments and image settings live in `bookmaker.toml`. Each role is independent. The Python provider protocol is intentionally small, so another backend (including an `llm` adapter) can be added without changing the pipeline.

## Full run

```sh
uv run bookmaker run space-cats "Nicholas meets kind cats in a tiny moon town" --deploy
```

The run is resumable: existing stage files and images are reused. Pass `--force` to regenerate them.

## Stage-by-stage use

```sh
uv run bookmaker write space-cats "Nicholas meets kind cats in a tiny moon town"
uv run bookmaker visuals space-cats
uv run bookmaker images space-cats
uv run bookmaker review space-cats
uv run bookmaker translate space-cats
uv run bookmaker build space-cats --deploy
```

This is useful when you want to edit `story.json` or `visual.json` by hand between stages. After a hand edit, pass `--force` to the immediately following stage so downstream art is refreshed. A forced writing or visual-planning stage also clears stale downstream artifacts automatically. Image review inspects all seven pages together. Failed pages are regenerated, up to `max_review_rounds`, and the complete set is reviewed again. Publishing stops if any page still fails unless `build --allow-review-failures` is explicitly used.

## Artifacts

- `story.json`: edited source-of-truth title, subtitle, and six content pages
- `editor-notes.json`: writing review notes
- `story-validation.json`: deterministic word and sentence checks
- `visual.json`: reviewed fixed visual bible, palette, and page scenes
- `art-review-notes.json`: art-direction review notes
- `prompts.md`: exact reproducible image prompts
- `image-review.json`: latest seven-page QA report
- `translations.json`: word-by-word Simplified Chinese map

Run tests with `uv run pytest`.

`make` requires `cwebp` (`brew install webp`). It creates full-resolution WebP
copies at quality 85, updates image URLs in the HTML, and deploys them. PNG/JPEG
originals remain locally for future edits but are excluded from deployment;
obsolete server originals are removed after the updated pages are uploaded.
Unchanged images are reused without recompression.
