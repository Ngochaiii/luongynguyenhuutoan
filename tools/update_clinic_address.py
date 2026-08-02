#!/usr/bin/env python3
"""Replace legacy clinic-address variants in website markup."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUFFIXES = {".html", ".htm", ".asp"}
NEW_ADDRESS = "Số 481 lô 22 Lê Hồng Phong, Phường Gia Viên, Thành phố Hải Phòng"
NEW_MAP = (
    "https://www.google.com/maps/search/?api=1&amp;query="
    "S%E1%BB%91%20481%20l%C3%B4%2022%20L%C3%AA%20H%E1%BB%93ng%20Phong%2C%20"
    "Ph%C6%B0%E1%BB%9Dng%20Gia%20Vi%C3%AAn%2C%20Th%C3%A0nh%20ph%E1%BB%91%20H%E1%BA%A3i%20Ph%C3%B2ng"
)

SPACE = r"(?:\s|&nbsp;|&#160;|<br\s*/?>)*"
OLD_ADDRESS = re.compile(
    rf"(?:(?:số)(?:{SPACE}nhà)?{SPACE})?"
    rf"(?:481{SPACE}[-–]{SPACE}482|481|482){SPACE},?{SPACE}"
    rf"lô{SPACE}22{SPACE}c?{SPACE},?{SPACE}"
    rf"(?:(?:đường){SPACE})?lê{SPACE}hồng{SPACE}phong"
    rf"{SPACE},?{SPACE}"
    rf"(?:(?:đông{SPACE}khê){SPACE},?{SPACE})?"
    rf"(?:(?:(?:quận){SPACE})?ngô{SPACE}quyền{SPACE},?{SPACE})?"
    rf"(?:(?:thành{SPACE}phố|tp\.?)?{SPACE}hải{SPACE}phòng)?",
    re.IGNORECASE,
)
OLD_MAP = re.compile(r"https://maps\.app\.goo\.gl/UT5oeUn4nBVrPFAu8")
STALE_SUFFIX = re.compile(
    re.escape(NEW_ADDRESS)
    + r"(?:\s*(?:,?\s*(?:Đông Khê,?\s*)?(?:Quận\s*)?Ngô Quyền,?\s*Hải Phòng|[–-]\s*Hải Phòng))",
    re.IGNORECASE,
)


def replace_address(match: re.Match[str]) -> str:
    # Do not touch text that is already followed by the new ward/city wording.
    following = match.string[match.end() : match.end() + 100]
    if re.match(r"\s*,?\s*Phường\s+Gia\s+Viên", following, re.IGNORECASE):
        return match.group(0)
    return NEW_ADDRESS


def main() -> None:
    changed_files = 0
    replacements = 0
    map_links = 0
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUFFIXES:
            continue
        original = path.read_text(encoding="utf-8", errors="surrogateescape")
        updated, count = OLD_ADDRESS.subn(replace_address, original)
        updated = STALE_SUFFIX.sub(NEW_ADDRESS, updated)
        updated, map_count = OLD_MAP.subn(NEW_MAP, updated)
        if NEW_ADDRESS in updated:
            updated = re.sub(r"[ \t]+(?=\n)", "", updated)
            updated = re.sub(r" +\t", "\t", updated)
        if updated == original:
            continue
        path.write_text(updated, encoding="utf-8", errors="surrogateescape", newline="\n")
        changed_files += 1
        replacements += count
        map_links += map_count
    print(f"changed_files={changed_files}")
    print(f"address_replacements={replacements}")
    print(f"map_links_updated={map_links}")


if __name__ == "__main__":
    main()
