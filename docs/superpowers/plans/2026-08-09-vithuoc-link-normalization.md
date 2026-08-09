# Vithuoc Link Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chuẩn hóa liên kết vị thuốc sang domain chính và đuôi `.html`, kiểm tra mỗi URL duy nhất, rồi chỉ tháo liên kết khi đích được xác nhận trả về 404/410.

**Architecture:** Một công cụ Python độc lập tách riêng ba trách nhiệm: chuẩn hóa URL, kiểm tra HTTP có cache theo URL duy nhất, và sửa tối thiểu thuộc tính `href`/thẻ `<a>` trong source. Công cụ chạy hai pha audit rồi apply để không ghi file trước khi việc kiểm tra hoàn tất, đồng thời xuất báo cáo JSON phục vụ kiểm chứng.

**Tech Stack:** Python 3 standard library (`urllib.parse`, `urllib.request`, `concurrent.futures`, `json`, `unittest`), HTML/HTM/ASP tĩnh.

## Global Constraints

- Chỉ xử lý `href` trên host `amp.thaythuoccuaban.com` hoặc `thaythuoccuaban.com`.
- Chuẩn hóa thành HTTPS, host `thaythuoccuaban.com`, và chỉ đổi hậu tố path `.htm` thành `.html`.
- Giữ nguyên query string, fragment và nội dung hiển thị.
- Chỉ tháo thẻ `<a>` khi GET xác nhận HTTP 404 hoặc 410.
- Không xóa liên kết do 403, 405, 408, 429, 5xx, DNS, TLS hoặc timeout.
- Không sửa Google Ads, Google Analytics, JSON-LD hoặc domain ngoài phạm vi.
- Chạy kiểm tra theo URL duy nhất và tái sử dụng kết quả cho mọi nơi tham chiếu.

---

### Task 1: URL normalization and link discovery

**Files:**
- Create: `tools/normalize_vithuoc_links.py`
- Create: `tests/test_normalize_vithuoc_links.py`

**Interfaces:**
- Produces: `normalize_url(url: str) -> str | None`
- Produces: `find_anchor_links(text: str) -> list[LinkReference]`
- Produces: immutable `LinkReference(original_url, normalized_url, start, end)`

- [ ] **Step 1: Write failing normalization tests**

```python
class NormalizeUrlTests(unittest.TestCase):
    def test_removes_amp_host_and_changes_htm_suffix(self):
        self.assertEqual(
            normalize_url("https://amp.thaythuoccuaban.com/vithuoc/thuocban.htm"),
            "https://thaythuoccuaban.com/vithuoc/thuocban.html",
        )

    def test_preserves_query_and_fragment(self):
        self.assertEqual(
            normalize_url("http://amp.thaythuoccuaban.com/vithuoc/a.htm?x=.htm#toa"),
            "https://thaythuoccuaban.com/vithuoc/a.html?x=.htm#toa",
        )

    def test_ignores_other_domains(self):
        self.assertIsNone(normalize_url("https://example.com/a.htm"))
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python3 -m unittest tests.test_normalize_vithuoc_links.NormalizeUrlTests -v
```

Expected: import failure because `tools.normalize_vithuoc_links` does not exist.

- [ ] **Step 3: Implement minimal URL normalizer and anchor discovery**

Implement URL parsing with `urlsplit`/`urlunsplit`; lowercase only the host comparison, preserve query/fragment, and use an `<a ... href=...>` matcher that records exact source spans instead of serializing the document.

```python
TARGET_HOSTS = {"amp.thaythuoccuaban.com", "thaythuoccuaban.com"}

def normalize_url(url: str) -> str | None:
    parsed = urlsplit(html.unescape(url.strip()))
    if (parsed.hostname or "").lower() not in TARGET_HOSTS:
        return None
    path = re.sub(r"(?i)\.htm$", ".html", parsed.path)
    return urlunsplit(("https", "thaythuoccuaban.com", path, parsed.query, parsed.fragment))
```

- [ ] **Step 4: Add discovery tests and verify GREEN**

Test double-quoted and single-quoted `href`, multiple links, and ignoring non-anchor `href`. Run:

```bash
python3 -m unittest tests.test_normalize_vithuoc_links -v
```

Expected: all Task 1 tests pass.

- [ ] **Step 5: Commit Task 1**

