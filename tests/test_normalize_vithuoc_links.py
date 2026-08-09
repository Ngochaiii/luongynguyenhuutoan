from __future__ import annotations

import unittest

from tools.normalize_vithuoc_links import find_anchor_links, normalize_url


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


if __name__ == "__main__":
    unittest.main()
