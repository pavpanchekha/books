"""Create full-resolution WebP copies and point the books at them.

Originals stay local for regeneration; make deploys only the WebP copies.
Requires cwebp (brew install webp).
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re
import os
import subprocess
import argparse

ROOT = Path(__file__).resolve().parent
SOURCE_SUFFIXES = {".png", ".jpg", ".jpeg"}
ART_URL = re.compile(r'(src=["\'])(art/[^"\']+\.(?:png|jpg|jpeg))(["\'])', re.I)


def compress(source: Path) -> Path:
    target = source.with_suffix(".webp")
    if not target.exists() or target.stat().st_mtime < source.stat().st_mtime:
        temporary = target.with_suffix(".webp.tmp")
        subprocess.run(
            ["cwebp", "-quiet", "-q", "85", str(source), "-o", str(temporary)],
            check=True,
        )
        temporary.replace(target)
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug")
    args = parser.parse_args()
    if args.slug and not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", args.slug):
        parser.error("invalid slug")
    art_root = ROOT / "art" / args.slug if args.slug else ROOT / "art"
    sources = sorted(p for p in art_root.rglob("*") if p.suffix.lower() in SOURCE_SUFFIXES)
    targets = [source.with_suffix(".webp") for source in sources]
    if len(set(targets)) != len(targets):
        raise RuntimeError("Multiple originals would overwrite the same WebP")
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(compress, sources))
    # Hard links create an upload tree without duplicating image data on disk.
    for source in art_root.rglob("*"):
        if not source.is_file() or source.suffix.lower() in SOURCE_SUFFIXES:
            continue
        staged = ROOT / ".deploy" / source.relative_to(ROOT)
        staged.parent.mkdir(parents=True, exist_ok=True)
        if staged.exists():
            if os.path.samefile(source, staged):
                continue
            staged.unlink()
        os.link(source, staged)

    def replace_url(match: re.Match) -> str:
        target = Path(match[2]).with_suffix(".webp")
        if not (ROOT / target).is_file():
            raise RuntimeError(f"Missing compressed art: {target}")
        return f"{match[1]}{target.as_posix()}{match[3]}"

    pages = [ROOT / f"{args.slug}.html"] if args.slug else ROOT.glob("*.html")
    for page in pages:
        original = page.read_text()
        updated = ART_URL.sub(replace_url, original)
        if updated != original:
            page.write_text(updated)
    before = sum(p.stat().st_size for p in sources)
    after = sum(p.stat().st_size for p in targets)
    print(f"{len(sources)} images: {before / 1024**2:.1f} MiB originals -> "
          f"{after / 1024**2:.1f} MiB WebP ({1 - after / before if before else 0:.1%} smaller)")


if __name__ == "__main__":
    main()