```bash
git add tools/normalize_vithuoc_links.py tests/test_normalize_vithuoc_links.py
git commit -m "feat: discover and normalize vithuoc links"
```

---

### Task 2: HTTP verification and status classification

**Files:**
- Modify: `tools/normalize_vithuoc_links.py`
- Modify: `tests/test_normalize_vithuoc_links.py`

**Interfaces:**
- Produces: `CheckResult(request_url, status, final_url, classification, error)`
- Produces: `check_url(url: str, opener: Callable) -> CheckResult`
- Produces: `check_unique_urls(urls: Iterable[str], workers: int) -> dict[str, CheckResult]`

- [ ] **Step 1: Write failing classification tests**

Use an injected fake opener returning real response-shaped objects. Cover:

```python
self.assertEqual(classify_status(200), "live")
self.assertEqual(classify_status(301), "live")
self.assertEqual(classify_status(404), "dead")
self.assertEqual(classify_status(410), "dead")
self.assertEqual(classify_status(403), "uncertain")
self.assertEqual(classify_status(429), "uncertain")
self.assertEqual(classify_status(503), "uncertain")
```

- [ ] **Step 2: Run targeted tests and verify RED**

```bash
python3 -m unittest tests.test_normalize_vithuoc_links.HttpCheckTests -v
```

Expected: failure because HTTP checking functions are missing.

- [ ] **Step 3: Implement minimal checker**

- Try HEAD first.
- Accept 200–399 immediately.
- For every non-live HEAD response or HEAD transport error, issue GET with `Range: bytes=0-0`.
- Classify only GET 404/410 as `dead`.
- Record transport errors as `uncertain`.
- Strip fragments for the request/cache key while retaining the normalized source URL in references.
- Use `ThreadPoolExecutor(max_workers=8)` and one future per unique request URL.

- [ ] **Step 4: Verify GET confirmation and de-duplication**

Add tests proving HEAD 404 followed by GET 200 is live, HEAD 404 followed by GET 404 is dead, timeout is uncertain, and duplicate URLs call the opener once. Run:

```bash
python3 -m unittest tests.test_normalize_vithuoc_links.HttpCheckTests -v
```

Expected: all HTTP tests pass.

- [ ] **Step 5: Commit Task 2**

```bash
git add tools/normalize_vithuoc_links.py tests/test_normalize_vithuoc_links.py
git commit -m "feat: verify unique vithuoc URLs"
```

---

### Task 3: Minimal source transformation

**Files:**
- Modify: `tools/normalize_vithuoc_links.py`
- Modify: `tests/test_normalize_vithuoc_links.py`

**Interfaces:**
- Produces: `transform_document(text: str, results: Mapping[str, CheckResult]) -> TransformResult`
- `TransformResult` contains `text`, `normalized_count`, and `unwrapped_count`.

- [ ] **Step 1: Write failing transform tests**

```python
def test_rewrites_live_href_without_reformatting_document(self):
    source = '<p><a class="x" href="https://amp.thaythuoccuaban.com/vithuoc/a.htm">A</a></p>'
    expected = '<p><a class="x" href="https://thaythuoccuaban.com/vithuoc/a.html">A</a></p>'
    self.assertEqual(transform_document(source, live_results).text, expected)

def test_unwraps_dead_anchor_but_keeps_children(self):
    source = '<p><a href="https://amp.thaythuoccuaban.com/vithuoc/a.htm"><strong>A</strong><img src="a.jpg"></a></p>'
    self.assertEqual(
        transform_document(source, dead_results).text,
        '<p><strong>A</strong><img src="a.jpg"></p>',
    )
```

- [ ] **Step 2: Run transform tests and verify RED**

```bash
python3 -m unittest tests.test_normalize_vithuoc_links.TransformTests -v
```

Expected: failure because `transform_document` is missing.

- [ ] **Step 3: Implement transform from right to left**

Collect exact anchor spans, then apply replacements in descending source-offset order. For `live` and `uncertain`, replace only the `href` value. For `dead`, replace the full `<a>...</a>` span with its inner HTML. Preserve all surrounding bytes and whitespace.

- [ ] **Step 4: Add regression cases and verify GREEN**

Cover uppercase `.HTM`, query/fragment, single quotes, multiple anchors, uncertain status retained, and a second transform producing no change. Run:

