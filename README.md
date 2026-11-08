# Books

Tools and shared reading UI for a local library of early-reader picture books.
See [AGENTS.md](AGENTS.md) for writing and illustration instructions,
[BOOKMAKER.md](BOOKMAKER.md) for the generation pipeline, and
[DEPLOY.md](DEPLOY.md) for publishing.

## Git workflow

This is a standalone repository, separate from the parent dotfiles repository.
Track code, shared `book.css` and `book.js`, configuration, tests, and docs here.
Use normal branches, commits, and pushes for changes to those files.

The library stays local and is ignored by Git:

- All root HTML files, including the changing `index.html` catalog
- `art/` illustrations and originals
- `book-data/` stories, visual plans, prompts, and generation results
- `.deploy/` staged uploads and the private deployment key
- Environment files, virtual environments, and caches

Adding or editing a book and updating its catalog entry therefore leaves
`git status` clean. Publish books with `make deploy`; that uploads to the book
server and does not commit or push anything to GitHub. Never force-add the
ignored library or credentials.

## Local setup

Install `uv` and `cwebp` (`brew install webp`), then run `uv sync`.
Run checks with `make test`. Set `OPENAI_API_KEY` in your environment when
using the generation pipeline.

A clone contains the tools, not the library. To use the existing collection
on another machine, copy the root HTML files, `art/`, and `book-data/` from
this machine separately. For deployment, also provision the ignored SSH key
as described in `DEPLOY.md`. GitHub is not a backup of the local library.

You can also publish from a partial checkout: `make sync-catalog` loads the
published vocabulary, and `make deploy SLUG=space-cats` publishes just one local
book while preserving the remote library. See [DEPLOY.md](DEPLOY.md).
