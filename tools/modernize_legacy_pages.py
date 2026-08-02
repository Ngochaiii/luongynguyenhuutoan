#!/usr/bin/env python3
"""Rebuild legacy table-layout pages with the shared herbal Bootstrap shell."""

from __future__ import annotations

import argparse
import copy
import html as html_std
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

from lxml import etree, html


ROOT = Path(__file__).resolve().parents[1]
MARKUP_SUFFIXES = {".html", ".htm", ".asp"}
ADS_PATTERN = re.compile(
    r"googletagmanager\.com|googleadservices\.com|google_conversion|"
    r"goog_report_conversion|\bgtag\s*\(|\bdataLayer\b|GTM-[A-Z0-9]+|AW-[0-9]+",
    re.I,
)
UTILITY_FILES = {
    "404.html",
    "502.html",
    "Menu.html",
    "danhmuc.html",
    "google474d2dcb64985d4f.html",
    "google89debc3c93de0cda.html",
    "thong-tac-voi-trung.html",
}
PRESENTATION_ATTRIBUTES = {
    "align",
    "valign",
    "bgcolor",
    "border",
    "cellpadding",
    "cellspacing",
    "color",
    "face",
    "style",
}


def serialize(node: etree._Element) -> str:
    return etree.tostring(node, encoding="unicode", method="html", with_tail=False)


def text_length(node: etree._Element) -> int:
    return len(" ".join(node.text_content().split()))


def parse_document(raw: bytes) -> etree._Element:
    parser = html.HTMLParser(recover=True, remove_comments=False)
    return html.document_fromstring(raw, parser=parser)


def is_legacy_page(path: Path, raw: bytes, doc: etree._Element) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    if relative in UTILITY_FILES:
        return False
    if b"bootstrap" in raw.lower():
        return False
    return bool(doc.xpath("//*[@id='khung'] | //*[@id='6']"))


def choose_content(doc: etree._Element) -> tuple[etree._Element | None, str]:
    for element_id, mode in (("6", "id-6"), ("noidung", "noidung")):
        matches = doc.xpath(f"//*[@id='{element_id}']")
        if matches and text_length(matches[0]) >= 80:
            return matches[0], mode

    khung = doc.xpath("//*[@id='khung']")
    if not khung:
        return None, "missing-khung"

    root = khung[0]
    candidates = []
    for node in root.xpath(".//*[self::main or self::article or self::section or self::div or self::td]"):
        if node.get("id") in {"left", "bottom", "menu", "search"}:
            continue
        length = text_length(node)
        headings = len(node.xpath(".//h1 | .//h2 | .//h3"))
        images = len(node.xpath(".//img | .//amp-img"))
        if length >= 120 and (headings or images):
            candidates.append((length + headings * 180 + images * 35, length, node))

    if not candidates:
        return root, "khung"
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2], "scored"


def unwrap(element: etree._Element) -> None:
    parent = element.getparent()
    if parent is None:
        return
    index = parent.index(element)
    if element.text:
        if index == 0:
            parent.text = (parent.text or "") + element.text
        else:
            previous = parent[index - 1]
            previous.tail = (previous.tail or "") + element.text
    for child in list(element):
        element.remove(child)
        parent.insert(index, child)
        index += 1
    if element.tail:
        if index == 0:
            parent.text = (parent.text or "") + element.tail
        else:
            previous = parent[index - 1]
            previous.tail = (previous.tail or "") + element.tail
    parent.remove(element)