```bash
python3 -m unittest tests.test_normalize_vithuoc_links -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 3**

```bash
git add tools/normalize_vithuoc_links.py tests/test_normalize_vithuoc_links.py
git commit -m "feat: rewrite and unwrap audited links"
```

---

### Task 4: CLI, audit report, and atomic apply

**Files:**
- Modify: `tools/normalize_vithuoc_links.py`
- Modify: `tests/test_normalize_vithuoc_links.py`
- Create at runtime: `reports/vithuoc-link-audit.json`

**Interfaces:**
- CLI: `python3 tools/normalize_vithuoc_links.py [--write] [--workers 8] [--timeout 15] [--report PATH]`
- Dry-run is default; `--write` applies only after every unique URL has a recorded result.

- [ ] **Step 1: Write failing end-to-end CLI tests**

Use a temporary directory with two documents pointing to the same URL and an injected result cache. Assert one unique audit entry, both references listed, no write in dry-run, write under `--write`, and valid deterministic JSON ordering.

- [ ] **Step 2: Run CLI tests and verify RED**

```bash
python3 -m unittest tests.test_normalize_vithuoc_links.CliTests -v
```

Expected: failure because orchestration/report functions are missing.

- [ ] **Step 3: Implement orchestration and report schema**

Report each request URL as:

```json
{
  "normalized_url": "https://thaythuoccuaban.com/vithuoc/a.html",
  "status": 200,
  "final_url": "https://thaythuoccuaban.com/vithuoc/a.html",
  "classification": "live",
  "error": null,
  "references": ["vithuoc/index.html"]
}
```

Write changed pages only after all checks finish. Write via a temporary sibling file followed by `Path.replace()` for atomicity. Sort report entries and reference paths.

- [ ] **Step 4: Verify CLI tests and complete suite**

```bash
python3 -m unittest tests.test_normalize_vithuoc_links -v
```

Expected: all tests pass with no warnings.

- [ ] **Step 5: Commit Task 4**

```bash
git add tools/normalize_vithuoc_links.py tests/test_normalize_vithuoc_links.py
git commit -m "feat: add auditable vithuoc link migration CLI"
```

---

### Task 5: Production audit, apply, and verification

**Files:**
- Modify: affected `.html`, `.htm`, `.asp` files
- Create: `reports/vithuoc-link-audit.json`

**Interfaces:**
- Consumes the completed CLI from Task 4.
- Produces normalized source files and the final HTTP evidence report.

- [ ] **Step 1: Run dry audit against live website**

```bash
python3 tools/normalize_vithuoc_links.py --workers 8 --timeout 15
```

Expected: report generated; summary shows counts for live, dead, and uncertain unique URLs; source files unchanged.

- [ ] **Step 2: Review uncertain and dead results**

Confirm every dead entry has status 404/410 from GET. Confirm uncertain entries remain scheduled for URL normalization but not anchor removal.

- [ ] **Step 3: Apply audited transformation**

```bash
python3 tools/normalize_vithuoc_links.py --write --workers 8 --timeout 15
```

Expected: affected files updated; every dead URL anchor unwrapped; report refreshed.

- [ ] **Step 4: Run complete verification**

```bash
python3 -m unittest tests.test_normalize_vithuoc_links -v
rg -n -i 'href=["'"'][^"'"']*amp\.thaythuoccuaban\.com' --glob '*.html' --glob '*.htm' --glob '*.asp' .
rg -n -i 'href=["'"']https?://thaythuoccuaban\.com/[^"'"']*\.htm([?#"'"'])' --glob '*.html' --glob '*.htm' --glob '*.asp' .
git diff --check
```

Expected: tests pass; both `rg` commands return no matches; diff check exits 0.

- [ ] **Step 5: Verify idempotence**

```bash
git diff --stat > /tmp/vithuoc-before.stat
python3 tools/normalize_vithuoc_links.py --write --workers 8 --timeout 15
git diff --stat > /tmp/vithuoc-after.stat
diff -u /tmp/vithuoc-before.stat /tmp/vithuoc-after.stat
```

Expected: no diff between before and after stats.

- [ ] **Step 6: Commit production migration**

```bash
git add tools/normalize_vithuoc_links.py tests/test_normalize_vithuoc_links.py reports/vithuoc-link-audit.json '*.html' '*.htm' '*.asp' vithuoc
git commit -m "fix: normalize and audit vithuoc links"
```
