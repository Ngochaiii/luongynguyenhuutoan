# Thiết kế chuẩn hóa liên kết vị thuốc

## Mục tiêu

Chuẩn hóa các liên kết từ website hiện tại sang `https://thaythuoccuaban.com`, loại bỏ subdomain `amp`, đổi đuôi đường dẫn `.htm` thành `.html`, kiểm tra đích HTTP sau khi chuẩn hóa và chỉ gỡ liên kết khi máy chủ xác nhận đích không tồn tại.

## Phạm vi

- Quét toàn bộ file `.html`, `.htm` và `.asp` trong dự án.
- Chỉ xử lý giá trị `href` có host `amp.thaythuoccuaban.com` hoặc `thaythuoccuaban.com`.
- Không đổi tên file cục bộ có đuôi `.htm` và không sửa URL thuộc domain khác.
- Không thay đổi nội dung chữ, hình ảnh, Google Ads, Google Analytics hoặc JSON-LD ngoài giá trị URL thuộc phạm vi.
- Phạm vi khảo sát ban đầu gồm khoảng 2.631 lần xuất hiện trong 1.543 file; số URL duy nhất sẽ được xác định khi chạy kiểm tra chính thức.

## Quy tắc chuẩn hóa

Mỗi URL thuộc phạm vi được xử lý theo thứ tự:

1. Ép giao thức thành `https`.
2. Đổi host `amp.thaythuoccuaban.com` thành `thaythuoccuaban.com`.
3. Nếu phần path kết thúc bằng `.htm`, đổi đúng hậu tố đó thành `.html`.
4. Giữ nguyên path còn lại, query string và fragment.
5. Không thay `.htm` xuất hiện trong query string hoặc nội dung chữ.

Ví dụ:

```text
https://amp.thaythuoccuaban.com/vithuoc/thuocban.htm
→ https://thaythuoccuaban.com/vithuoc/thuocban.html
```

## Kiểm tra HTTP

- Thu thập URL đã chuẩn hóa thành tập URL duy nhất để mỗi đích chỉ được kiểm tra một lần.
- Thực hiện `HEAD` trước; nếu máy chủ không hỗ trợ `HEAD` hoặc kết quả không đủ kết luận thì dùng `GET` giới hạn dữ liệu tải về.
- Theo redirect và đánh giá URL cuối cùng.
- Giới hạn đồng thời và đặt timeout để không gây tải lớn cho website.
- Dùng cùng một kết quả kiểm tra cho mọi lần xuất hiện của cùng URL.

Phân loại kết quả:

- `200–399`: liên kết hợp lệ, giữ URL đã chuẩn hóa.
- `404` hoặc `410`: liên kết chết đã được xác nhận, gỡ khả năng nhấp.
- `403`, `405`, `408`, `429`, `5xx`, lỗi DNS, TLS hoặc timeout: chưa đủ bằng chứng là liên kết chết; giữ URL đã chuẩn hóa và ghi vào báo cáo cần xem lại.

## Xử lý liên kết chết

Khi URL trả về `404` hoặc `410`, chỉ tháo thẻ `<a>` và giữ nguyên toàn bộ nội dung con của thẻ, bao gồm chữ, hình ảnh và định dạng bên trong. Không xóa đoạn văn hoặc hình ảnh khỏi bài viết.

Ví dụ:

```html
<a href="https://thaythuoccuaban.com/vithuoc/khong-ton-tai.html"><strong>Tên vị thuốc</strong></a>
```

trở thành:

```html
<strong>Tên vị thuốc</strong>
```

## Công cụ và dữ liệu đầu ra

- Tạo công cụ lặp lại được tại `tools/normalize_vithuoc_links.py`.
- Công cụ có chế độ kiểm tra không ghi file và chế độ áp dụng thay đổi.
- Ghi báo cáo máy đọc được tại `reports/vithuoc-link-audit.json`, gồm URL ban đầu, URL chuẩn hóa, mã HTTP, URL cuối sau redirect, trạng thái xử lý và danh sách file tham chiếu.
- Kết quả phải ổn định: chạy lại sau khi hoàn tất không tạo thêm thay đổi.

## An toàn và phục hồi lỗi

- Parse và thay đổi thuộc tính `href` thay vì thay chuỗi `.htm` trên toàn file.
- Không xóa liên kết dựa trên lỗi mạng tạm thời.
- Không ghi file nào nếu quá trình thu thập hoặc kiểm tra URL chưa hoàn tất.
- Ghi file theo UTF-8 với cơ chế bảo toàn byte không hợp lệ để tránh làm hỏng các trang cũ.
- Không triển khai website và không thay đổi nội dung bên ngoài repository.

## Kiểm thử và tiêu chí hoàn tất

- Kiểm thử đơn vị cho chuyển host, chuyển `.htm` thành `.html`, bảo toàn query/fragment và bỏ qua domain ngoài phạm vi.
- Kiểm thử phân loại HTTP, gồm redirect, 404/410, 403/429/5xx và timeout.
- Kiểm thử việc tháo thẻ `<a>` nhưng giữ nguyên nội dung con.
- Sau khi áp dụng, không còn `href` trỏ tới `amp.thaythuoccuaban.com`.
- Sau khi áp dụng, không còn path `.htm` trên các `href` thuộc `thaythuoccuaban.com`.
- Mọi URL bị tháo liên kết phải có bằng chứng `404` hoặc `410` trong báo cáo.
- Mọi URL không xác định do lỗi mạng phải được giữ và xuất hiện trong báo cáo.
- Chạy kiểm tra cấu trúc HTML và `git diff --check` sau khi sửa.