def clean_content(source: etree._Element) -> tuple[etree._Element, int, int]:
    content = copy.deepcopy(source)

    for node in list(content.xpath(".//script | .//style | .//form | .//noscript")):
        parent = node.getparent()
        if parent is not None:
            parent.remove(node)

    for node in list(content.xpath(".//*[contains(@class, 'livechat_button')]")):
        parent = node.getparent()
        if parent is not None:
            parent.remove(node)

    for node in list(content.iter()):
        if isinstance(node.tag, str) and node.tag.lower() in {"fb:like", "g:plusone", "gcse:search"}:
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)

    for node in list(content.xpath(".//*[@id='left' or @id='bottom' or @id='chiase' or @id='menu' or @id='search' or @id='dautrang']")):
        parent = node.getparent()
        if parent is not None:
            parent.remove(node)

    for node in list(content.xpath(".//iframe")):
        src = (node.get("src") or "").lower()
        if any(fragment in src for fragment in ("menu.html", "danhmuc.html", "dautrang.html", "link.html")):
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)

    before = text_length(content)

    # Some old AMP pages close <amp-img> with malformed tags such as
    # </amp-amp>. The recovery parser then nests the rest of the article inside
    # that image element. Promote any such children before turning it into the
    # void HTML <img> element, otherwise serialization would drop them.
    for node in list(content.xpath(".//amp-img")):
        parent = node.getparent()
        if parent is not None and (node.text or len(node)):
            old_tail = node.tail or ""
            node.tail = node.text or ""
            node.text = None
            index = parent.index(node) + 1
            moved = []
            for child in list(node):
                node.remove(child)
                parent.insert(index, child)
                moved.append(child)
                index += 1
            if moved:
                moved[-1].tail = (moved[-1].tail or "") + old_tail
            else:
                node.tail = (node.tail or "") + old_tail

    for node in content.iter():
        if not isinstance(node.tag, str):
            continue
        if node.tag.lower() == "amp-img":
            node.tag = "img"
        if node.tag.lower() == "img" and not node.get("src") and node.get("data-src"):
            node.set("src", node.get("data-src"))
        for attribute in list(node.attrib):
            if attribute.lower() in PRESENTATION_ATTRIBUTES:
                del node.attrib[attribute]
        element_id = node.get("id")
        if element_id and (element_id.isdigit() or element_id in {"khung", "noidung"}):
            del node.attrib["id"]
        if "class" in node.attrib:
            del node.attrib["class"]

    for node in list(content.xpath(".//font | .//center | .//span")):
        unwrap(node)

    for node in list(content.iter()):
        if isinstance(node.tag, str) and node.tag.lower() in {"o:p", "select", "option"}:
            unwrap(node)

    for node in list(content.xpath(".//tr[not(ancestor::table)]")):
        unwrap(node)

    first_h1 = content.xpath(".//h1")
    if first_h1:
        heading = first_h1[0]
        heading_length = text_length(heading)
        if before - heading_length >= 80:
            parent = heading.getparent()
            if parent is not None:
                parent.remove(heading)

    for table in list(content.xpath(".//table")):
        if text_length(table) == 0 and not table.xpath(".//img | .//iframe | .//video"):
            parent = table.getparent()
            if parent is not None:
                parent.remove(table)
            continue
        table.set("class", "table table-bordered align-middle")
        parent = table.getparent()
        if parent is None or parent.get("class") == "herbal-table-wrap":
            continue
        wrapper = etree.Element("div", {"class": "herbal-table-wrap"})
        index = parent.index(table)
        parent.remove(table)
        wrapper.append(table)
        parent.insert(index, wrapper)

    after = text_length(content)
    return content, before, after


def extract_title(doc: etree._Element, content: etree._Element, path: Path) -> str:
    headings = content.xpath(".//h1")
    if headings:
        title = " ".join(headings[0].text_content().split())
        if title:
            return title
    titles = doc.xpath("//title")
    if titles:
        title = " ".join(titles[0].text_content().split())
        if title:
            return title
    return path.stem.replace("-", " ").strip().title()


