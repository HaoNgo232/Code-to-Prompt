# Thiết kế Nâng cấp Apply Tab với Luồng Auto-Detection

Tài liệu này mô tả chi tiết thiết kế kỹ thuật để nâng cấp tab **Apply** (`ApplyViewQt`) trong codebase Synapse Desktop. Việc nâng cấp này bổ sung luồng tự động phát hiện patch (auto-detection flow) khi người dùng dán hoặc gõ văn bản, cập nhật nhãn tóm tắt (Summary Label) và tự động thay đổi trạng thái kích hoạt của nút **Apply Changes**.

---

## 1. Mục tiêu (Goals)
- Tự động phát hiện xem văn bản trong textarea có chứa patch hợp lệ (OPX hoặc Search/Replace) hay không sau khi trì hoãn (debounce) 800ms kể từ lần gõ/dán cuối cùng.
- Hiển thị nhãn tóm tắt (Summary Label) thân thiện ở giữa textarea và hàng nút chức năng để báo cáo số lượng thay đổi và danh sách các file bị ảnh hưởng.
- Tự động kích hoạt (enable) nút **Apply Changes** khi có ít nhất một patch hợp lệ, và vô hiệu hóa (disable) khi không có patch nào hoặc khi textarea trống.
- Tái sử dụng nút **Paste** hiện tại để đảm bảo giao diện gọn gàng, không bị trùng lặp chức năng.
- Đảm bảo sau khi áp dụng patch thành công, textarea được làm sạch và nhãn tóm tắt hiển thị thông báo thành công mà không bị luồng tự động phát hiện đè mất.
- Đảm bảo không có bất kỳ giao diện (UI) nào bị trùng lặp (ví dụ: chỉ có đúng 1 textarea).

---

## 2. Vị trí File & Cấu trúc Lớp
- **Giao diện sửa đổi**: `presentation/views/apply/apply_view_qt.py`
- **Unit Tests**: `tests/presentation/test_apply_tab_upgrade.py`

---

## 3. Thiết kế Chi tiết (Detailed Design)

### 3.1. Các thay đổi trong `ApplyViewQt`

#### Khởi tạo (Constructor `__init__`)
Chúng ta sẽ thêm các thuộc tính quản lý trạng thái sau:
```python
# Trong ApplyViewQt.__init__
self._apply_btn: Optional[QPushButton] = None  # Quản lý nút Apply Changes
self._summary_label: Optional[QLabel] = None   # Nhãn hiển thị tóm tắt
self._detection_result = None                  # Lưu kết quả detect gần nhất

# Khởi tạo QTimer quản lý debounce 800ms
from PySide6.QtCore import QTimer
self._debounce_timer = QTimer(self)
self._debounce_timer.setSingleShot(True)
self._debounce_timer.timeout.connect(self._on_debounce_timeout)
```

#### Bố cục giao diện (`_build_left_panel`)
Sắp xếp lại layout dọc của bảng điều khiển bên trái để chèn nhãn tóm tắt ngay bên dưới textarea và trên hàng nút:
```python
# Định nghĩa self._summary_label
self._summary_label = QLabel()
self._summary_label.setWordWrap(True)
self._summary_label.setStyleSheet(
    f"font-size: 11px; color: {ThemeColors.TEXT_MUTED}; font-weight: 500; margin-top: 4px; padding-left: 2px;"
)
self._summary_label.hide()  # Ban đầu ẩn đi

# Chèn vào layout sau textarea
layout.addWidget(self._opx_input, stretch=1)
layout.addWidget(self._summary_label)  # <--- Chèn Summary Label vào đây
```

Đồng thời, thay thế biến cục bộ `apply_btn` thành thuộc tính lớp `self._apply_btn`:
```python
self._apply_btn = QPushButton("Apply Changes")
# ... style code ...
self._apply_btn.setEnabled(False)  # Mặc định disabled khi khởi tạo
self._apply_btn.clicked.connect(self._apply_changes)
btn_row.addWidget(self._apply_btn)
```

Liên kết sự kiện thay đổi text của textarea:
```python
self._opx_input.textChanged.connect(self._on_text_changed)
```

