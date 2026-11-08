from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .pipeline import Pipeline, require_api_key, slugify, validate_story
from .models import BookDraft
from .repository import older_corpus_words


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="bookmaker",
        description="Generate, review, assemble, index, and deploy a Nicholas book.",
    )
    result.add_argument("--root", type=Path, default=Path.cwd(), help="books repository root")
    sub = result.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run every stage, resuming existing artifacts")
    run.add_argument("slug")
    run.add_argument("idea")
    run.add_argument("--force", action="store_true")
    run.add_argument("--deploy", action="store_true")

    write = sub.add_parser("write", help="write and edit the story")
    write.add_argument("slug")
    write.add_argument("idea")
    write.add_argument("--force", action="store_true")

    for name, help_text in [
        ("visuals", "create and review the visual bible and scenes"),
        ("images", "generate missing illustrations"),
        ("review", "review all illustrations and repair failed pages"),
        ("translate", "translate every visible word"),
    ]:
        command = sub.add_parser(name, help=help_text)
        command.add_argument("slug")
        if name in {"visuals", "images", "translate"}:
            command.add_argument("--force", action="store_true")

    build = sub.add_parser("build", help="render HTML and update the index")
    build.add_argument("slug")
    build.add_argument("--allow-review-failures", action="store_true")
    build.add_argument("--deploy", action="store_true")

    validate = sub.add_parser("validate", help="validate saved story constraints")
    validate.add_argument("slug")
    return result


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    try:
        root = args.root.resolve()
        slug = slugify(args.slug)
        api_commands = {"run", "write", "visuals", "images", "review", "translate"}
        if args.command in api_commands:
            require_api_key()
        pipeline = Pipeline(root)
        if args.command == "run":
            output = pipeline.run(slug=slug, idea=args.idea, force=args.force)
            print(output)
        elif args.command == "write":
            result = pipeline.write(slug=slug, idea=args.idea, force=args.force)
            print(result.model_dump_json(indent=2))
        elif args.command == "visuals":
            result = pipeline.visuals(slug=slug, force=args.force)
            print(result.model_dump_json(indent=2))
        elif args.command == "images":
            pipeline.images(slug=slug, force=args.force)
            print(pipeline.art_dir(slug))
        elif args.command == "review":
            result = pipeline.review_and_repair(slug=slug)
            print(result.model_dump_json(indent=2))
            failed = [page.page_number for page in result.pages if not page.passed]
            if failed:
                print(f"bookmaker: image QA still fails pages {failed}", file=sys.stderr)
                raise SystemExit(1)
        elif args.command == "translate":
            result = pipeline.translate(slug=slug, force=args.force)
            print(result.model_dump_json(indent=2))
        elif args.command == "build":
            output = pipeline.build(slug=slug, allow_review_failures=args.allow_review_failures)
            print(output)
        elif args.command == "validate":
            draft = BookDraft.model_validate_json((pipeline.source_dir(slug) / "story.json").read_text())
            older = set(token.lower() for token in older_corpus_words(root, f"{slug}.html"))
            problems = validate_story(draft, older)
            print("\n".join(problems) if problems else "Story constraints pass.")
            if any(problem.startswith("ERROR:") for problem in problems):
                raise SystemExit(1)
        if getattr(args, "deploy", False):
            subprocess.run(["make", "deploy", f"SLUG={slug}"], cwd=root, check=True)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"bookmaker: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
