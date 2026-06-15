"""
GUI Tests cho các hộp thoại PySide6: ExclusionsDialog và CustomTemplateDialog.
"""

import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QLineEdit, QTextEdit, QMessageBox

from presentation.components.dialogs.exclusions_dialog import ExclusionsDialog, PatternRow
from presentation.components.dialogs.custom_template_dialog import CustomTemplateDialog
from domain.ports.registry import DomainRegistry
from domain.config.app_settings import AppSettings


class DummySettingsService:
    """Mock SettingsService để trả về AppSettings điều khiển được."""
    def __init__(self) -> None:
        self._settings = AppSettings(
            excluded_folders="node_modules\ndist",
            use_gitignore=True
        )

    def load_settings(self) -> AppSettings:
        return self._settings

    def update_setting(self, key: str, value: str) -> None:
        setattr(self._settings, key, value)


@pytest.fixture(autouse=True)
def setup_settings_port():
    """Tự động đăng ký DummySettingsService cho DomainRegistry."""
    old_service = None
    try:
        old_service = DomainRegistry.settings_service()
    except RuntimeError:
        pass
        
    service = DummySettingsService()
    DomainRegistry.register_settings_service(service)
    yield service
    
    # Restore
    if old_service is not None:
        DomainRegistry.register_settings_service(old_service)


# ===========================================================================
# Exclusions Dialog Tests
# ===========================================================================

def test_exclusions_dialog_loading(qtbot):
    """Test ExclusionsDialog tải đúng các patterns từ settings."""
    dialog = ExclusionsDialog()
    qtbot.addWidget(dialog)
    dialog.show()

    # Kiểm tra xem có 2 PatternRow được tạo ra (node_modules, dist)
    rows = dialog.findChildren(PatternRow)
    assert len(rows) == 2
    patterns = {r.pattern for r in rows}
    assert patterns == {"node_modules", "dist"}


def test_exclusions_dialog_add_pattern(qtbot):
    """Test thêm pattern mới thông qua ô input và click Add."""
    dialog = ExclusionsDialog()
    qtbot.addWidget(dialog)
    dialog.show()

    dialog._input.setText("build")
    
    # Giả lập bấm nút Add (nút QPushButton đầu tiên chứa text "Add")
    add_btn = None
    for btn in dialog.findChildren(QPushButton):
        if btn.text() == "Add":
            add_btn = btn
            break
            
    assert add_btn is not None
    qtbot.mouseClick(add_btn, Qt.MouseButton.LeftButton)

    # Đợi các sự kiện deleteLater xử lý xong
    qtbot.wait(100)

    # Sau khi add, ô input phải rỗng và danh sách tải lại
    assert dialog._input.text() == ""
    rows = dialog.findChildren(PatternRow)
    assert len(rows) == 3
    patterns = {r.pattern for r in rows}
    assert "build" in patterns


def test_exclusions_dialog_del_pattern(qtbot):
    """Test xóa pattern khi click xóa."""
    dialog = ExclusionsDialog()
    qtbot.addWidget(dialog)
    dialog.show()

    rows = dialog.findChildren(PatternRow)
    assert len(rows) == 2
    
    # Gọi trực tiếp callback delete
    dialog._on_del("node_modules")
    
    # Đợi Qt dọn dẹp
    qtbot.wait(100)
    
    rows_after = dialog.findChildren(PatternRow)
    assert len(rows_after) == 1
    assert rows_after[0].pattern == "dist"


# ===========================================================================
# Custom Template Dialog Tests
# ===========================================================================

def test_custom_template_dialog_create(qtbot, tmp_path):
    """Test CustomTemplateDialog khi tạo mới template."""
    # Custom templates dir mock
    mock_dir = tmp_path / "custom_templates"
    
    with patch("presentation.components.dialogs.custom_template_dialog.CUSTOM_TEMPLATES_DIR", mock_dir):
        dialog = CustomTemplateDialog()
        qtbot.addWidget(dialog)
        dialog.show()

        # Nhập dữ liệu
        dialog.name_input.setText("Reviewer Custom")
        dialog.desc_input.setText("A custom code reviewer template")
        dialog.content_input.setPlainText("You are a reviewer. Review my code.")

        # Click Save ( QPushButton có text "Save Template" hoặc objectName "saveBtn" )
        save_btn = dialog.findChild(QPushButton, "saveBtn")
        assert save_btn is not None
        
        # Click Save
        qtbot.mouseClick(save_btn, Qt.MouseButton.LeftButton)
        
        # File template mới phải được lưu
        expected_file = mock_dir / "reviewer_custom.md"
        assert expected_file.exists()
        content = expected_file.read_text(encoding="utf-8")
        assert "<!-- name: Reviewer Custom, desc: A custom code reviewer template -->" in content
        assert "You are a reviewer. Review my code." in content


def test_custom_template_dialog_validation(qtbot):
    """Test validation khi bỏ trống trường bắt buộc."""
    dialog = CustomTemplateDialog()
    qtbot.addWidget(dialog)
    dialog.show()

    # Không nhập gì và bấm save -> phải hiện cảnh báo QMessageBox
    save_btn = dialog.findChild(QPushButton, "saveBtn")
    
    with patch.object(QMessageBox, "warning") as mock_warning:
        qtbot.mouseClick(save_btn, Qt.MouseButton.LeftButton)
        mock_warning.assert_called_once()
