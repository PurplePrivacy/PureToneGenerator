#!/usr/bin/env python3
"""Download all 50 books from Project Gutenberg (French translations).

Run once:  python books/fetch_books.py

- Downloads each book by Gutenberg ID
- Strips Gutenberg headers/footers
- Saves cleaned text to books/texts/<name>.txt
- Skips already-downloaded files (re-run safe)
- Handles encoding (UTF-8, Latin-1 fallback)
"""

import os
import sys
import time
import urllib.request
import urllib.error

# Allow running from project root or from inside books/
_here = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_here)
sys.path.insert(0, _project_root)

from books.catalog import BOOK_CATALOG

TEXTS_DIR = os.path.join(_here, "texts")
os.makedirs(TEXTS_DIR, exist_ok=True)

# Gutenberg URL patterns (they vary by era and mirror)
_URL_PATTERNS = [
    "https://www.gutenberg.org/cache/epub/{gid}/pg{gid}.txt",
    "https://www.gutenberg.org/files/{gid}/{gid}-0.txt",
    "https://www.gutenberg.org/files/{gid}/{gid}.txt",
]

# Standard Gutenberg markers for header/footer stripping
_START_MARKERS = [
    "*** START OF THIS PROJECT GUTENBERG",
    "*** START OF THE PROJECT GUTENBERG",
    "***START OF THIS PROJECT GUTENBERG",
    "***START OF THE PROJECT GUTENBERG",
]
_END_MARKERS = [
    "*** END OF THIS PROJECT GUTENBERG",
    "*** END OF THE PROJECT GUTENBERG",
    "***END OF THIS PROJECT GUTENBERG",
    "***END OF THE PROJECT GUTENBERG",
    "End of the Project Gutenberg",
    "End of Project Gutenberg",
]


def _fetch_url(url: str) -> str | None:
    """Fetch URL content as string. Returns None on failure."""
    req = urllib.request.Request(url, headers={"User-Agent": "PureToneGenerator/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return None

    # Try UTF-8 first, then Latin-1 (covers most Gutenberg French texts)
    for enc in ("utf-8", "latin-1", "iso-8859-1", "cp1252"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return None


def _strip_gutenberg(text: str) -> str:
    """Remove Project Gutenberg header and footer boilerplate."""
    lines = text.splitlines(keepends=True)

    # Find start marker
    start_idx = 0
    for i, line in enumerate(lines):
        upper = line.upper()
        if any(m.upper() in upper for m in _START_MARKERS):
            start_idx = i + 1
            # Skip blank lines right after marker
            while start_idx < len(lines) and lines[start_idx].strip() == "":
                start_idx += 1
            break

    # Find end marker
    end_idx = len(lines)
    for i in range(len(lines) - 1, start_idx, -1):
        upper = lines[i].upper()
        if any(m.upper() in upper for m in _END_MARKERS):
            end_idx = i
            break

    return "".join(lines[start_idx:end_idx]).strip()


def download_book(name: str, meta: dict, index: int, total: int) -> bool:
    """Download a single book. Returns True on success."""
    out_path = os.path.join(TEXTS_DIR, f"{name}.txt")
    if os.path.exists(out_path) and os.path.getsize(out_path) > 100:
        print(f"  [{index}/{total}] {meta['title']} — {meta['author']}  [already downloaded]")
        return True

    gid = meta["gutenberg_id"]
    print(f"  [{index}/{total}] Downloading: {meta['title']} — {meta['author']} (ID {gid})...", end="", flush=True)

    text = None
    for pattern in _URL_PATTERNS:
        url = pattern.format(gid=gid)
        text = _fetch_url(url)
        if text and len(text) > 500:
            break
        text = None

    if text is None:
        print("  FAILED (not found)")
        return False

    cleaned = _strip_gutenberg(text)
    if len(cleaned) < 200:
        print(f"  WARNING (only {len(cleaned)} chars after stripping)")
        # Save anyway — user can inspect
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(cleaned)
        return False

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(cleaned)

    words = len(cleaned.split())
    print(f"  OK ({words:,} words)")
    return True


def main():
    total = len(BOOK_CATALOG)
    print(f"\nFetching {total} books from Project Gutenberg...\n")

    ok = 0
    failed = []
    for i, (name, meta) in enumerate(BOOK_CATALOG.items(), 1):
        if download_book(name, meta, i, total):
            ok += 1
        else:
            failed.append(name)
        # Be polite to Gutenberg servers
        time.sleep(1.0)

    print(f"\nDone: {ok}/{total} downloaded successfully.")
    if failed:
        print(f"Failed ({len(failed)}): {', '.join(failed)}")
        print("You can re-run this script to retry failed downloads.")
    print(f"\nBooks saved to: {TEXTS_DIR}/")


if __name__ == "__main__":
    main()
