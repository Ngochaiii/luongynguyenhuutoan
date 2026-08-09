from __future__ import annotations

import unittest
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
import json

from tools.normalize_vithuoc_links import (
    HttpResponse,
    CheckResult,
    audit_project,
    check_unique_urls,
    check_url,
    classify_status,
    find_anchor_links,
    find_href_links,
    normalize_url,
    transform_document,
)


class NormalizeUrlTests(unittest.TestCase):
    def test_removes_amp_host_and_changes_htm_suffix(self) -> None:
        self.assertEqual(
            normalize_url("https://amp.thaythuoccuaban.com/vithuoc/thuocban.htm"),
            "https://thaythuoccuaban.com/vithuoc/thuocban.html",
        )

    def test_preserves_query_and_fragment(self) -> None:
        self.assertEqual(
            normalize_url("http://amp.thaythuoccuaban.com/vithuoc/a.htm?x=.htm#toa"),
            "https://thaythuoccuaban.com/vithuoc/a.html?x=.htm#toa",
        )

    def test_normalizes_main_domain_htm_path(self) -> None:
        self.assertEqual(
            normalize_url("https://thaythuoccuaban.com/vithuoc/a.HTM"),
            "https://thaythuoccuaban.com/vithuoc/a.html",
        )

    def test_ignores_other_domains(self) -> None:
        self.assertIsNone(normalize_url("https://example.com/a.htm"))

    def test_ignores_relative_links(self) -> None:
        self.assertIsNone(normalize_url("../vithuoc/a.htm"))

    def test_finds_quoted_anchor_links_only(self) -> None:
        source = (
            '<a href="https://amp.thaythuoccuaban.com/vithuoc/a.htm">A</a>'
            "<a href='https://thaythuoccuaban.com/vithuoc/b.htm'>B</a>"
            '<link href="https://amp.thaythuoccuaban.com/style.htm">'
        )
        links = find_anchor_links(source)
        self.assertEqual([link.original_url for link in links], [
            "https://amp.thaythuoccuaban.com/vithuoc/a.htm",
            "https://thaythuoccuaban.com/vithuoc/b.htm",
        ])
        self.assertTrue(all(source[link.url_start:link.url_end] == link.original_url for link in links))

    def test_finds_canonical_link_href(self) -> None:
        source = (
            '<link rel="canonical" '
            'href="https://amp.thaythuoccuaban.com/vithuoc/a.htm">'
        )
        links = find_href_links(source)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].tag_name, "link")
        self.assertEqual(
            links[0].normalized_url,
            "https://thaythuoccuaban.com/vithuoc/a.html",
        )


