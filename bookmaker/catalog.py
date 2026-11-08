"""Fetch reading metadata from the public site without retaining older books."""
from __future__ import annotations

import argparse
import json
import re
import tempfile
from pathlib import Path
from urllib.request import urlopen

from .repository import index_order, parse_book, words

SITE = "https://pavpanchekha.com/nsp/"


def sync_catalog(root: Path, site: str = SITE) -> None:
    def fetch(name: str) -> str:
        with urlopen(site.rstrip("/") + "/" + name, timeout=30) as response:
            return response.read().decode("utf-8")

    # Collect and validate everything before changing local state.
    index = fetch("index.html")
    records = {}
    with tempfile.TemporaryDirectory() as directory:
        scratch = Path(directory)
        (scratch / "index.html").write_text(index)
        order = index_order(scratch)
        for filename in order:
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*\.html", filename):
                raise ValueError(f"Unsafe catalog filename: {filename}")
            page = scratch / filename
            page.write_text(fetch(filename))
            title, stories = parse_book(page)
            records[filename] = {"title": title, "tokens": words(" ".join([title, *stories]))}
            page.unlink()
    cache = root / ".deploy" / "catalog.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(records, ensure_ascii=False))
    (root / "index.html").write_text(index)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    sync_catalog(args.root)


if __name__ == "__main__":
    main()
