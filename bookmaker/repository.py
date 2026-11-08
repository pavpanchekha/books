from __future__ import annotations

import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable

from .models import BookDraft, TranslationSet, VisualPlan

WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")


def words(text: str) -> list[str]:
    return WORD_RE.findall(text)


def visible_words(draft: BookDraft) -> list[str]:
    return words(" ".join([draft.title, *(page.text for page in draft.pages)]))


class BookHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._capture: str | None = None
        self._buffer: list[str] = []
        self.title = ""
        self.stories: list[str] = []
        self.is_book = False

    @staticmethod
    def _classes(attrs: list[tuple[str, str | None]]) -> set[str]:
        value = dict(attrs).get("class") or ""
        return set(value.split())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = self._classes(attrs)
        if tag == "section" and "book" in classes:
            self.is_book = True
        if tag == "h1":
            self._capture = "title"
            self._buffer = []
        elif tag == "p" and "story" in classes:
            self._capture = "story"
            self._buffer = []
        elif tag == "br" and self._capture:
            self._buffer.append(" ")

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1" and self._capture == "title":
            self.title = re.sub(r"\s+", " ", "".join(self._buffer)).strip()
            self._capture = None
        elif tag == "p" and self._capture == "story":
            text = re.sub(r"\s+", " ", "".join(self._buffer)).strip()
            self.stories.append(text)
            self._capture = None


def parse_book(path: Path) -> tuple[str, list[str]]:
    parser = BookHTMLParser()
    parser.feed(path.read_text())
    if not parser.is_book or not parser.title:
        raise ValueError(f"Not a generated book: {path}")
    return parser.title, parser.stories


def cached_tokens(root: Path, filename: str) -> list[str]:
    cache = root / ".deploy" / "catalog.json"
    if cache.exists():
        return json.loads(cache.read_text()).get(filename, {}).get("tokens", [])
    return []


def corpus_words(root: Path) -> list[str]:
    result: list[str] = []
    for filename in index_order(root):
        path = root / filename
        if path.exists():
            title, stories = parse_book(path)
            result.extend(words(" ".join([title, *stories])))
        else:
            result.extend(cached_tokens(root, filename))
    return result


def older_corpus_words(root: Path, filename: str) -> list[str]:
    """Return tokens in books older than filename, or all books for a new title."""
    order = index_order(root)
    if filename in order:
        order = order[order.index(filename) + 1 :]
    result: list[str] = []
    for older_filename in order:
        path = root / older_filename
        if path.exists():
            title, stories = parse_book(path)
            result.extend(words(" ".join([title, *stories])))
        else:
            result.extend(cached_tokens(root, older_filename))
    return result


def index_order(root: Path) -> list[str]:
    if not (root / "index.html").exists():
        return []
    index = (root / "index.html").read_text()
    match = re.search(r'<ol class="book-list">(.*?)</ol>', index, re.DOTALL)
    if not match:
        raise ValueError("index.html has no book-list")
    ordered: list[str] = []
    for filename in re.findall(r'href="([^"]+\.html)"', match.group(1)):
        if filename not in ordered:
            ordered.append(filename)
    return ordered