class FakeOpener:
    def __init__(self, outcomes: dict[str, list[HttpResponse | Exception]]) -> None:
        self.outcomes = {key: list(value) for key, value in outcomes.items()}
        self.calls: list[tuple[str, str]] = []

    def __call__(self, method: str, url: str, timeout: float) -> HttpResponse:
        self.calls.append((method, url))
        outcome = self.outcomes[method].pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class HttpCheckTests(unittest.TestCase):
    def test_classifies_only_confirmed_missing_as_dead(self) -> None:
        self.assertEqual(classify_status(200), "live")
        self.assertEqual(classify_status(301), "live")
        self.assertEqual(classify_status(404), "dead")
        self.assertEqual(classify_status(410), "dead")
        self.assertEqual(classify_status(403), "uncertain")
        self.assertEqual(classify_status(429), "uncertain")
        self.assertEqual(classify_status(503), "uncertain")

    def test_head_404_requires_get_confirmation(self) -> None:
        opener = FakeOpener({
            "HEAD": [HttpResponse(404, "https://thaythuoccuaban.com/a.html")],
            "GET": [HttpResponse(200, "https://thaythuoccuaban.com/a.html")],
        })
        result = check_url("https://thaythuoccuaban.com/a.html", opener=opener)
        self.assertEqual(result.classification, "live")
        self.assertEqual(opener.calls, [
            ("HEAD", "https://thaythuoccuaban.com/a.html"),
            ("GET", "https://thaythuoccuaban.com/a.html"),
        ])

    def test_get_404_is_dead(self) -> None:
        opener = FakeOpener({
            "HEAD": [HttpResponse(404, "https://thaythuoccuaban.com/a.html")],
            "GET": [HttpResponse(404, "https://thaythuoccuaban.com/a.html")],
        })
        result = check_url("https://thaythuoccuaban.com/a.html", opener=opener)
        self.assertEqual(result.status, 404)
        self.assertEqual(result.classification, "dead")

    def test_timeout_is_uncertain(self) -> None:
        opener = FakeOpener({
            "HEAD": [TimeoutError("head timeout")],
            "GET": [TimeoutError("get timeout")],
        })
        result = check_url("https://thaythuoccuaban.com/a.html", opener=opener)
        self.assertIsNone(result.status)
        self.assertEqual(result.classification, "uncertain")
        self.assertIn("get timeout", result.error or "")

    def test_unique_checker_deduplicates_fragments(self) -> None:
        opener = FakeOpener({
            "HEAD": [HttpResponse(200, "https://thaythuoccuaban.com/a.html")],
        })
        results = check_unique_urls(
            [
                "https://thaythuoccuaban.com/a.html#one",
                "https://thaythuoccuaban.com/a.html#two",
                "https://thaythuoccuaban.com/a.html#one",
            ],
            opener=opener,
            workers=2,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(Counter(opener.calls), Counter({
            ("HEAD", "https://thaythuoccuaban.com/a.html"): 1,
        }))


class TransformTests(unittest.TestCase):
    def result(self, classification: str, status: int | None = 200):
        url = "https://thaythuoccuaban.com/vithuoc/a.html"
        return {
            url: __import__(
                "tools.normalize_vithuoc_links", fromlist=["CheckResult"]
            ).CheckResult(url, status, url, classification)
        }

    def test_rewrites_live_href_without_reformatting_document(self) -> None:
        source = (
            '<p><a class="x" '
            'href="https://amp.thaythuoccuaban.com/vithuoc/a.htm">A</a></p>'
        )
        expected = (
            '<p><a class="x" '
            'href="https://thaythuoccuaban.com/vithuoc/a.html">A</a></p>'
        )
        transformed = transform_document(source, self.result("live"))
        self.assertEqual(transformed.text, expected)
        self.assertEqual(transformed.normalized_count, 1)
        self.assertEqual(transformed.unwrapped_count, 0)

    def test_unwraps_dead_anchor_but_keeps_children(self) -> None:
        source = (
            '<p><a href="https://amp.thaythuoccuaban.com/vithuoc/a.htm">'
            '<strong>A</strong><img src="a.jpg"></a></p>'
        )
        transformed = transform_document(source, self.result("dead", 404))
        self.assertEqual(
            transformed.text,
            '<p><strong>A</strong><img src="a.jpg"></p>',
        )
        self.assertEqual(transformed.unwrapped_count, 1)

    def test_keeps_uncertain_anchor_and_normalizes_its_href(self) -> None:
        source = (
            "<a href='https://amp.thaythuoccuaban.com/vithuoc/a.HTM?x=1#d'>A</a>"
        )
        url = "https://thaythuoccuaban.com/vithuoc/a.html?x=1#d"
        request_url = "https://thaythuoccuaban.com/vithuoc/a.html?x=1"
        results = {
            request_url: __import__(
                "tools.normalize_vithuoc_links", fromlist=["CheckResult"]
            ).CheckResult(request_url, 429, request_url, "uncertain")
        }
        transformed = transform_document(source, results)
        self.assertIn(f"href='{url}'", transformed.text)
        self.assertIn(">A</a>", transformed.text)

    def test_second_transform_is_idempotent(self) -> None:
        source = '<a href="https://amp.thaythuoccuaban.com/vithuoc/a.htm">A</a>'
        first = transform_document(source, self.result("live"))
        second = transform_document(first.text, self.result("live"))
        self.assertEqual(second.text, first.text)
        self.assertEqual(second.normalized_count, 0)

    def test_normalizes_live_canonical_href(self) -> None:
        source = (
            '<link rel="canonical" '
            'href="https://amp.thaythuoccuaban.com/vithuoc/a.htm">'
        )
        transformed = transform_document(source, self.result("live"))
        self.assertEqual(
            transformed.text,
            '<link rel="canonical" '
            'href="https://thaythuoccuaban.com/vithuoc/a.html">',
        )

    def test_removes_dead_canonical_tag(self) -> None:
        source = (
            '<head><link rel="canonical" '
            'href="https://amp.thaythuoccuaban.com/vithuoc/a.htm"></head>'
        )
        transformed = transform_document(source, self.result("dead", 404))
        self.assertEqual(transformed.text, "<head></head>")


class CliTests(unittest.TestCase):
    def test_dry_run_checks_unique_url_and_writes_deterministic_report(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "a.html"
            second = root / "sub" / "b.htm"
            second.parent.mkdir()
            source = '<a href="https://amp.thaythuoccuaban.com/vithuoc/a.htm">A</a>'
            first.write_text(source, encoding="utf-8")
            second.write_text(source, encoding="utf-8")
            report = root / "reports" / "audit.json"
            calls = []

            def checker(urls, **_kwargs):
                calls.append(list(urls))
                url = "https://thaythuoccuaban.com/vithuoc/a.html"
                return {url: CheckResult(url, 200, url, "live")}

            summary = audit_project(
                root,
                write=False,
                report_path=report,
                checker=checker,
            )

            self.assertEqual(calls, [[
                "https://thaythuoccuaban.com/vithuoc/a.html",
                "https://thaythuoccuaban.com/vithuoc/a.html",
            ]])
            self.assertEqual(first.read_text(encoding="utf-8"), source)
            self.assertEqual(second.read_text(encoding="utf-8"), source)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["unique_request_urls"], 1)
            self.assertEqual(payload["links"][0]["references"], ["a.html", "sub/b.htm"])
            self.assertEqual(summary["changed_files"], 2)

    def test_write_applies_dead_and_live_results_after_checking(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            page = root / "page.html"
            page.write_text(
                '<a href="https://amp.thaythuoccuaban.com/vithuoc/live.htm">Live</a>'
                '<a href="https://amp.thaythuoccuaban.com/vithuoc/dead.htm"><b>Dead</b></a>',
                encoding="utf-8",
            )

            def checker(urls, **_kwargs):
                live = "https://thaythuoccuaban.com/vithuoc/live.html"
                dead = "https://thaythuoccuaban.com/vithuoc/dead.html"
                self.assertEqual(set(urls), {live, dead})
                return {
                    live: CheckResult(live, 200, live, "live"),
                    dead: CheckResult(dead, 404, dead, "dead"),
                }

            audit_project(
                root,
                write=True,
                report_path=root / "audit.json",
                checker=checker,
            )
            self.assertEqual(
                page.read_text(encoding="utf-8"),
                '<a href="https://thaythuoccuaban.com/vithuoc/live.html">Live</a><b>Dead</b>',
            )

    def test_second_write_is_idempotent(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            page = root / "page.html"
            page.write_text(
                '<a href="https://thaythuoccuaban.com/vithuoc/a.html">A</a>',
                encoding="utf-8",
            )
            url = "https://thaythuoccuaban.com/vithuoc/a.html"

            def checker(_urls, **_kwargs):
                return {url: CheckResult(url, 200, url, "live")}

            summary = audit_project(
                root,
                write=True,
                report_path=root / "audit.json",
                checker=checker,
            )
            self.assertEqual(summary["changed_files"], 0)


if __name__ == "__main__":
    unittest.main()
