# Runtime Imports and Unicode Decode Fix Design

**Goal:** Khắc phục lỗi import `is_binary_file` từ đường dẫn cũ khi đóng ứng dụng và sửa lỗi `UnicodeDecodeError` khi chạy các tiến trình Git trên môi trường Windows.

## Proposed Changes

### 1. Sửa import lỗi trong `infrastructure/filesystem/file_scanner.py`

**File:** [file_scanner.py](file:///d:/share_vm/Synapse-Desktop/infrastructure/filesystem/file_scanner.py)

**Sửa đổi:**
Thay đổi import từ:
```python
from infrastructure.filesystem.file_utils import (
    TreeItem,
    is_system_path,
    is_binary_file,
)
```
Thành:
```python
from infrastructure.filesystem.file_utils import (
    TreeItem,
    is_system_path,
)
from shared.utils.file_utils import is_binary_file
```

---

### 2. Cập nhật các wrapper trong `infrastructure/adapters/subprocess_utils.py`

**File:** [subprocess_utils.py](file:///d:/share_vm/Synapse-Desktop/infrastructure/adapters/subprocess_utils.py)

**Sửa đổi:**
Cập nhật `run_subprocess` và `popen_subprocess` để tự động inject `encoding="utf-8"` và `errors="replace"` nếu `text=True` hoặc `universal_newlines=True` được thiết lập mà không truyền tham số `encoding` rõ ràng.

---

### 3. Cập nhật `infrastructure/git/git_utils.py` sử dụng wrapper

**File:** [git_utils.py](file:///d:/share_vm/Synapse-Desktop/infrastructure/git/git_utils.py)

**Sửa đổi:**
- Import `run_subprocess` từ `infrastructure.adapters.subprocess_utils`.
- Thay thế tất cả các lượt gọi `subprocess.run` trực tiếp thành `run_subprocess`.

---

## Verification Plan

### Automated Tests
- Chạy toàn bộ test suite để đảm bảo không xảy ra regression:
  ```bash
  .venv/Scripts/pytest tests/ -v
  ```

### Manual Verification
- Chạy lại ứng dụng `.\start.bat --no-license` trên Windows, thao tác một số hành động liên quan đến Git (chọn file diff, xem log) và tắt ứng dụng.
- Đảm bảo terminal không còn in ra `UnicodeDecodeError` của `_readerthread` và không còn lỗi import `is_binary_file` của `closeEvent`.
