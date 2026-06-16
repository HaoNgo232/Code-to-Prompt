# Hướng Dẫn Sử Dụng Tính Năng Bản Quyền (Licensing Guide)

Tài liệu này hướng dẫn bạn cách khởi chạy, tạo mã kích hoạt (License Key) và kích hoạt/hủy kích hoạt bản quyền cho ứng dụng **Synapse Desktop**.

---

## Bước 1: Chạy ứng dụng (Bật/Tắt check bản quyền)

Ứng dụng **mặc định luôn yêu cầu và kiểm tra bản quyền** khi khởi chạy. Tuy nhiên, để thuận tiện cho việc phát triển, ta sử dụng tham số `--no-license` để tắt tính năng này.

### 1.1 Khởi chạy chế độ phát triển (Dev Mode - Bỏ qua check bản quyền)
Script khởi động dự án đã được tích hợp sẵn tham số `--no-license`:
```bash
./start.sh
```
Hoặc dùng lệnh python trực tiếp:
```bash
PYTHONPATH=. .venv/bin/python main.py --no-license
```
* **Kết quả:** Ứng dụng tự động bỏ qua kiểm tra bản quyền và khởi động trực tiếp vào giao diện chính để bạn phát triển các tính năng khác.

### 1.2 Khởi chạy chế độ kiểm thử bản quyền (Bật check bản quyền)
Để kiểm thử giao diện kích hoạt hoặc luồng xác thực bản quyền, bạn cần chạy ứng dụng mà **không** truyền tham số `--no-license`:
```bash
PYTHONPATH=. .venv/bin/python main.py
```
* **Kết quả:** Cửa sổ chính của ứng dụng sẽ **không** hiện lên ngay. Thay vào đó, hộp thoại **"Activate Synapse Desktop"** sẽ xuất hiện yêu cầu bạn nhập License Key để kích hoạt.

---

## Bước 2: Tạo License Key hợp lệ (Developer Tool)
Mở một cửa sổ terminal mới và chạy lệnh sau để sinh ra một mã kích hoạt dùng thử:

* **Tạo Key có thời hạn 365 ngày (cho email `dev@test.com`):**
  ```bash
  PYTHONPATH=. .venv/bin/python tools/license_generator.py --id LIC-DEV-99 --email dev@test.com --days 365
  ```

* **Tạo Key trọn đời (Lifetime - Mua 1 lần):**
  ```bash
  PYTHONPATH=. .venv/bin/python tools/license_generator.py --id LIC-LIFE-99 --email dev@test.com --lifetime
  ```

* **Kết quả hiển thị trên terminal:**
  ```text
  === GENERATED LICENSE KEY ===
  SYNAPSE-KEY.eyJsaWNlbnNlX2lkIjoiTElDLURFVi05OSIsImVtYWlsIjoiZGV2QHN5bmFwc2UuY29tIiwiZXhwaXJ5X2RhdGUiOiIyMDI3LTA2LTE2IiwicHJvZHVjdCI6IlN5bmFwc2UgRGVza3RvcCJ9._5HUQ2FSsfevsNnZ59c_HEMwYD8sdElU58LLcxkepdwYt8QIVGKYIoNqzPCFC3GJAA6HP7Pe515p_-eZjCF9Dw
  =============================
  ```
  *(Hãy bôi đen và copy toàn bộ chuỗi ký tự bắt đầu bằng `SYNAPSE-KEY.` cho đến hết)*

---

## Bước 3: Kích hoạt ứng dụng
1. Khởi chạy ứng dụng ở chế độ kiểm thử (Bước 1.2).
2. Dán (Paste) chuỗi License Key vừa copy ở Bước 2 vào ô nhập liệu.
3. Nhấp vào nút **Activate**.
4. **Kết quả:** Hộp thoại sẽ đóng lại và cửa sổ chính của Synapse Desktop sẽ xuất hiện!

---

## Bước 4: Kiểm tra và Hủy kích hoạt (Deactivate)
1. Trên giao diện chính của Synapse Desktop, chọn tab **Settings** (biểu tượng bánh răng ở góc dưới).
2. Tại cột thứ 3, bạn sẽ thấy một thẻ mới mang tên **Product Licensing** hiển thị chi tiết thông tin bản quyền của bạn (Mã số bản quyền, Email sở hữu, Ngày hết hạn).
3. Để gỡ bỏ bản quyền (ví dụ khi muốn chuyển sang máy khác):
   - Nhấp vào nút **Deactivate License**.
   - Hộp thoại xác nhận sẽ hiện ra. Chọn **Yes**.
   - **Kết quả:** Ứng dụng sẽ tự động xóa key bản quyền trong file cài đặt và đóng phần mềm. Lần khởi chạy kế tiếp sẽ tiếp tục yêu cầu nhập key bản quyền từ đầu.

---

## Lưu ý kỹ thuật cho Lập trình viên
* **Vị trí lưu Key:** Key bản quyền sau khi kích hoạt thành công được lưu tại file cấu hình hệ thống chuẩn `~/.config/synapse-desktop/settings.json` (dưới trường `"license_key"`). Để phục vụ backward compatibility, ứng dụng cũng hỗ trợ tự động di chuyển key từ đường dẫn cũ `~/.synapse-desktop/settings.json` nếu có.
* **Cơ chế bảo mật:** Thuật toán sử dụng là **Ed25519** (mật mã hóa bất đối xứng). 
  - Khóa công khai (**Public Key**) được nhúng cứng trong file `infrastructure/adapters/license_service.py`.
  - Khóa bí mật (**Private Key**) nằm trong công cụ `tools/license_generator.py` dùng để ký số ra License Key. Khi triển khai thực tế trên môi trường Production, khóa bí mật này phải được cất giữ trên server kích hoạt và không được đóng gói cùng ứng dụng.
* **Cơ chế Feature Flag cho Build Production:**
  - Để đảm bảo tính bảo mật, các bản build đóng gói (AppImage cho Linux, EXE cho Windows) sẽ **luôn thực thi kiểm tra bản quyền** do không truyền tham số `--no-license` theo mặc định.
  - Ta không cần cấu hình thêm bất kỳ biến môi trường (`SYNAPSE_LICENSE_CHECK`) hay runtime hook phức tạp nào khác cho PyInstaller.
