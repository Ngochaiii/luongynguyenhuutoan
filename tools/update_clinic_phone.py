#!/usr/bin/env python3
"""Normalize only tel: targets while preserving displayed and Zalo numbers."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUFFIXES = {".html", ".htm", ".asp"}
NEW_PHONE = "18006834"
KNOWN_NUMBERS = {
    NEW_PHONE,
    "8418006834",
    "19006834",
    "0943954889",
    "0912759613",
    "0334266646",
    "02432123435",
    "02557300111",
    "02257300111",
    "0317300111",
    "032257300111",
    "0975537259",
}
SEPARATOR = r"[\s.()\-]*"


def number_body(number: str) -> str:
    return SEPARATOR.join(map(re.escape, number))


TOKEN_PATTERN = re.compile(
    r"(?<!\d)\+?(?:"
    + "|".join(number_body(number) for number in sorted(KNOWN_NUMBERS, key=len, reverse=True))
    + r")(?!\d)"
)
TEL_PATTERN = re.compile(r"(?i)tel:(?://)?\+?\d(?:[\s.()\-]*\d){5,14}")


def markup_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file() and path.suffix.lower() in SUFFIXES
    )


def restore_nonmodern_from_head() -> None:
    changed = 0
    skipped = []
    for path in markup_files():
        current_bytes = path.read_bytes()
        if b"herbal-modern.css" in current_bytes:
            continue
        relative = path.relative_to(ROOT).as_posix()
        result = subprocess.run(
            ["git", "show", f"HEAD:{relative}"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode:
            continue
        original = result.stdout.decode("utf-8", "surrogateescape")
        current = current_bytes.decode("utf-8", "surrogateescape")
        old_tokens = [match.group(0) for match in TOKEN_PATTERN.finditer(original)]
        current_tokens = list(TOKEN_PATTERN.finditer(current))
        if len(old_tokens) != len(current_tokens):
            skipped.append((relative, len(old_tokens), len(current_tokens)))
            continue
        values = iter(old_tokens)
        restored = TOKEN_PATTERN.sub(lambda _match: next(values), current)
        if restored != current:
            path.write_text(restored, encoding="utf-8", errors="surrogateescape", newline="\n")
            changed += 1
    print(f"restored_nonmodern_files={changed}")
    print(f"restore_skipped={len(skipped)}")
    for item in skipped:
        print("SKIP", *item)


def normalize_tel_targets() -> None:
    changed_files = 0
    replacements = 0
    for path in markup_files():
        original = path.read_text(encoding="utf-8", errors="surrogateescape")
        updated, count = TEL_PATTERN.subn(f"tel:{NEW_PHONE}", original)
        if updated == original:
            continue
        path.write_text(updated, encoding="utf-8", errors="surrogateescape", newline="\n")
        changed_files += 1
        replacements += count
    print(f"changed_files={changed_files}")
    print(f"tel_targets_updated={replacements}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore-nonmodern-from-head", action="store_true")
    args = parser.parse_args()
    if args.restore_nonmodern_from_head:
        restore_nonmodern_from_head()
    else:
        normalize_tel_targets()


if __name__ == "__main__":
    main()
