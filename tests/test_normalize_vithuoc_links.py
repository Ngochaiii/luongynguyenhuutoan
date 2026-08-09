from __future__ import annotations

import unittest
from collections import Counter

from tools.normalize_vithuoc_links import (
    HttpResponse,
    check_unique_urls,
    check_url,
    classify_status,
    find_anchor_links,
    normalize_url,
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


if __name__ == "__main__":
    unittest.main()
