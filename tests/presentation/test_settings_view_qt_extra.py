"""
Unit and integration tests for SettingsViewQt.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QMessageBox,
    QFileDialog,
    QDialog,
    QLineEdit,
)
from domain.ports.registry import DomainRegistry
from domain.config.app_settings import AppSettings
from presentation.views.settings.settings_view_qt import SettingsViewQt


class DummySettingsService:
    def __init__(self) -> None:
        self._settings = AppSettings(
            model_id="gpt-5.1",
            use_gitignore=True,
            ai_api_key="old-key",
            ai_base_url="https://api.openai.com/v1",
            ai_model_id="gpt-5.1",
            output_language="Vietnamese",
            excluded_folders="node_modules\ndist",
        )

    def load_settings(self) -> AppSettings:
        return self._settings

    def update_setting(self, key: str, value: str) -> None:
        setattr(self._settings, key, value)


class DummySessionState:
    def clear_session_state(self) -> None:
        pass


class DummyMCPInstaller:
    def get_mcp_targets(self) -> dict:
        return {
            "Cursor": {"workspace_only": False},
            "Copilot": {"workspace_only": True},
        }

    def check_installed(self, target_name: str, workspace_path: str = None) -> bool:
        return target_name == "Cursor"

    def get_config_path(self, target_name: str, workspace_path: str = None) -> str:
        return f"/mock/path/{target_name}"

    def preview_json(self, target_name: str, workspace_path: str = None) -> str:
        return '{"name": "synapse"}'

    def install_config(
        self, target_name: str, workspace_path: str = None
    ) -> tuple[bool, str]:
        return True, "Success"

    def get_mcp_command(self) -> list[str]:
        return ["python", "main.py", "--run-mcp"]


class DummyAIProvider:
    def __init__(self) -> None:
        self.api_key = ""
        self.base_url = ""

    def configure(self, api_key: str, base_url: str) -> None:
        self.api_key = api_key
        self.base_url = base_url

    def fetch_available_models(self) -> list:
        return ["model-a", "model-b"]


@pytest.fixture(autouse=True)
def setup_registry_dependencies():
    # Save original values
    orig_settings_service = None
    orig_settings_provider = None
    orig_session_state = None
    orig_mcp_installer = None
    orig_ai_factory = None

    try:
        orig_settings_service = DomainRegistry.settings_service()
    except RuntimeError:
        pass
    try:
        orig_settings_provider = DomainRegistry._settings_provider
    except AttributeError:
        pass
    try:
        orig_session_state = DomainRegistry.session_state()
    except RuntimeError:
        pass
    try:
        orig_mcp_installer = DomainRegistry.mcp_installer()
    except RuntimeError:
        pass
    try:
        orig_ai_factory = DomainRegistry.ai_provider_factory()
    except RuntimeError:
        pass

    # Setup dummies
    settings_service = DummySettingsService()
    DomainRegistry.register_settings_service(settings_service)
    DomainRegistry.register_settings_provider(lambda: settings_service.load_settings())

    session_state = DummySessionState()
    DomainRegistry.register_session_state(session_state)

    mcp_installer = DummyMCPInstaller()
    DomainRegistry.register_mcp_installer(mcp_installer)

    ai_provider = DummyAIProvider()
    DomainRegistry.register_ai_provider_factory(lambda: ai_provider)

    yield settings_service, session_state, mcp_installer, ai_provider

    # Restore originals
    if orig_settings_service is not None:
        DomainRegistry.register_settings_service(orig_settings_service)
    DomainRegistry._settings_provider = orig_settings_provider
    if orig_session_state is not None:
        DomainRegistry.register_session_state(orig_session_state)
    if orig_mcp_installer is not None:
        DomainRegistry.register_mcp_installer(orig_mcp_installer)
    if orig_ai_factory is not None:
        DomainRegistry.register_ai_provider_factory(orig_ai_factory)


def test_settings_view_initial_state(qtbot):
    view = SettingsViewQt()
    qtbot.addWidget(view)

    # Assert values loaded correctly from DummySettingsService
    assert view._gitignore_toggle.isChecked() is True
    assert view._tag_chips.get_patterns() == ["node_modules", "dist"]
    assert view._ai_api_key_input.text() == "old-key"
    assert view._ai_base_url_input.text() == "https://api.openai.com/v1"
    assert view._ai_model_combo.currentText() == "gpt-5.1"
    assert view._output_language_combo.currentText() == "Vietnamese"

    # MCP Target Status Labels
    assert view._mcp_status_labels["Cursor"].text() == "✓ Installed"
    assert view._mcp_status_labels["Copilot"].text() == "○ Not installed"


def test_settings_view_auto_save(qtbot, setup_registry_dependencies):
    svc, _, _, _ = setup_registry_dependencies
    view = SettingsViewQt()
    qtbot.addWidget(view)

    # Change gitignore toggle by clicking it
    qtbot.mouseClick(view._gitignore_toggle._toggle, Qt.MouseButton.LeftButton)
    assert view.has_unsaved_changes() is True
    assert view._auto_save_indicator.text() == "Auto-saving..."

    # Force auto save timer to trigger immediately
    view._auto_save_timer.stop()
    view._save_settings()

    assert view.has_unsaved_changes() is False
    assert view._auto_save_indicator.text() == "✓ Changes saved"
    assert svc.load_settings().use_gitignore is False


def test_settings_view_reset_settings(qtbot, setup_registry_dependencies):
    svc, _, _, _ = setup_registry_dependencies
    view = SettingsViewQt()
    qtbot.addWidget(view)

    # 1. Reset settings, but user Cancels
    with patch.object(
        QMessageBox, "warning", return_value=QMessageBox.StandardButton.Cancel
    ) as mock_warn:
        view._reset_settings()
        mock_warn.assert_called_once()
        assert svc.load_settings().use_gitignore is True  # Not changed

    # 2. Reset settings, user accepts (Yes)
    with patch.object(
        QMessageBox, "warning", return_value=QMessageBox.StandardButton.Yes
    ):
        view._reset_settings()
        # Verify defaults are set
        assert view._gitignore_toggle.isChecked() is True
        assert view._ai_api_key_input.text() == ""
        assert view._ai_base_url_input.text() == "https://api.openai.com/v1"


def test_settings_view_load_presets(qtbot):
    view = SettingsViewQt()
    qtbot.addWidget(view)

    # Select Python preset
    view._preset_combo.setCurrentText("Python")
    # Verify merged (Python preset includes venv, __pycache__, etc.)
    patterns = view._tag_chips.get_patterns()
    assert "__pycache__" in patterns
    assert "node_modules" in patterns  # Kept original

    # Select invalid preset should return early
    view._load_preset("Select profile...")


def test_settings_view_clear_session(qtbot):
    view = SettingsViewQt()
    qtbot.addWidget(view)

    # 1. User Cancels
    with (
        patch.object(
            QMessageBox, "question", return_value=QMessageBox.StandardButton.Cancel
        ) as mock_quest,
        patch(
            "presentation.views.settings.settings_view_qt.clear_session_state"
        ) as mock_clear,
    ):
        view._clear_session()
        mock_quest.assert_called_once()
        mock_clear.assert_not_called()

    # 2. User accepts
    with (
        patch.object(
            QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes
        ),
        patch(
            "presentation.views.settings.settings_view_qt.clear_session_state",
            return_value=True,
        ) as mock_clear,
    ):
        view._clear_session()
        mock_clear.assert_called_once()


def test_settings_view_export_import_settings(qtbot):
    view = SettingsViewQt()
    qtbot.addWidget(view)

    # Export settings
    with patch(
        "presentation.views.settings.settings_view_qt.copy_to_clipboard",
        return_value=(True, ""),
    ) as mock_copy:
        view._export_settings()
        mock_copy.assert_called_once()
        # The exported data must be JSON containing AppSettings keys
        args = mock_copy.call_args[0][0]
        data = json.loads(args)
        assert data["use_gitignore"] is True
        assert "excluded_folders" in data

    # Import settings
    # 1. Clipboard is empty or invalid
    with patch(
        "presentation.views.settings.settings_view_qt.get_clipboard_text",
        return_value=(True, ""),
    ) as mock_get_empty:
        view._import_settings()
        mock_get_empty.assert_called_once()

    with patch(
        "presentation.views.settings.settings_view_qt.get_clipboard_text",
        return_value=(True, "{invalid-json}"),
    ):
        view._import_settings()

    with patch(
        "presentation.views.settings.settings_view_qt.get_clipboard_text",
        return_value=(True, '{"some_other_key": 1}'),
    ):
        view._import_settings()

    # 2. Valid settings imported
    import_data = {
        "excluded_folders": "imported_folder\nother",
        "use_gitignore": False,
        "include_git_changes": False,
        "use_relative_paths": False,
        "enable_security_check": False,
        "ai_base_url": "https://api.imported.com/v1",
        "ai_model_id": "imported-model",
    }
    with (
        patch(
            "presentation.views.settings.settings_view_qt.get_clipboard_text",
            return_value=(True, json.dumps(import_data)),
        ),
        patch.object(
            QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes
        ),
    ):
        view._import_settings()
        # Verify imported
        assert view._gitignore_toggle.isChecked() is False
        assert view._tag_chips.get_patterns() == ["imported_folder", "other"]
        assert view._ai_base_url_input.text() == "https://api.imported.com/v1"
        assert view._ai_model_combo.currentText() == "imported-model"


def test_settings_view_mcp_config_snippet(qtbot):
    view = SettingsViewQt()
    qtbot.addWidget(view)

    # Click Generic IDE Config Snippet
    with (
        patch(
            "presentation.views.settings.settings_view_qt.copy_to_clipboard",
            return_value=(True, ""),
        ) as mock_copy,
        patch.object(QDialog, "exec") as mock_exec,
    ):
        view._copy_mcp_config()
        mock_exec.assert_called_once()
        # Simulate user clicking copy inside the dialog, which calls _do_copy
        # We can extract and call the slot manually
        # But here we just want to verify it opens and generates the snippet


def test_settings_view_install_mcp(qtbot, setup_registry_dependencies):
    _, _, mcp, _ = setup_registry_dependencies
    view = SettingsViewQt()
    qtbot.addWidget(view)

    # 1. Global install flow for Cursor (non workspace_only)
    with patch.object(
        QDialog, "exec", return_value=QDialog.DialogCode.Accepted
    ) as mock_exec:
        view._install_mcp_for("Cursor")
        mock_exec.assert_called_once()
        assert view._mcp_status_labels["Cursor"].text() == "✓ Installed"

    # 2. Workspace install flow for Copilot (workspace_only)
    with (
        patch.object(
            QFileDialog, "getExistingDirectory", return_value="/mock/workspace"
        ) as mock_fd,
        patch.object(
            QDialog, "exec", return_value=QDialog.DialogCode.Accepted
        ) as mock_exec,
    ):
        view._ask_workspace_and_install("Copilot")
        mock_fd.assert_called_once()
        mock_exec.assert_called_once()


def test_settings_view_toggle_api_key_visibility(qtbot):
    view = SettingsViewQt()
    qtbot.addWidget(view)

    # Initially password mode
    assert view._ai_api_key_input.echoMode() == QLineEdit.EchoMode.Password

    # Toggle to Normal
    view._toggle_api_key_visibility()
    assert view._ai_api_key_input.echoMode() == QLineEdit.EchoMode.Normal

    # Toggle back to Password
    view._toggle_api_key_visibility()
    assert view._ai_api_key_input.echoMode() == QLineEdit.EchoMode.Password


def test_settings_view_fetch_ai_models(qtbot, setup_registry_dependencies):
    _, _, _, ai = setup_registry_dependencies
    view = SettingsViewQt()
    qtbot.addWidget(view)

    # 1. Key is empty -> show warning
    view._ai_api_key_input.setText("")
    with patch.object(view, "_show_status") as mock_status:
        view._fetch_ai_models()
        mock_status.assert_called_with("Please enter an API Key first.", is_error=True)

    # 2. Key is present -> start background thread (patched to run synchronously)
    view._ai_api_key_input.setText("key")

    with patch.object(
        QThreadPool.globalInstance(), "start", side_effect=lambda w: w.run()
    ):
        view._fetch_ai_models()

    # The combo box should be populated with models ["model-a", "model-b"]
    assert view._ai_model_combo.count() == 2
    assert view._ai_model_combo.itemText(0) == "model-a"
    assert view._ai_model_combo.itemText(1) == "model-b"


def test_settings_view_fetch_ai_models_error(qtbot, setup_registry_dependencies):
    _, _, _, ai = setup_registry_dependencies
    view = SettingsViewQt()
    qtbot.addWidget(view)

    # Mock fetch to raise error
    ai.fetch_available_models = MagicMock(side_effect=Exception("API limit exceeded"))

    view._ai_api_key_input.setText("key")
    with patch.object(view, "_show_status") as mock_status:
        with patch.object(
            QThreadPool.globalInstance(), "start", side_effect=lambda w: w.run()
        ):
            view._fetch_ai_models()

        # Verify status shows error
        mock_status.assert_any_call("API limit exceeded", is_error=True)
        assert view._fetch_btn.isEnabled() is True


def test_settings_view_close_event(qtbot):
    view = SettingsViewQt()
    qtbot.addWidget(view)

    # Setup a mock worker
    view._fetch_worker = MagicMock()
    # Trigger close
    view.close()
    # verify signals disconnected or worker reference cleared
    assert view._fetch_worker is None
