# Apply Tab Auto-Detection Upgrade Implementation Plan (Cập nhật Phương án B)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nâng cấp tab Apply để tự động nhận diện patch, hiển thị nhãn tóm tắt và kích hoạt Popup Menu chứa danh sách cuộn các file bị ảnh hưởng dưới dạng click-to-copy.

**Architecture:** Sử dụng `PatchDetectionService` tích hợp vào `ApplyViewQt`. Liên kết tín hiệu `textChanged` của textarea với `QTimer` 800ms debounce. Sử dụng liên kết HTML `[Show Files]` trên `QLabel` cùng tín hiệu `linkActivated` để hiển thị `QMenu` chứa danh sách file có tích hợp copy clipboard.

**Tech Stack:** Python 3, PySide6, Pytest, Pytest-qt, Ruff, Pyrefly.

---

### Task 1: Thiết lập TDD - Tạo file kiểm thử với các test rỗng

**Files:**
- Create: `tests/presentation/test_apply_tab_upgrade.py`

- [ ] **Step 1: Tạo cấu trúc test file rỗng**

Tạo file `tests/presentation/test_apply_tab_upgrade.py` định nghĩa các phương thức kiểm thử (nội dung dùng `pass`):

```python
import pytest

def test_no_duplicate_textarea_in_apply_tab(qtbot) -> None:
    """Kiểm tra chỉ có đúng một textarea trong Apply View."""
    pass

def test_detection_triggers_after_800ms_debounce(qtbot) -> None:
    """Kiểm tra tính năng tự động nhận diện được kích hoạt sau 800ms debounce."""
    pass

def test_apply_button_disabled_without_valid_patches(qtbot) -> None:
    """Nút Apply Changes bị disable khi không chứa patch hợp lệ."""
    pass

def test_apply_button_enabled_with_valid_patches(qtbot) -> None:
    """Nút Apply Changes được enable khi chứa patch hợp lệ."""
    pass

def test_summary_label_shows_show_files_link(qtbot) -> None:
    """Summary label hiển thị đúng liên kết Show Files."""
    pass

def test_summary_label_hidden_when_text_empty(qtbot) -> None:
    """Summary label tự động ẩn đi khi textarea trống."""
    pass

def test_paste_clipboard_button_fills_textarea(qtbot) -> None:
    """Verify việc dán clipboard chèn text vào textarea."""
    pass

def test_textarea_clears_after_successful_apply(qtbot) -> None:
    """Textarea được dọn sạch sau khi áp dụng patch thành công."""
    pass

def test_summary_shows_success_after_apply(qtbot) -> None:
    """Nhãn tóm tắt hiển thị thông báo thành công sau khi apply."""
    pass
```

- [ ] **Step 2: Chạy pytest xác nhận các test rỗng PASS**

Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/presentation/test_apply_tab_upgrade.py -v`
Expected: 9 passed

- [ ] **Step 3: Commit**

```bash
git add tests/presentation/test_apply_tab_upgrade.py
git commit -m "test: setup TDD structure for Apply tab upgrade with show files popup"
```

---

### Task 2: Cập nhật các Test Case thực tế và xác nhận chúng FAIL

**Files:**
- Modify: `tests/presentation/test_apply_tab_upgrade.py`

- [ ] **Step 1: Viết nội dung kiểm thử chi tiết sử dụng pytest-qt**

Ghi đè nội dung file `tests/presentation/test_apply_tab_upgrade.py` bằng các test case thực tế:

```python
import pytest
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QPlainTextEdit,
    QTextEdit,
    QPushButton,
    QApplication,
)
from presentation.views.apply.apply_view_qt import ApplyViewQt

def test_no_duplicate_textarea_in_apply_tab(qtbot) -> None:
    """Kiểm tra chỉ có đúng một textarea trong Apply View."""
    view = ApplyViewQt(get_workspace=lambda: Path("."))
    qtbot.addWidget(view)

    textareas_plain = view.findChildren(QPlainTextEdit)
    textareas_rich = view.findChildren(QTextEdit)
    total_textareas = len(textareas_plain) + len(textareas_rich)

    assert total_textareas == 1
    assert view._opx_input is not None

def test_detection_triggers_after_800ms_debounce(qtbot) -> None:
    """Kiểm tra tính năng tự động nhận diện được kích hoạt sau 800ms debounce."""
    view = ApplyViewQt(get_workspace=lambda: Path("."))
    qtbot.addWidget(view)

    view._opx_input.setPlainText(
        "<<<<<<< SEARCH main.py\n=======\n>>>>>>> REPLACE"
    )

    # Ngay lập tức kết quả detect chưa được thiết lập
    assert view._detection_result is None

    # Chờ 900ms để debounce kích hoạt
    qtbot.wait(900)

    assert view._detection_result is not None
    assert view._detection_result.has_patches is True