def _sentence_html(text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return "<br /><br />".join(html.escape(part, quote=False) for part in sentences)


def _title_html(title: str) -> str:
    title_words = title.split()
    if len(title) <= 16:
        return html.escape(title)
    lines: list[str] = []
    line: list[str] = []
    for word in title_words:
        candidate = " ".join([*line, word])
        if line and len(candidate) > 15:
            lines.append(" ".join(line))
            line = [word]
        else:
            line.append(word)
    if line:
        lines.append(" ".join(line))
    return "<br />".join(html.escape(line) for line in lines)


def render_book(
    *,
    slug: str,
    draft: BookDraft,
    visual: VisualPlan,
    translations: TranslationSet,
) -> str:
    translation_map = {item.word.lower(): item.chinese for item in translations.translations}
    translation_json = html.escape(
        json.dumps(translation_map, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        quote=True,
    )
    p = visual.palette
    body_style = (
        f"--body-background: {p.body_background}; --ink: {p.ink}; --paper: {p.paper}; "
        f"--heading: {p.heading}; --accent: {p.accent}; --subtitle: {p.subtitle}; "
        f"--active-dot: {p.active_dot}; --focus-color: {p.focus}; "
        f"--button-shadow: color-mix(in srgb, {p.accent} 28%, transparent); "
        f"--dot-color: color-mix(in srgb, {p.accent} 30%, transparent); "
        f"--top-control-background: color-mix(in srgb, {p.ink} 80%, transparent); "
        f"--top-control-shadow: color-mix(in srgb, {p.ink} 22%, transparent); "
        "--story-size: clamp(39px, 4.5vw, 65px)"
    )
    pages: list[str] = []
    for index, scene in enumerate(visual.scenes):
        active = " active" if index == 0 else ""
        label = "Cover" if index == 0 else f"Page {index + 1}"
        if index == 0:
            copy = (
                f'<h1>{_title_html(draft.title)}</h1>\n'
                f'          <p class="subtitle">{html.escape(draft.subtitle)}</p>'
            )
        else:
            copy = f'<p class="story">{_sentence_html(draft.pages[index - 1].text)}</p>'
        pages.append(
            f'''      <article class="page{active}" data-page="{index + 1}" aria-label="{label}" style="--copy-background: {p.copy_backgrounds[index]};">
        <div class="copy">{copy}</div>
        <div class="art" aria-hidden="true">
          <img src="art/{slug}/{scene.filename}" alt="" width="960" height="1280" />
        </div>
      </article>'''
        )
    safe_bible = visual.visual_bible.replace("-->", "—>")
    bible = "\n".join(f"  {line}" for line in safe_bible.splitlines())
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <title>{html.escape(draft.title)}</title>
  <link rel="stylesheet" href="book.css" />
</head>
<!--
Visual bible:
{bible}
-->
<body style="{body_style}">
  <main class="book-shell">
    <section class="book" data-translations="{translation_json}" data-swipe-threshold="110" aria-label="{html.escape(draft.title)}, a seven-page picture book">
      <a class="index-link" href="index.html" aria-label="Back to book index">← Index</a>

{chr(10).join(pages)}

      <div class="top-controls" aria-label="Book options">
        <button id="chinese-toggle" class="chinese-toggle" type="button" aria-pressed="false" aria-label="Enable Chinese word translations" title="Enable Chinese word translations">中</button>
        <button id="fullscreen" type="button" aria-label="Enter full screen" title="Enter full screen">⛶</button>
      </div>
      <div class="controls" aria-label="Page controls">
        <button id="prev" type="button" aria-label="Previous page">←</button>
        <div class="dots" aria-label="Page list"></div>
        <button id="next" type="button" aria-label="Next page">→</button>
      </div>
    </section>
  </main>
  <script src="book.js"></script>
</body>
</html>
'''


def update_index(root: Path, newest_filename: str, *, local_filenames: set[str] | None = None) -> None:
    order = index_order(root)
    if newest_filename not in order:
        order.insert(0, newest_filename)
    cache_path = root / ".deploy" / "catalog.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    books: list[tuple[str, str, list[str]]] = []
    for filename in order:
        path = root / filename
        if path.exists() and (local_filenames is None or filename in local_filenames):
            title, stories = parse_book(path)
            books.append((filename, title, words(" ".join([title, *stories]))))
        elif filename in cache:
            record = cache[filename]
            books.append((filename, record["title"], record["tokens"]))
        else:
            raise ValueError(f"Missing catalog data for {filename}; run make sync-catalog")

    older: set[str] = set()
    rendered_reversed: list[str] = []
    for filename, title, tokens in reversed(books):
        seen: set[str] = set()
        new_words: list[str] = []
        for token in tokens:
            key = token.lower()
            if key not in older and key not in seen:
                new_words.append(token)
                seen.add(key)
        slug = filename.removesuffix(".html")
        items = "".join(f"<li>{html.escape(word)}</li>" for word in new_words)
        rendered_reversed.append(
            f'''        <li>
          <a href="{html.escape(filename)}"><span>{html.escape(title)}</span><span class="book-count">{len(tokens)} English words</span></a>
          <section class="book-new-words" aria-labelledby="{slug}-new-words"><h3 id="{slug}-new-words">New words ({len(new_words)})</h3><ul class="book-new-word-list">{items}</ul></section>
        </li>'''
        )
        older.update(token.lower() for token in tokens)
    rendered = "\n".join(reversed(rendered_reversed))
    index_path = root / "index.html"
    source = index_path.read_text() if index_path.exists() else '<!doctype html><html><head><link rel="stylesheet" href="book.css"></head><body><h1>Books</h1><ol class="book-list"></ol></body></html>'
    updated, count = re.subn(
        r'<ol class="book-list">.*?</ol>',
        f'<ol class="book-list">\n{rendered}\n      </ol>',
        source,
        count=1,
        flags=re.DOTALL,
    )
    if count != 1:
        raise ValueError("Could not replace index book list")
    index_path.write_text(updated)


def unique_casefolded(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.lower()
        if key not in seen:
            result.append(value)
            seen.add(key)
    return result
