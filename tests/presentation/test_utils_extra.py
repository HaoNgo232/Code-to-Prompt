"""
Tests cho presentation/utils modules:
- clipboard.py: copy_to_clipboard, get_clipboard_text
- history_view_qt.py: backward compatibility re-exports and functions
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from domain.ports.registry import DomainRegistry
from domain.config.app_settings import AppSettings


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
# clipboard.py Tests
# ===========================================================================


def test_copy_to_clipboard_success(qtbot):
    from presentation.utils.clipboard import copy_to_clipboard
    success, err = copy_to_clipboard("Hello world")
    assert success is True
    assert err == ""


def test_copy_to_clipboard_empty_string(qtbot):
    from presentation.utils.clipboard import copy_to_clipboard
    success, err = copy_to_clipboard("")
    # Empty string is still valid clipboard content
    assert isinstance(success, bool)


def test_copy_to_clipboard_no_clipboard(qtbot):
    from presentation.utils.clipboard import copy_to_clipboard
    from PySide6.QtGui import QGuiApplication
    with patch.object(QGuiApplication, "clipboard", return_value=None):
        success, err = copy_to_clipboard("text")
        assert success is False
        assert "not available" in err


def test_copy_to_clipboard_exception(qtbot):
    from presentation.utils.clipboard import copy_to_clipboard
    from PySide6.QtGui import QGuiApplication
    with patch.object(QGuiApplication, "clipboard", side_effect=RuntimeError("crash")):
        success, err = copy_to_clipboard("text")
        assert success is False
        assert "crash" in err


def test_get_clipboard_text_success(qtbot):
    from presentation.utils.clipboard import copy_to_clipboard, get_clipboard_text
    copy_to_clipboard("clipboard content")
    success, text = get_clipboard_text()
    assert success is True
    assert text == "clipboard content"


def test_get_clipboard_text_no_clipboard(qtbot):
    from presentation.utils.clipboard import get_clipboard_text
    from PySide6.QtGui import QGuiApplication
    with patch.object(QGuiApplication, "clipboard", return_value=None):
        success, err = get_clipboard_text()
        assert success is False
        assert "not available" in err


def test_get_clipboard_text_exception(qtbot):
    from presentation.utils.clipboard import get_clipboard_text
    from PySide6.QtGui import QGuiApplication
    with patch.object(QGuiApplication, "clipboard", side_effect=RuntimeError("crash")):
        success, err = get_clipboard_text()
        assert success is False
        assert "crash" in err


# ===========================================================================
# history_view_qt.py Backward Compatibility Tests
# ===========================================================================


def test_history_view_qt_imports():
    """Test that history_view_qt.py exports all expected symbols."""
    import presentation.views.history.history_view_qt as hvq
    assert hasattr(hvq, "HistoryViewQt")
    assert hasattr(hvq, "DateGroupHeader")
    assert hasattr(hvq, "OperationBadge")
    assert hasattr(hvq, "FileChangeRow")
    assert hasattr(hvq, "ErrorCard")
    assert hasattr(hvq, "get_history_entries")
    assert hasattr(hvq, "get_entry_by_id")
    assert hasattr(hvq, "clear_history")
    assert hasattr(hvq, "get_history_stats")
    assert hasattr(hvq, "delete_entry")


def test_get_history_entries_calls_service():
    from presentation.views.history.history_view_qt import get_history_entries
    history_service = MagicMock()
    history_service.get_history_entries.return_value = []

    with patch.object(DomainRegistry, "history_service", return_value=history_service):
        result = get_history_entries(limit=10)
        history_service.get_history_entries.assert_called_once_with(limit=10)
        assert result == []


def test_get_entry_by_id_calls_service():
    from presentation.views.history.history_view_qt import get_entry_by_id
    history_service = MagicMock()
    history_service.get_entry_by_id.return_value = None

    with patch.object(DomainRegistry, "history_service", return_value=history_service):
        result = get_entry_by_id("abc-123")
        history_service.get_entry_by_id.assert_called_once_with("abc-123")


def test_clear_history_calls_service():
    from presentation.views.history.history_view_qt import clear_history
    history_service = MagicMock()
    history_service.clear_history.return_value = 5

    with patch.object(DomainRegistry, "history_service", return_value=history_service):
        result = clear_history()
        history_service.clear_history.assert_called_once()


def test_get_history_stats_calls_service():
    from presentation.views.history.history_view_qt import get_history_stats
    history_service = MagicMock()
    history_service.get_history_stats.return_value = {"total": 10}

    with patch.object(DomainRegistry, "history_service", return_value=history_service):
        result = get_history_stats()
        history_service.get_history_stats.assert_called_once()
        assert result == {"total": 10}


def test_delete_entry_calls_service():
    from presentation.views.history.history_view_qt import delete_entry
    history_service = MagicMock()
    history_service.delete_entry.return_value = True

    with patch.object(DomainRegistry, "history_service", return_value=history_service):
        result = delete_entry("abc-123")
        history_service.delete_entry.assert_called_once_with("abc-123")