def test_apply_button_disabled_without_valid_patches(qtbot) -> None:
    """Nút Apply Changes bị disable khi không chứa patch hợp lệ."""
    view = ApplyViewQt(get_workspace=lambda: Path("."))
    qtbot.addWidget(view)

    view._opx_input.setPlainText("Chào bạn, tôi muốn trò chuyện bình thường.")
    qtbot.wait(900)

    assert view._apply_btn is not None
    assert view._apply_btn.isEnabled() is False

def test_apply_button_enabled_with_valid_patches(qtbot) -> None:
    """Nút Apply Changes được enable khi chứa patch hợp lệ."""
    view = ApplyViewQt(get_workspace=lambda: Path("."))
    qtbot.addWidget(view)

    view._opx_input.setPlainText(
        "<<<<<<< SEARCH main.py\n=======\n>>>>>>> REPLACE"
    )
    qtbot.wait(900)

    assert view._apply_btn is not None
    assert view._apply_btn.isEnabled() is True

def test_summary_label_shows_show_files_link(qtbot) -> None:
    """Summary label hiển thị đúng liên kết Show Files."""
    view = ApplyViewQt(get_workspace=lambda: Path("."))
    qtbot.addWidget(view)

    text = (
        "<<<<<<< SEARCH src/a.py\n=======\n>>>>>>> REPLACE\n"
        "<<<<<<< SEARCH src/b.py\n=======\n>>>>>>> REPLACE"
    )
    view._opx_input.setPlainText(text)
    qtbot.wait(900)

    assert view._summary_label is not None
    assert not view._summary_label.isHidden()
    summary_text = view._summary_label.text()
    assert "Found 2 changes in 2 affected files" in summary_text
    assert "[Show Files]" in summary_text

def test_summary_label_hidden_when_text_empty(qtbot) -> None:
    """Summary label tự động ẩn đi khi textarea trống."""
    view = ApplyViewQt(get_workspace=lambda: Path("."))
    qtbot.addWidget(view)

    view._opx_input.setPlainText(
        "<<<<<<< SEARCH main.py\n=======\n>>>>>>> REPLACE"
    )
    qtbot.wait(900)
    assert not view._summary_label.isHidden()

    view._opx_input.clear()
    qtbot.wait(900)
    assert view._summary_label.isHidden()

def test_paste_clipboard_button_fills_textarea(qtbot) -> None:
    """Verify việc paste clipboard chèn text vào textarea và kích hoạt detect."""
    clipboard = QApplication.clipboard()
    test_text = "<<<<<<< SEARCH main.py\n=======\n>>>>>>> REPLACE"
    clipboard.setText(test_text)

    view = ApplyViewQt(get_workspace=lambda: Path("."))
    qtbot.addWidget(view)

    paste_btn = None
    for btn in view.findChildren(QPushButton):
        if btn.text() == "Paste":
            paste_btn = btn
            break

    assert paste_btn is not None
    qtbot.mouseClick(paste_btn, Qt.MouseButton.LeftButton)

    assert view._opx_input.toPlainText() == test_text

def test_textarea_clears_after_successful_apply(qtbot, monkeypatch) -> None:
    """Textarea được dọn sạch sau khi áp dụng patch thành công."""
    from infrastructure.filesystem.file_actions import ActionResult

    def mock_apply_file_actions(file_actions, roots):
        return [
            ActionResult(
                action="create", path="main.py", success=True, message="Success"
            )
        ]

    monkeypatch.setattr(
        "presentation.views.apply.apply_view_qt.apply_file_actions",
        mock_apply_file_actions,
    )

    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )

    view = ApplyViewQt(get_workspace=lambda: Path("."))
    qtbot.addWidget(view)

    view._opx_input.setPlainText(
        "<<<<<<< SEARCH main.py\n=======\n>>>>>>> REPLACE"
    )
    qtbot.wait(900)

    qtbot.mouseClick(view._apply_btn, Qt.MouseButton.LeftButton)

    assert view._opx_input.toPlainText() == ""

def test_summary_shows_success_after_apply(qtbot, monkeypatch) -> None:
    """Nhãn tóm tắt hiển thị thông báo thành công sau khi apply."""
    from infrastructure.filesystem.file_actions import ActionResult

    def mock_apply_file_actions(file_actions, roots):
        return [
            ActionResult(
                action="create", path="main.py", success=True, message="Success"
            )
        ]

    monkeypatch.setattr(
        "presentation.views.apply.apply_view_qt.apply_file_actions",
        mock_apply_file_actions,
    )

    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )

    view = ApplyViewQt(get_workspace=lambda: Path("."))
    qtbot.addWidget(view)

    view._opx_input.setPlainText(
        "<<<<<<< SEARCH main.py\n=======\n>>>>>>> REPLACE"
    )
    qtbot.wait(900)

    qtbot.mouseClick(view._apply_btn, Qt.MouseButton.LeftButton)

    # Chờ để đảm bảo debounce không chạy đè
    qtbot.wait(900)

    assert "Successfully applied 1 changes" in view._summary_label.text()
    assert not view._summary_label.isHidden()
