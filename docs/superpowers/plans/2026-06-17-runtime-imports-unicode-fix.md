# Runtime Imports and Unicode Decode Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Khắc phục lỗi import `is_binary_file` của `closeEvent` và lỗi `UnicodeDecodeError` khi chạy tiến trình Git trên Windows.

**Architecture:** Sửa import trong `file_scanner.py`, viết kiểm thử và cập nhật `subprocess_utils.py` để tự động gán UTF-8 encoding khi chạy text mode, đồng thời cập nhật `git_utils.py` sử dụng wrapper này.

**Tech Stack:** Python 3.12, PySide6, pytest, subprocess.

## Global Constraints
- Absolute imports must be used at all times.
- DO NOT run any git commit commands automatically (`RULE[user_global]`).
- Paths should be compared using OS-agnostic methods.

---

### Task 1: Fix Runtime Import Error in File Scanner

**Files:**
- Modify: `infrastructure/filesystem/file_scanner.py`

- [ ] **Step 1: Cập nhật dòng import trong `file_scanner.py`**
  Thay đổi đoạn import ở dòng 25-29 của [file_scanner.py](file:///d:/share_vm/Synapse-Desktop/infrastructure/filesystem/file_scanner.py) từ:
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
- [ ] **Step 2: Chạy test kiểm chứng**
  Chạy: `.venv\Scripts\pytest tests/ -v` (hoặc chạy một file test UI như `tests/ui/test_main_ui.py`)
  Expected: Collection và test chạy bình thường, không bị crash do ImportError.

---

### Task 2: Implement UTF-8 Encoding in Subprocess Wrapper and Update Git Utils

**Files:**
- Create: `tests/integration/test_subprocess_utils.py`
- Modify: `infrastructure/adapters/subprocess_utils.py`
- Modify: `infrastructure/git/git_utils.py`

- [ ] **Step 1: Viết test case phát hiện lỗi (TDD - failing test)**
  Tạo file [test_subprocess_utils.py](file:///d:/share_vm/Synapse-Desktop/tests/integration/test_subprocess_utils.py) với nội dung:
  ```python
  import subprocess
  import pytest
  from infrastructure.adapters.subprocess_utils import run_subprocess, popen_subprocess

  def test_run_subprocess_utf8_encoding(tmp_path):
      script = tmp_path / "print_utf8.py"
      # Ghi file chứa ký tự UTF-8 đặc biệt (tiếng Việt có dấu)
      script.write_text("print('Xin chào, đây là UTF-8: \u008f')", encoding="utf-8")

      # Chạy với text=True, nếu không có encoding="utf-8" mặc định trên Windows (cp1252),
      # nó sẽ ném ra UnicodeDecodeError trong luồng đọc.
      result = run_subprocess(
          ["python", str(script)],
          capture_output=True,
          text=True,
          check=True
      )
      assert "Xin chào" in result.stdout
  ```
- [ ] **Step 2: Chạy test để xác nhận nó thất bại trên Windows**
  Run: `.venv\Scripts\pytest tests/integration/test_subprocess_utils.py -v`
  Expected: FAIL (UnicodeDecodeError hoặc lỗi tương tự trên Windows).
- [ ] **Step 3: Cập nhật `subprocess_utils.py` để inject UTF-8 encoding**
  Trong [subprocess_utils.py](file:///d:/share_vm/Synapse-Desktop/infrastructure/adapters/subprocess_utils.py), cập nhật `run_subprocess` và `popen_subprocess`:
  ```python
  def run_subprocess(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess:
      if _IS_WINDOWS and "creationflags" not in kwargs:
          kwargs["creationflags"] = _NO_WINDOW_FLAGS

      if kwargs.get("text") or kwargs.get("universal_newlines"):
          if "encoding" not in kwargs:
              kwargs["encoding"] = "utf-8"
              if "errors" not in kwargs:
                  kwargs["errors"] = "replace"

      return subprocess.run(*args, **kwargs)


  def popen_subprocess(*args: Any, **kwargs: Any) -> subprocess.Popen:
      if _IS_WINDOWS and "creationflags" not in kwargs:
          kwargs["creationflags"] = _NO_WINDOW_FLAGS

      if kwargs.get("text") or kwargs.get("universal_newlines"):
          if "encoding" not in kwargs:
              kwargs["encoding"] = "utf-8"
              if "errors" not in kwargs:
                  kwargs["errors"] = "replace"

      return subprocess.Popen(*args, **kwargs)
  ```
- [ ] **Step 4: Chạy lại test để xác nhận nó pass**
  Run: `.venv\Scripts\pytest tests/integration/test_subprocess_utils.py -v`
  Expected: PASS
- [ ] **Step 5: Cập nhật `git_utils.py` sử dụng wrapper**
  Trong [git_utils.py](file:///d:/share_vm/Synapse-Desktop/infrastructure/git/git_utils.py), import `run_subprocess` và thay thế các lượt gọi `subprocess.run` trực tiếp thành `run_subprocess`:
  - Dòng 6: import `subprocess` -> Giữ lại hoặc import thêm `from infrastructure.adapters.subprocess_utils import run_subprocess`.
  - Thay thế `subprocess.run(` bằng `run_subprocess(` tại các dòng: 183 (`is_git_repo`), 218 (`get_git_diffs`), 228, 236, 281 (`get_git_logs`), 394 (`get_diff_only`), 403, 424, 433, 470, 484, 506, 516.
- [ ] **Step 6: Chạy thử bộ test Git để xác minh tính đúng đắn**
  Run: `.venv\Scripts\pytest tests/test_git_utils.py -v`
  Expected: PASS

---

### Task 3: Chạy nghiệm thu toàn bộ Test Suite

- [ ] **Step 1: Chạy full test suite**
  Run: `.venv\Scripts\pytest tests/ -v`
  Expected: 100% PASS
