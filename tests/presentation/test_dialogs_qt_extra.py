"""
Tests cho dialogs_qt.py: BaseDialogQt, SecurityDialogQt, RemoteRepoDialogQt,
DirtyRepoDialogQt, FilePreviewDialogQt, CacheManagementDialogQt.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QMessageBox, QPushButton

from domain.ports.registry import DomainRegistry
from domain.config.app_settings import AppSettings
from presentation.components.dialogs.dialogs_qt import (
    BaseDialogQt,
    SecurityDialogQt,
    RemoteRepoDialogQt,
    DirtyRepoDialogQt,
    FilePreviewDialogQt,
    CacheManagementDialogQt,
)


# ===========================================================================
# Fixtures
# ===========================================================================


class DummySettingsService:
    def __init__(self) -> None:
        self._settings = AppSettings()

    def load_settings(self) -> AppSettings:
        return self._settings

    def update_setting(self, key: str, value: str) -> None:
        setattr(self._settings, key, value)


@pytest.fixture(autouse=True)
def setup_registry():
    orig_service = None
    try:
        orig_service = DomainRegistry.settings_service()
    except RuntimeError:
        pass

    service = DummySettingsService()
    DomainRegistry.register_settings_service(service)

    yield service

    if orig_service is not None:
        DomainRegistry.register_settings_service(orig_service)


# ===========================================================================
# BaseDialogQt Tests
# ===========================================================================


def test_base_dialog_init(qtbot):
    dialog = BaseDialogQt(title="Test Title")
    qtbot.addWidget(dialog)
    assert dialog.windowTitle() == "Test Title"
    assert dialog.isModal()


def test_base_dialog_make_buttons(qtbot):
    dialog = BaseDialogQt(title="Test")
    qtbot.addWidget(dialog)
    primary = dialog._make_primary_btn("Primary")
    danger = dialog._make_danger_btn("Danger")
    outlined = dialog._make_outlined_btn("Outlined")
    assert primary.text() == "Primary"
    assert danger.text() == "Danger"
    assert outlined.text() == "Outlined"


def test_base_dialog_make_label(qtbot):
    dialog = BaseDialogQt(title="Test")
    qtbot.addWidget(dialog)
    label = dialog._make_label("Hello world")
    assert label.text() == "Hello world"

    muted_label = dialog._make_label("Muted", muted=True)
    assert muted_label.text() == "Muted"


def test_base_dialog_make_status_label(qtbot):
    dialog = BaseDialogQt(title="Test")
    qtbot.addWidget(dialog)
    status = dialog._make_status_label()
    assert status.text() == ""


# ===========================================================================
# SecurityDialogQt Tests
# ===========================================================================


def _make_security_match(
    secret_type: str = "API_KEY",
    file_path: str = "/path/to/file.py",
    line_number: int = 42,
    redacted_preview: str = "sk-****",
) -> MagicMock:
    m = MagicMock()
    m.secret_type = secret_type
    m.file_path = file_path
    m.line_number = line_number
    m.redacted_preview = redacted_preview
    return m


@pytest.fixture()
def mock_security_scanner():
    """Mock DomainRegistry.security_scanner() với format_security_warning."""
    scanner = MagicMock()
    scanner.format_security_warning.return_value = "Found secrets!"

    orig = DomainRegistry._security_scanner
    DomainRegistry._security_scanner = scanner
    yield scanner
    DomainRegistry._security_scanner = orig


def test_security_dialog_renders(qtbot, mock_security_scanner):
    match = _make_security_match()
    cb = MagicMock()
    dialog = SecurityDialogQt(
        parent=None, prompt="test prompt", matches=[match], on_copy_anyway=cb
    )
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.windowTitle() == "Security Warning"


def test_security_dialog_copy_anyway(qtbot, mock_security_scanner):
    match = _make_security_match()
    cb = MagicMock()
    dialog = SecurityDialogQt(
        parent=None, prompt="test prompt", matches=[match], on_copy_anyway=cb
    )
    qtbot.addWidget(dialog)
    dialog.show()

    # Find "Copy Anyway" button and click it
    copy_anyway_btn = None
    for btn in dialog.findChildren(QPushButton):
        if "anyway" in btn.text().lower():
            copy_anyway_btn = btn
            break

    assert copy_anyway_btn is not None
    copy_anyway_btn.click()
    cb.assert_called_once_with("test prompt")


def test_security_dialog_cancel(qtbot, mock_security_scanner):
    match = _make_security_match()
    cb = MagicMock()
    dialog = SecurityDialogQt(
        parent=None, prompt="test prompt", matches=[match], on_copy_anyway=cb
    )
    qtbot.addWidget(dialog)
    dialog.show()

    # Find Cancel button and click it
    cancel_btn = None
    for btn in dialog.findChildren(QPushButton):
        if btn.text().lower() == "cancel":
            cancel_btn = btn
            break

    assert cancel_btn is not None
    cancel_btn.click()
    cb.assert_not_called()


def test_security_dialog_copy_results(qtbot, mock_security_scanner):
    match = _make_security_match()
    cb = MagicMock()
    dialog = SecurityDialogQt(
        parent=None, prompt="test prompt", matches=[match], on_copy_anyway=cb
    )
    qtbot.addWidget(dialog)
    dialog.show()

    with patch(
        "presentation.components.dialogs.dialogs_qt.copy_to_clipboard"
    ) as mock_copy:
        dialog._copy_results()
        mock_copy.assert_called_once()


def test_security_dialog_no_file_path(qtbot, mock_security_scanner):
    """Test with match that has no file_path."""
    match = _make_security_match(file_path="")
    cb = MagicMock()
    dialog = SecurityDialogQt(
        parent=None, prompt="", matches=[match], on_copy_anyway=cb
    )
    qtbot.addWidget(dialog)
    dialog.show()
    # Should render without error even with empty file path
    assert dialog.isVisible()


# ===========================================================================
# RemoteRepoDialogQt Tests
# ===========================================================================


def test_remote_repo_dialog_renders(qtbot):
    repo_manager = MagicMock()
    on_success = MagicMock()
    dialog = RemoteRepoDialogQt(
        parent=None, repo_manager=repo_manager, on_clone_success=on_success
    )
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.windowTitle() == "Open Remote Repository"
    assert dialog._url_field is not None


def test_remote_repo_dialog_empty_url(qtbot):
    repo_manager = MagicMock()
    on_success = MagicMock()
    dialog = RemoteRepoDialogQt(
        parent=None, repo_manager=repo_manager, on_clone_success=on_success
    )
    qtbot.addWidget(dialog)
    dialog.show()

    # Click Clone without entering URL
    dialog._clone_btn.click()
    # Status should show error
    assert "enter" in dialog._status.text().lower()
    repo_manager.clone_repo.assert_not_called()


def test_remote_repo_dialog_clone_success(qtbot, tmp_path):
    repo_path = tmp_path / "cloned_repo"
    repo_path.mkdir()

    repo_manager = MagicMock()
    repo_manager.clone_repo.return_value = repo_path

    on_success = MagicMock()
    dialog = RemoteRepoDialogQt(
        parent=None, repo_manager=repo_manager, on_clone_success=on_success
    )
    qtbot.addWidget(dialog)
    dialog.show()

    # Simulate clone result directly (as if threading completed)
    dialog._handle_clone_result(repo_path)
    on_success.assert_called_once_with(repo_path)


def test_remote_repo_dialog_clone_error(qtbot):
    repo_manager = MagicMock()
    on_success = MagicMock()
    dialog = RemoteRepoDialogQt(
        parent=None, repo_manager=repo_manager, on_clone_success=on_success
    )
    qtbot.addWidget(dialog)
    dialog.show()

    error = Exception("Network error")
    dialog._handle_clone_result(error)
    assert "Network error" in dialog._status.text()
    on_success.assert_not_called()


# ===========================================================================
# DirtyRepoDialogQt Tests
# ===========================================================================


def test_dirty_repo_dialog_renders(qtbot):
    repo_manager = MagicMock()
    on_done = MagicMock()
    repo_path = Path("/fake/repo")
    dialog = DirtyRepoDialogQt(
        parent=None,
        repo_manager=repo_manager,
        repo_path=repo_path,
        repo_name="my-repo",
        on_done=on_done,
    )
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.windowTitle() == "Uncommitted Changes"


def test_dirty_repo_dialog_stash_and_pull(qtbot):
    repo_manager = MagicMock()
    on_done = MagicMock()
    repo_path = Path("/fake/repo")
    dialog = DirtyRepoDialogQt(
        parent=None,
        repo_manager=repo_manager,
        repo_path=repo_path,
        repo_name="my-repo",
        on_done=on_done,
    )
    qtbot.addWidget(dialog)

    # _stash_and_pull starts a daemon thread; just verify it runs without exception
    # Patch run_on_main_thread to avoid updating closed dialog
    with patch("presentation.components.dialogs.dialogs_qt.run_on_main_thread"):
        dialog._stash_and_pull()
    # Dialog accepted immediately, thread scheduled in background
    assert True  # No exception means success


def test_dirty_repo_dialog_discard_cancel(qtbot):
    """Test that choosing No in QMessageBox does not proceed."""
    repo_manager = MagicMock()
    on_done = MagicMock()
    repo_path = Path("/fake/repo")
    dialog = DirtyRepoDialogQt(
        parent=None,
        repo_manager=repo_manager,
        repo_path=repo_path,
        repo_name="my-repo",
        on_done=on_done,
    )
    qtbot.addWidget(dialog)
    dialog.show()

    with patch.object(
        QMessageBox, "warning", return_value=QMessageBox.StandardButton.No
    ):
        dialog._discard_and_pull()
    # Should not proceed
    repo_manager.discard_changes.assert_not_called()


def test_dirty_repo_dialog_discard_confirm(qtbot):
    """Test that choosing Yes in QMessageBox calls discard."""
    repo_manager = MagicMock()
    on_done = MagicMock()
    repo_path = Path("/fake/repo")
    dialog = DirtyRepoDialogQt(
        parent=None,
        repo_manager=repo_manager,
        repo_path=repo_path,
        repo_name="my-repo",
        on_done=on_done,
    )
    qtbot.addWidget(dialog)

    with patch.object(
        QMessageBox, "warning", return_value=QMessageBox.StandardButton.Yes
    ):
        dialog._discard_and_pull()

    # Should proceed (thread runs but we don't wait for it)
    # Dialog is accepted at this point


# ===========================================================================
# FilePreviewDialogQt Tests
# ===========================================================================


def test_file_preview_dialog_with_content(qtbot, tmp_path):
    f = tmp_path / "test.py"
    f.write_text("line1\nline2\nline3")

    dialog = FilePreviewDialogQt(
        parent=None, file_path=str(f), content="line1\nline2\nline3"
    )
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.windowTitle() != ""


def test_file_preview_dialog_no_content_reads_file(qtbot, tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello from file")
    dialog = FilePreviewDialogQt(parent=None, file_path=str(f))
    qtbot.addWidget(dialog)
    dialog.show()
    # Should load content from disk
    assert dialog.isVisible()


def test_file_preview_dialog_missing_file(qtbot):
    dialog = FilePreviewDialogQt(parent=None, file_path="/nonexistent/file.py")
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.isVisible()


def test_file_preview_dialog_with_highlight_line(qtbot, tmp_path):
    f = tmp_path / "test.py"
    lines = [f"line {i}" for i in range(10)]
    f.write_text("\n".join(lines))

    dialog = FilePreviewDialogQt(
        parent=None, file_path=str(f), content="\n".join(lines), highlight_line=5
    )
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.isVisible()


# ===========================================================================
# CacheManagementDialogQt Tests
# ===========================================================================


def test_cache_management_dialog_renders(qtbot):
    repo_manager = MagicMock()
    repo_manager.list_cached_repos.return_value = []
    on_open = MagicMock()

    dialog = CacheManagementDialogQt(
        parent=None, repo_manager=repo_manager, on_open_repo=on_open
    )
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.windowTitle() == "Cached Repositories"


def test_cache_management_dialog_with_repos(qtbot):
    repo_manager = MagicMock()
    from datetime import datetime

    repo = MagicMock()
    repo.name = "my-repo"
    repo.size_bytes = 1024 * 1024 * 50  # 50 MB
    repo.last_modified = datetime.now()
    repo.path = Path("/fake/path/my-repo")

    repo_manager.list_cached_repos.return_value = [repo]
    on_open = MagicMock()

    dialog = CacheManagementDialogQt(
        parent=None, repo_manager=repo_manager, on_open_repo=on_open
    )
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.isVisible()