def preserved_head_markup(doc: etree._Element) -> tuple[str, int]:
    parts = []
    seen = set()

    for node in doc.xpath("//head/title | //head/meta"):
        if node.tag.lower() == "meta" and (node.get("name") or "").lower() == "viewport":
            continue
        markup = serialize(node)
        if markup not in seen:
            seen.add(markup)
            parts.append(markup)

    for node in doc.xpath("//head/link"):
        rel = " ".join(node.get("rel", "").lower().split())
        if any(value in rel for value in ("canonical", "icon")):
            markup = serialize(node)
            if markup not in seen:
                seen.add(markup)
                parts.append(markup)

    ads_nodes = 0
    for node in doc.xpath("//script"):
        node_type = (node.get("type") or "").lower()
        markup = serialize(node)
        if node_type == "application/ld+json" or ADS_PATTERN.search(markup):
            # Keep every original tracking/structured-data node, including
            # intentional duplicates. Ad campaigns can depend on their exact
            # placement and count, so these must not be metadata-deduplicated.
            parts.append(markup)
            if ADS_PATTERN.search(markup):
                ads_nodes += 1

    return "\n".join(parts), ads_nodes


def preserved_gtm_noscript(doc: etree._Element) -> str:
    parts = []
    for node in doc.xpath("//noscript"):
        markup = serialize(node)
        if "googletagmanager.com" in markup:
            parts.append(markup)
    return "\n".join(parts)


def inner_markup(node: etree._Element) -> str:
    pieces = []
    if node.text and node.text.strip():
        pieces.append(html_std.escape(node.text))
    for child in node:
        pieces.append(serialize(child))
        # lxml stores text following a child element in child.tail. Serializing
        # with_tail=False is needed to avoid accidental duplication elsewhere,
        # so explicitly retain that article text here.
        if child.tail and child.tail.strip():
            pieces.append(html_std.escape(child.tail))
    return "\n".join(pieces)


