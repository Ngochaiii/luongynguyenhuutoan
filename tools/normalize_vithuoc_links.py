#!/usr/bin/env python3
"""Audit and normalize thaythuoccuaban.com links in static markup."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit


TARGET_HOSTS = {"amp.thaythuoccuaban.com", "thaythuoccuaban.com"}
ANCHOR_OPEN_RE = re.compile(r"<a\b[^>]*>", re.IGNORECASE | re.DOTALL)
HREF_RE = re.compile(
    r"\bhref\s*=\s*(?P<quote>['\"])(?P<url>.*?)(?P=quote)",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class LinkReference:
    original_url: str
    normalized_url: str
    url_start: int
    url_end: int
    anchor_start: int
    anchor_open_end: int


def normalize_url(url: str) -> str | None:
    parsed = urlsplit(html.unescape(url.strip()))
    if (parsed.hostname or "").lower() not in TARGET_HOSTS:
        return None
    path = re.sub(r"(?i)\.htm$", ".html", parsed.path)
    return urlunsplit(
        ("https", "thaythuoccuaban.com", path, parsed.query, parsed.fragment)
    )


def find_anchor_links(text: str) -> list[LinkReference]:
    references = []
    for anchor in ANCHOR_OPEN_RE.finditer(text):
        href = HREF_RE.search(anchor.group(0))
        if href is None:
            continue
        original = href.group("url")
        normalized = normalize_url(original)
        if normalized is None:
            continue
        url_start = anchor.start() + href.start("url")
        references.append(
            LinkReference(
                original_url=original,
                normalized_url=normalized,
                url_start=url_start,
                url_end=anchor.start() + href.end("url"),
                anchor_start=anchor.start(),
                anchor_open_end=anchor.end(),
            )
        )
    return references
