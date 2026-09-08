#!/usr/bin/env python3
"""Point every clinic contact number (including Zalo) at a single mobile.

The 1800 6834 hotline is deliberately preserved everywhere, as are numbers
that only look like phones: the business registration number, the example in
form placeholders, and patient numbers quoted inside testimonials.

A second pass fixes legacy pages that print the hotline as 1900 6834 while
linking to tel:18006834, so the visible number matches the link target.
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUFFIXES = {".html", ".htm", ".asp"}
NEW_PHONE = "0334266646"
HOTLINE = "18006834"
HOTLINE_TYPO = "19006834"

# Clinic contact numbers that must all collapse onto NEW_PHONE.
OLD_NUMBERS = [
    "032257300111",
    "02257300111",
    "02557300111",
    "02432123435",
    "0943954889",
    "0912759613",
    "0317300111",
    "0975537259",
]

# Never touched: the hotline the user asked to keep, the business registration
# number, the form placeholder example, and a patient's own number quoted in a
# testimonial. (19006834 is not listed here because the hotline pass has already
# turned it into HOTLINE by the time the contact pass runs.)
PRESERVED = ["18006834", "0313656992", "0912345678", "0979482619"]

SEPARATOR = r"[\s.()\-]*"


def spaced(number: str) -> str:
    return SEPARATOR.join(map(re.escape, number))


PRESERVED_PATTERN = re.compile(
    r"(?<!\d)\+?(?:" + "|".join(spaced(n) for n in PRESERVED) + r")(?!\d)"
)
OLD_PATTERN = re.compile(
    r"(?<!\d)\+?(?:"
    + "|".join(spaced(n) for n in sorted(OLD_NUMBERS, key=len, reverse=True))
    + r")(?!\d)"
)
HOTLINE_TYPO_PATTERN = re.compile(r"(?<!\d)" + spaced(HOTLINE_TYPO) + r"(?!\d)")


def markup_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file() and path.suffix.lower() in SUFFIXES and ".git" not in path.parts
    )


def formatted(match: re.Match[str]) -> str:
    """Keep the grouping style the old number used (0912.759.613 -> 0334.266.646)."""
    sep = separator_of(match.group(0))
    if sep is None:
        return NEW_PHONE
    return sep.join((NEW_PHONE[:4], NEW_PHONE[4:7], NEW_PHONE[7:]))


def separator_of(text: str) -> str | None:
    separators = [c for c in text if c in " .-"]
    if not separators:
        return None
    return Counter(separators).most_common(1)[0][0]


def fix_hotline(match: re.Match[str]) -> str:
    """1900 6834 -> 1800 6834, keeping whatever grouping the page already used."""
    sep = separator_of(match.group(0))
    return HOTLINE if sep is None else sep.join((HOTLINE[:4], HOTLINE[4:]))


def rewrite(text: str) -> tuple[str, int]:
    """Replace clinic numbers, stepping over every preserved number untouched."""
    out: list[str] = []
    count = 0
    cursor = 0
    for keep in PRESERVED_PATTERN.finditer(text):
        chunk, hits = OLD_PATTERN.subn(formatted, text[cursor : keep.start()])
        out.append(chunk)
        out.append(keep.group(0))
        count += hits
        cursor = keep.end()
    chunk, hits = OLD_PATTERN.subn(formatted, text[cursor:])
    out.append(chunk)
    return "".join(out), count + hits


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    changed_files = 0
    replacements = 0
    hotlines_fixed = 0
    for path in markup_files():
        original = path.read_text(encoding="utf-8", errors="surrogateescape")
        updated, hotline_count = HOTLINE_TYPO_PATTERN.subn(fix_hotline, original)
        updated, count = rewrite(updated)
        if updated == original:
            continue
        if not args.dry_run:
            path.write_text(updated, encoding="utf-8", errors="surrogateescape", newline="\n")
        changed_files += 1
        replacements += count
        hotlines_fixed += hotline_count
    print(f"changed_files={changed_files}")
    print(f"numbers_updated={replacements}")
    print(f"hotline_typos_fixed={hotlines_fixed}")


if __name__ == "__main__":
    main()