def build_page(
    doc: etree._Element,
    path: Path,
    content: etree._Element,
    title: str,
) -> tuple[str, int]:
    metadata, ads_nodes = preserved_head_markup(doc)
    gtm_noscript = preserved_gtm_noscript(doc)
    article = inner_markup(content)
    category = "Thư viện dược liệu" if "vithuoc" in path.parts else "Kiến thức sức khỏe"
    safe_title = html_std.escape(title)

    page = f'''<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  {metadata}
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <link href="/assets/vendor/bootstrap/css/bootstrap.min.css" rel="stylesheet">
  <link href="/assets/vendor/bootstrap-icons/bootstrap-icons.css" rel="stylesheet">
  <link href="/assets/css/herbal-modern.css" rel="stylesheet">
</head>
<body class="herbal-site">
  {gtm_noscript}
  <div class="herbal-topbar">
    <div class="container d-flex justify-content-between align-items-center gap-3">
      <span class="topbar-address"><i class="bi bi-geo-alt me-1"></i>Số 481 lô 22 Lê Hồng Phong, Phường Gia Viên, Thành phố Hải Phòng</span>
      <a href="tel:18006834" onclick="return typeof gtag_report_conversion === 'function' ? gtag_report_conversion('tel:18006834') : true"><i class="bi bi-telephone-fill me-1"></i>Tư vấn: 1800 6834</a>
    </div>
  </div>

  <nav class="navbar navbar-expand-lg herbal-navbar sticky-top" aria-label="Điều hướng chính">
    <div class="container">
      <a class="navbar-brand herbal-brand" href="/">
        <span class="herbal-brand-mark" aria-hidden="true"><i class="bi bi-flower1"></i></span>
        <span class="herbal-brand-text">
          <strong>Đông y Nguyễn Hữu Toàn</strong>
          <span>Gia truyền 15 đời</span>
        </span>
      </a>
      <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#herbalNav" aria-controls="herbalNav" aria-expanded="false" aria-label="Mở menu">
        <span class="navbar-toggler-icon"></span>
      </button>
      <div class="collapse navbar-collapse" id="herbalNav">
        <ul class="navbar-nav ms-auto align-items-lg-center">
          <li class="nav-item"><a class="nav-link" href="/">Trang chủ</a></li>
          <li class="nav-item"><a class="nav-link" href="/phong-kham-dong-y-nguyen-huu-toan-hinh-thanh-va-phat-trien.html">Phòng khám</a></li>
          <li class="nav-item"><a class="nav-link" href="/vithuoc/">Dược liệu</a></li>
          <li class="nav-item"><a class="nav-link" href="/danhmuc.html">Bài thuốc</a></li>
          <li class="nav-item ms-lg-2"><a class="herbal-hotline" href="tel:18006834"><i class="bi bi-telephone-fill"></i>1800 6834</a></li>
        </ul>
      </div>
    </div>
  </nav>

  <header class="herbal-hero">
    <div class="container">
      <span class="herbal-kicker"><i class="bi bi-leaf"></i>{html_std.escape(category)}</span>
      <h1>{safe_title}</h1>
      <nav class="herbal-breadcrumb" aria-label="Breadcrumb">
        <a href="/">Trang chủ</a><i class="bi bi-chevron-right" aria-hidden="true"></i><span>{safe_title}</span>
      </nav>
    </div>
  </header>

  <main class="herbal-main">
    <div class="container">
      <div class="row g-4 align-items-start">
        <div class="col-lg-8">
          <article class="herbal-article">
            {article}
          </article>
        </div>
        <aside class="col-lg-4">
          <div class="herbal-sidebar">
            <div class="herbal-form-card">
              <h2>Tôi muốn được tư vấn</h2>
              <p class="form-intro">Để lại thông tin, phòng khám sẽ liên hệ và hỗ trợ anh/chị sớm nhất.</p>
              <form id="contacts-form" class="form-card" novalidate>
                <div class="mb-3">
                  <label class="form-label" for="fname">Họ và tên <span class="text-danger">*</span></label>
                  <input class="form-control" type="text" id="fname" name="fname" minlength="2" placeholder="Nhập họ tên" autocomplete="name" required>
                </div>
                <div class="mb-3">
                  <label class="form-label" for="contact-phone">Số điện thoại <span class="text-danger">*</span></label>
                  <input class="form-control" type="tel" id="contact-phone" name="phone" maxlength="11" placeholder="Ví dụ: 0912345678" autocomplete="tel" inputmode="tel" required>
                </div>
                <div class="mb-3">
                  <label class="form-label" for="Email">Email</label>
                  <input class="form-control" type="email" id="Email" name="Email" placeholder="Không bắt buộc" autocomplete="email">
                </div>
                <div class="mb-3">
                  <label class="form-label" for="ans">Vấn đề cần tư vấn</label>
                  <textarea class="form-control" id="ans" name="ans" rows="4" placeholder="Mô tả ngắn tình trạng của anh/chị"></textarea>
                </div>
                <input type="hidden" name="traffic_source">
                <input type="hidden" name="user_platform">
                <button class="btn herbal-submit" type="submit"><i class="bi bi-send me-2"></i>Gửi cho bác sĩ</button>
                <p class="herbal-privacy"><i class="bi bi-shield-check"></i>Thông tin chỉ được dùng để liên hệ tư vấn sức khỏe.</p>
              </form>
            </div>
            <div class="herbal-info-card">
              <strong><i class="bi bi-clock me-2"></i>Thời gian làm việc</strong>
              <p>Thứ Hai – Chủ Nhật: 7:30–18:00</p>
              <p><a href="tel:18006834">Hotline miễn cước: 1800 6834</a></p>
            </div>
          </div>
        </aside>
      </div>
    </div>
  </main>

  <footer class="herbal-footer">
    <div class="container">
      <div class="row g-4">
        <div class="col-lg-7">
          <h2>Phòng khám Đông y Nguyễn Hữu Toàn</h2>
          <p>Địa chỉ: Số 481 lô 22 Lê Hồng Phong, Phường Gia Viên, Thành phố Hải Phòng.</p>
          <p>Thông tin trên website có tính chất tham khảo, không thay thế chẩn đoán và chỉ định của người hành nghề y.</p>
        </div>
        <div class="col-lg-5 text-lg-end">
          <p><strong>Hotline: <a href="tel:18006834">1800 6834</a></strong></p>
          <p>Giấy phép: 197GCN HNY SYTH</p>
        </div>
      </div>
    </div>
  </footer>

  <div class="herbal-floating-actions" aria-label="Liên hệ nhanh">
    <a href="tel:18006834" aria-label="Gọi hotline"><i class="bi bi-telephone-fill"></i></a>
    <a href="https://zalo.me/0943954889" aria-label="Liên hệ Zalo"><span class="fw-bold">Zalo</span></a>
  </div>

  <script src="/assets/vendor/bootstrap/js/bootstrap.bundle.min.js"></script>
  <script src="/assets/assets/js/submit-data.js"></script>
</body>
</html>
'''
    # Legacy article fragments often contain spaces after their final visible
    # character. Remove only end-of-line whitespace; content stays unchanged.
    page = re.sub(r"[ \t]+(?=\n)", "", page)
    page = re.sub(r" +\t", "\t", page)
    return page, ads_nodes


