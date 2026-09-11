"""Check that every local href/src in the repo's HTML resolves to a file on disk.

Broken relative asset paths are the one failure a human reading a page would not
notice: the page still renders, just unstyled, unhighlighted, and with a dead
quiz. Every lesson in every topic links the shared stylesheet from its own depth,
so one wrong `../` silently breaks every page written from then on.

Run from anywhere:

    uv run python scripts/check-asset-paths.py

Exits 0 when every link resolves, 1 with a report otherwise.

Two rules are enforced:

1. Every local link resolves to an existing file.
2. No link is root-absolute. A leading `/` breaks both `file://` reading and
   GitHub Pages project sites, which serve this repo under `/researcher/`.

External links (`http:`, `https:`, `mailto:`) and bare fragments are ignored --
this checks asset geometry, not the reachability of the web.
"""

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

REPO_ROOT = Path(__file__).resolve().parent.parent

# Matches href="..." and src="..." with single, double, or no quotes.
LINK_PATTERN = re.compile(
    r"""\b(href|src)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""",
    re.IGNORECASE,
)

IGNORED_SCHEMES = ("http:", "https:", "mailto:", "data:", "tel:", "//")

COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)


def without_comments(html: str) -> str:
    """Blank out HTML comments, keeping line numbers intact.

    A commented-out link is not a link. Pages carry example markup in comments
    to show an author what to add -- those examples point at files that do not
    exist yet, by design.
    """
    return COMMENT_PATTERN.sub(
        lambda match: "\n" * match.group(0).count("\n"), html
    )


def links_in(html_path: Path) -> list[tuple[int, str, str]]:
    """Return (line number, attribute, raw value) for each link in a file."""
    found = []
    html = without_comments(html_path.read_text(encoding="utf-8"))
    for line_number, line in enumerate(html.splitlines(), start=1):
        for match in LINK_PATTERN.finditer(line):
            attribute = match.group(1).lower()
            value = match.group(2) or match.group(3) or match.group(4) or ""
            found.append((line_number, attribute, value))
    return found


def problem_with(html_path: Path, attribute: str, value: str) -> str | None:
    """Return a human-readable problem with this link, or None if it is fine."""
    value = value.strip()
    if not value or value.startswith("#"):
        return None
    if value.lower().startswith(IGNORED_SCHEMES):
        return None

    if value.startswith("/"):
        return f"root-absolute {attribute} (breaks file:// and Pages subpaths)"

    target = unquote(urlsplit(value).path)
    if not target:
        return None

    resolved = (html_path.parent / target).resolve()
    if not resolved.exists():
        return f"{attribute} does not resolve to a file on disk"
    return None


def main() -> int:
    html_files = sorted(
        path
        for path in REPO_ROOT.rglob("*.html")
        if ".git" not in path.parts
    )

    if not html_files:
        print("No HTML files found -- nothing to check.")
        return 0

    failures = []
    link_count = 0
    for html_path in html_files:
        for line_number, attribute, value in links_in(html_path):
            link_count += 1
            problem = problem_with(html_path, attribute, value)
            if problem:
                relative = html_path.relative_to(REPO_ROOT)
                failures.append(f"{relative}:{line_number}: {problem}: {value!r}")

    for failure in failures:
        print(f"FAIL {failure}")

    pages = len(html_files)
    if failures:
        print(
            f"\n{len(failures)} broken link(s) "
            f"across {link_count} link(s) in {pages} page(s)."
        )
        return 1

    print(f"OK {link_count} local link(s) resolve across {pages} page(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
