#!/usr/bin/env python3
"""Audit and normalize thaythuoccuaban.com links in static markup."""

from __future__ import annotations

import html
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Iterable, Mapping
from urllib.error import HTTPError
from urllib.parse import urldefrag, urlsplit, urlunsplit
from urllib.request import Request, urlopen


TARGET_HOSTS = {"amp.thaythuoccuaban.com", "thaythuoccuaban.com"}
ANCHOR_OPEN_RE = re.compile(r"<a\b[^>]*>", re.IGNORECASE | re.DOTALL)
ANCHOR_FULL_RE = re.compile(
    r"<a\b[^>]*>(?P<inner>.*?)</a\s*>", re.IGNORECASE | re.DOTALL
)
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


@dataclass(frozen=True)
class HttpResponse:
    status: int
    final_url: str


@dataclass(frozen=True)
class CheckResult:
    request_url: str
    status: int | None
    final_url: str | None
    classification: str
    error: str | None = None


@dataclass(frozen=True)
class TransformResult:
    text: str
    normalized_count: int
    unwrapped_count: int


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


def classify_status(status: int) -> str:
    if 200 <= status <= 399:
        return "live"
    if status in {404, 410}:
        return "dead"
    return "uncertain"


def default_opener(method: str, url: str, timeout: float) -> HttpResponse:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; LinkAudit/1.0)",
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
    }
    if method == "GET":
        headers["Range"] = "bytes=0-0"
    request = Request(url, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            if method == "GET":
                response.read(1)
            return HttpResponse(response.getcode(), response.geturl())
    except HTTPError as error:
        return HttpResponse(error.code, error.geturl())


def check_url(
    url: str,
    *,
    opener: Callable[[str, str, float], HttpResponse] = default_opener,
    timeout: float = 15,
) -> CheckResult:
    request_url = urldefrag(url)[0]
    try:
        head = opener("HEAD", request_url, timeout)
        if classify_status(head.status) == "live":
            return CheckResult(
                request_url, head.status, head.final_url, "live"
            )
    except Exception:
        pass

    try:
        response = opener("GET", request_url, timeout)
        return CheckResult(
            request_url,
            response.status,
            response.final_url,
            classify_status(response.status),
        )
    except Exception as error:
        return CheckResult(
            request_url,
            None,
            None,
            "uncertain",
            f"{type(error).__name__}: {error}",
        )


def check_unique_urls(
    urls: Iterable[str],
    *,
    opener: Callable[[str, str, float], HttpResponse] = default_opener,
    workers: int = 8,
    timeout: float = 15,
) -> dict[str, CheckResult]:
    request_urls = sorted({urldefrag(url)[0] for url in urls})
    results: dict[str, CheckResult] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                check_url, url, opener=opener, timeout=timeout
            ): url
            for url in request_urls
        }
        for future in as_completed(futures):
            url = futures[future]
            results[url] = future.result()
    return results


def transform_document(
    text: str, results: Mapping[str, CheckResult]
) -> TransformResult:
    unwrapped_count = 0
    full_replacements: list[tuple[int, int, str]] = []
    for anchor in ANCHOR_FULL_RE.finditer(text):
        opening = ANCHOR_OPEN_RE.match(anchor.group(0))
        if opening is None:
            continue
        href = HREF_RE.search(opening.group(0))
        if href is None:
            continue
        normalized = normalize_url(href.group("url"))
        if normalized is None:
            continue
        result = results.get(urldefrag(normalized)[0])
        if result is not None and result.classification == "dead":
            full_replacements.append(
                (anchor.start(), anchor.end(), anchor.group("inner"))
            )
            unwrapped_count += 1

    transformed = text
    for start, end, replacement in reversed(full_replacements):
        transformed = transformed[:start] + replacement + transformed[end:]

    normalized_count = 0
    for reference in reversed(find_anchor_links(transformed)):
        replacement = html.escape(reference.normalized_url, quote=True)
        if html.unescape(reference.original_url) == reference.normalized_url:
            continue
        transformed = (
            transformed[: reference.url_start]
            + replacement
            + transformed[reference.url_end :]
        )
        normalized_count += 1

    return TransformResult(transformed, normalized_count, unwrapped_count)