def find_targets() -> list[Path]:
    targets = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in MARKUP_SUFFIXES:
            continue
        if ".git" in path.parts:
            continue
        raw = path.read_bytes()
        try:
            doc = parse_document(raw)
        except (etree.ParserError, ValueError):
            continue
        if is_legacy_page(path, raw, doc):
            targets.append(path)
    return sorted(targets)


def find_modernized_targets() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.suffix.lower() in MARKUP_SUFFIXES
        and b"herbal-modern.css" in path.read_bytes()
    )


def read_head_version(path: Path) -> bytes:
    relative = path.relative_to(ROOT).as_posix()
    return subprocess.run(
        ["git", "show", f"HEAD:{relative}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Write converted pages")
    parser.add_argument(
        "--rebuild-modern",
        action="store_true",
        help="Rebuild already-modernized pages from their original HEAD versions",
    )
    parser.add_argument("--limit", type=int, default=0, help="Limit pages for testing")
    parser.add_argument("--file", action="append", default=[], help="Convert only this relative path")
    args = parser.parse_args()

    if args.file:
        targets = [ROOT / value for value in args.file]
    elif args.rebuild_modern:
        targets = find_modernized_targets()
    else:
        targets = find_targets()
    if args.limit:
        targets = targets[: args.limit]

    modes = Counter()
    converted = 0
    skipped = []
    ad_nodes = 0
    minimum_ratio = 1.0

    for path in targets:
        raw = read_head_version(path) if args.rebuild_modern else path.read_bytes()
        try:
            doc = parse_document(raw)
        except (etree.ParserError, ValueError) as error:
            skipped.append((path, f"parse: {error}"))
            continue

        source, mode = choose_content(doc)
        modes[mode] += 1
        if source is None:
            skipped.append((path, mode))
            continue

        title = extract_title(doc, source, path)
        cleaned, before, after = clean_content(source)
        ratio = after / before if before else 0
        minimum_ratio = min(minimum_ratio, ratio)
        if before < 1 or ratio < 0.88:
            skipped.append((path, f"content ratio {ratio:.3f} ({after}/{before})"))
            continue

        page, page_ads = build_page(doc, path, cleaned, title)
        ad_nodes += page_ads
        if args.write:
            path.write_text(page, encoding="utf-8", newline="\n")
        converted += 1

    print(f"targets={len(targets)}")
    print(f"converted={converted}")
    print(f"skipped={len(skipped)}")
    print(f"minimum_content_ratio={minimum_ratio:.3f}")
    print(f"preserved_ads_nodes={ad_nodes}")
    print("modes=" + ",".join(f"{key}:{value}" for key, value in sorted(modes.items())))
    for path, reason in skipped[:100]:
        print(f"SKIP {path.relative_to(ROOT)} | {reason}")
    return 1 if skipped else 0


if __name__ == "__main__":
    sys.exit(main())