```

- [ ] **Step 2: Chạy pytest và verify test FAIL**

Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/presentation/test_apply_tab_upgrade.py -v`
Expected: FAIL (do test case `test_summary_label_shows_show_files_link` bị lỗi do nhãn hiển thị cũ)

- [ ] **Step 3: Commit**

```bash
git add tests/presentation/test_apply_tab_upgrade.py
git commit -m "test: write UI tests for show files popup menu flow"
```

---

### Task 3: Triển khai nâng cấp giao diện Phương án B

**Files:**
- Modify: `presentation/views/apply/apply_view_qt.py`

- [ ] **Step 1: Cập nhật cấu hình summary label trong `_build_left_panel`**

Bổ sung cấu hình đón nhận tín hiệu click link HTML:
```python
        self._summary_label = QLabel()
        self._summary_label.setWordWrap(True)
        # Bổ sung flag tương tác link HTML
        self._summary_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self._summary_label.setOpenExternalLinks(False)
        self._summary_label.linkActivated.connect(self._show_affected_files_menu)
```

- [ ] **Step 2: Thêm slot `_show_affected_files_menu`**

Triển khai phương thức sinh ra QMenu chứa danh sách file và copy clipboard khi click:
```python
    @Slot(str)
    def _show_affected_files_menu(self, link_text: str) -> None:
        """Hiển thị Popup Menu chứa các file bị ảnh hưởng."""
        if not self._detection_result or not self._detection_result.affected_files:
            return

        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{"
            f"  background-color: {ThemeColors.BG_ELEVATED};"
            f"  border: 1px solid {ThemeColors.BORDER};"
            f"  border-radius: 6px;"
            f"  padding: 4px 0px;"
            f"}}"
            f"QMenu::item {{"
            f"  padding: 6px 16px;"
            f"  color: {ThemeColors.TEXT_PRIMARY};"
            f"  font-family: 'Cascadia Code', 'Fira Code', monospace;"
            f"  font-size: 11px;"
            f"}}"
            f"QMenu::item:selected {{"
            f"  background-color: {ThemeColors.PRIMARY};"
            f"  color: white;"
            f"}}"
        )

        for file_path in self._detection_result.affected_files:
            action = menu.addAction(f"📄  {file_path}")
            action.setToolTip("Click to copy file path")
            action.triggered.connect(
                lambda checked=False, p=file_path: (
                    copy_to_clipboard(p),
                    self._show_status(f"Copied: {p}")
                )
            )

        pos = self._summary_label.mapToGlobal(self._summary_label.rect().bottomLeft())
        pos.setY(pos.y() + 4)
        menu.exec(pos)
```

- [ ] **Step 3: Cập nhật nhãn tóm tắt trong `_update_detection_ui`**

Cập nhật lại nhãn tóm tắt chỉ hiển thị tổng quan và link `[Show Files]`:
```python
        if self._detection_result and self._detection_result.has_patches:
            num_changes = sum(
                max(1, len(a.changes)) for a in self._detection_result.file_actions
            )
            num_files = len(self._detection_result.affected_files)

            if self._summary_label:
                self._summary_label.setText(
                    f"Found {num_changes} changes in {num_files} affected files. "
                    f"<a href='show_files' style='color: {ThemeColors.PRIMARY}; text-decoration: none; font-weight: bold;'>[Show Files]</a>"
                )
                self._summary_label.setToolTip("") # Không cần tooltip nữa
                self._summary_label.setStyleSheet(
                    f"font-size: 11px; color: {ThemeColors.PRIMARY}; font-weight: 600; "
                    f"background-color: rgba(59, 130, 246, 0.08); border: 1px solid rgba(59, 130, 246, 0.2); "
                    f"border-radius: 6px; padding: 6px 10px; margin-top: 4px;"
                )
                self._summary_label.show()
```

- [ ] **Step 4: Chạy pytest xác nhận toàn bộ test PASS**

Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/presentation/test_apply_tab_upgrade.py -v`
Expected: 9 passed

- [ ] **Step 5: Chạy Ruff format và check**

Run:
```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/ruff format presentation/views/apply/apply_view_qt.py tests/presentation/test_apply_tab_upgrade.py
env -u PYTHONHOME -u PYTHONPATH .venv/bin/ruff check --fix presentation/views/apply/apply_view_qt.py tests/presentation/test_apply_tab_upgrade.py
```

- [ ] **Step 6: Commit**

```bash
git add presentation/views/apply/apply_view_qt.py tests/presentation/test_apply_tab_upgrade.py
git commit -m "feat: optimize Apply tab summary label with HTML show files link and popup menu"
```