#### Các phương thức xử lý sự kiện mới (Slots)
```python
@Slot()
def _on_text_changed(self) -> None:
    """Kích hoạt timer debounce 800ms mỗi khi nội dung thay đổi."""
    self._debounce_timer.start(800)

@Slot()
def _on_debounce_timeout(self) -> None:
    """Gọi PatchDetectionService khi hết thời gian trì hoãn."""
    text = self._opx_input.toPlainText()
    workspace = self.get_workspace()
    ws_root = str(workspace) if workspace else None

    from domain.prompt.patch_detection_service import PatchDetectionService
    detector = PatchDetectionService(workspace_root=ws_root)
    self._detection_result = detector.detect(text)
    
    self._update_detection_ui()

def _update_detection_ui(self) -> None:
    """Cập nhật trạng thái hiển thị của Summary Label và Apply Button."""
    text = self._opx_input.toPlainText().strip()
    
    if not text:
        self._summary_label.hide()
        if self._apply_btn:
            self._apply_btn.setEnabled(False)
        return

    if self._detection_result and self._detection_result.has_patches:
        # Tính tổng số lượng change blocks chi tiết
        num_changes = sum(max(1, len(a.changes)) for a in self._detection_result.file_actions)
        num_files = len(self._detection_result.affected_files)
        files_str = ", ".join(self._detection_result.affected_files)
        
        self._summary_label.setText(
            f"Tìm thấy {num_changes} thay đổi trong {num_files} file: {files_str}"
        )
        self._summary_label.setStyleSheet(
            f"font-size: 11px; color: {ThemeColors.PRIMARY}; font-weight: 600; padding: 2px;"
        )
        self._summary_label.show()
        if self._apply_btn:
            self._apply_btn.setEnabled(True)
    else:
        # Không tìm thấy patch hợp lệ
        self._summary_label.setText("Không tìm thấy patch hợp lệ")
        self._summary_label.setStyleSheet(
            f"font-size: 11px; color: {ThemeColors.ERROR}; font-weight: 600; padding: 2px;"
        )
        self._summary_label.show()
        if self._apply_btn:
            self._apply_btn.setEnabled(False)
```

#### Xử lý sau khi áp dụng patch thành công (`_apply_changes`)
Sửa đổi phần cuối của phương thức `_apply_changes` khi apply thành công:
```python
# Sau khi apply thành công và ghi lịch sử:
success_count = sum(1 for r in results if r.success)
if success_count > 0:
    # Block tín hiệu tạm thời để tránh clear() kích hoạt lại _on_text_changed
    self._opx_input.blockSignals(True)
    self._opx_input.clear()
    self._opx_input.blockSignals(False)
    
    # Hiển thị thông báo thành công trực tiếp
    self._summary_label.setText(f"Đã áp dụng {success_count} thay đổi thành công")
    self._summary_label.setStyleSheet(
        f"font-size: 11px; color: #4ADE80; font-weight: 600; padding: 2px;"
    )
    self._summary_label.show()
    if self._apply_btn:
        self._apply_btn.setEnabled(False)
```

---

## 4. Kế hoạch Kiểm thử (Verification Plan)

### Kiểm thử Tự động (Automated Tests)
Chúng ta sẽ tạo file `tests/presentation/test_apply_tab_upgrade.py` sử dụng thư viện `pytest-qt` để kiểm soát và tương tác với các UI components của PySide6:

1.  **`test_no_duplicate_textarea_in_apply_tab`**:
    *   Khởi tạo `ApplyViewQt`.
    *   Duyệt tìm tất cả các widget kiểu `QPlainTextEdit` và `QTextEdit` trong view.
    *   Khẳng định (assert) số lượng tìm thấy bằng đúng 1.
2.  **`test_detection_triggers_after_800ms_debounce`**:
    *   Điền text chứa patch vào `self._opx_input`.
    *   Verify rằng ngay sau khi điền, logic detect chưa chạy ngay lập tức.
    *   Chờ 800ms (hoặc trigger timer timeout nhân tạo) và kiểm tra xem `self._detection_result` đã được thiết lập.
3.  **`test_apply_button_disabled_without_valid_patches`**:
    *   Nhập chuỗi văn bản bình thường (không chứa cấu trúc patch) vào textarea.
    *   Đợi timer hết giờ, verify `self._apply_btn.isEnabled()` là `False`.
4.  **`test_apply_button_enabled_with_valid_patches`**:
    *   Nhập cấu trúc Search/Replace hợp lệ vào textarea.
    *   Đợi timer hết giờ, verify `self._apply_btn.isEnabled()` là `True`.
5.  **`test_summary_label_shows_filenames`**:
    *   Nhập patch thay đổi 2 file khác nhau.
    *   Đợi timer hết giờ, verify `self._summary_label.text()` chứa đúng thông tin tóm tắt và tên các file.
6.  **`test_summary_label_hidden_when_text_empty`**:
    *   Nhập text vào textarea, sau đó xóa sạch.
    *   Đợi timer hết giờ, verify `self._summary_label.isVisible()` là `False`.
7.  **`test_paste_clipboard_button_fills_textarea`**:
    *   Mock clipboard chứa chuỗi patch.
    *   Giả lập click nút "Paste" (`paste_btn`).
    *   Verify `self._opx_input.toPlainText()` chứa đúng nội dung và trigger sự kiện thay đổi text.
8.  **`test_textarea_clears_after_successful_apply`**:
    *   Mock hàm `apply_file_actions` trả về kết quả thành công.
    *   Nhập patch, click apply button.
    *   Verify `self._opx_input.toPlainText()` trở thành rỗng.
9.  **`test_summary_shows_success_after_apply`**:
    *   Sau khi apply thành công, verify `self._summary_label.text()` hiển thị `"Đã áp dụng X thay đổi thành công"` và nhãn vẫn hiển thị (không bị ẩn).

### Lệnh chạy test
```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/presentation/test_apply_tab_upgrade.py -v
```
