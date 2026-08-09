#!/usr/bin/env python3
"""Audit and normalize thaythuoccuaban.com links in static markup."""

from __future__ import annotations

import argparse
import html
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping
from urllib.error import HTTPError
from urllib.parse import urldefrag, urlsplit, urlunsplit
from urllib.request import Request, urlopen


TARGET_HOSTS = {"amp.thaythuoccuaban.com", "thaythuoccuaban.com"}
ROOT = Path(__file__).resolve().parents[1]
MARKUP_SUFFIXES = {".html", ".htm", ".asp"}
ANCHOR_OPEN_RE = re.compile(r"<a\b[^>]*>", re.IGNORECASE | re.DOTALL)
START_TAG_RE = re.compile(
    r"<(?P<tag>[A-Za-z][\w:-]*)\b[^>]*>", re.IGNORECASE | re.DOTALL
)
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
    tag_name: str


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
    removed_tag_count: int = 0


def normalize_url(url: str) -> str | None:
    parsed = urlsplit(html.unescape(url.strip()))
    if (parsed.hostname or "").lower() not in TARGET_HOSTS:
        return None
    path = re.sub(r"(?i)\.htm$", ".html", parsed.path)
    return urlunsplit(
        ("https", "thaythuoccuaban.com", path, parsed.query, parsed.fragment)
    )


def find_anchor_links(text: str) -> list[LinkReference]:
    return [reference for reference in find_href_links(text) if reference.tag_name == "a"]


def find_href_links(text: str) -> list[LinkReference]:
    references = []
    for tag in START_TAG_RE.finditer(text):
        href = HREF_RE.search(tag.group(0))
        if href is None:
            continue
        original = href.group("url")
        normalized = normalize_url(original)
        if normalized is None:
            continue
        url_start = tag.start() + href.start("url")
        references.append(
            LinkReference(
                original_url=original,
                normalized_url=normalized,
                url_start=url_start,
                url_end=tag.start() + href.end("url"),
                anchor_start=tag.start(),
                anchor_open_end=tag.end(),
                tag_name=tag.group("tag").lower(),
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
    removed_tag_count = 0
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

    for reference in find_href_links(text):
        if reference.tag_name != "link":
            continue
        result = results.get(urldefrag(reference.normalized_url)[0])
        if result is not None and result.classification == "dead":
            full_replacements.append(
                (reference.anchor_start, reference.anchor_open_end, "")
            )
            removed_tag_count += 1

    transformed = text
    for start, end, replacement in reversed(full_replacements):
        transformed = transformed[:start] + replacement + transformed[end:]

    normalized_count = 0
    for reference in reversed(find_href_links(transformed)):
        replacement = html.escape(reference.normalized_url, quote=True)
        if html.unescape(reference.original_url) == reference.normalized_url:
            continue
        transformed = (
            transformed[: reference.url_start]
            + replacement
            + transformed[reference.url_end :]
        )
        normalized_count += 1

    return TransformResult(
        transformed, normalized_count, unwrapped_count, removed_tag_count
    )


def atomic_write(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.link-audit.tmp")
    try:
        temporary.write_text(
            text, encoding="utf-8", errors="surrogateescape", newline="\n"
        )
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def audit_project(
    root: Path,
    *,
    write: bool,
    report_path: Path,
    checker: Callable[..., dict[str, CheckResult]] = check_unique_urls,
    workers: int = 8,
    timeout: float = 15,
) -> dict[str, int]:
    documents: dict[Path, str] = {}
    references_by_request: dict[str, set[str]] = defaultdict(set)
    originals_by_request: dict[str, set[str]] = defaultdict(set)
    normalized_urls: list[str] = []

    for path in sorted(root.rglob("*")):
        if (
            not path.is_file()
            or path.suffix.lower() not in MARKUP_SUFFIXES
            or ".git" in path.parts
        ):
            continue
        text = path.read_text(encoding="utf-8", errors="surrogateescape")
        references = find_href_links(text)
        if not references:
            continue
        documents[path] = text
        relative = path.relative_to(root).as_posix()
        for reference in references:
            request_url = urldefrag(reference.normalized_url)[0]
            normalized_urls.append(reference.normalized_url)
            references_by_request[request_url].add(relative)
            originals_by_request[request_url].add(reference.original_url)

    results = checker(normalized_urls, workers=workers, timeout=timeout)
    missing = sorted(set(references_by_request) - set(results))
    if missing:
        raise RuntimeError(f"Missing HTTP results for {len(missing)} URLs")

    transformed_documents: dict[Path, str] = {}
    normalized_count = 0
    unwrapped_count = 0
    removed_tag_count = 0
    for path, text in documents.items():
        transformed = transform_document(text, results)
        normalized_count += transformed.normalized_count
        unwrapped_count += transformed.unwrapped_count
        removed_tag_count += transformed.removed_tag_count
        if transformed.text != text:
            transformed_documents[path] = transformed.text

    classifications = Counter(result.classification for result in results.values())
    summary = {
        "source_files": len(documents),
        "references": len(normalized_urls),
        "unique_request_urls": len(results),
        "live": classifications["live"],
        "dead": classifications["dead"],
        "uncertain": classifications["uncertain"],
        "changed_files": len(transformed_documents),
        "normalized_links": normalized_count,
        "unwrapped_links": unwrapped_count,
        "removed_link_tags": removed_tag_count,
    }
    links = []
    for request_url in sorted(results):
        result = results[request_url]
        links.append(
            {
                "normalized_url": request_url,
                "original_urls": sorted(originals_by_request[request_url]),
                "status": result.status,
                "final_url": result.final_url,
                "classification": result.classification,
                "error": result.error,
                "references": sorted(references_by_request[request_url]),
            }
        )
    report = {"summary": summary, "links": links}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(
        report_path,
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )

    if write:
        for path, text in transformed_documents.items():
            atomic_write(path, text)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "reports" / "vithuoc-link-audit.json",
    )
    args = parser.parse_args()
    summary = audit_project(
        ROOT,
        write=args.write,
        report_path=args.report,
        workers=args.workers,
        timeout=args.timeout,
    )
    for key, value in summary.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
