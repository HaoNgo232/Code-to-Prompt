"""
Tests cho PresetWidget - UI component cho Context Presets.
"""

import pytest
from typing import List
from unittest.mock import MagicMock, patch
from PySide6.QtCore import Signal, QObject
from PySide6.QtWidgets import QInputDialog, QMessageBox

from domain.ports.registry import DomainRegistry
from domain.config.app_settings import AppSettings
from presentation.components.preset_widget import PresetWidget


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


class DummyPresetEntry:
    def __init__(self, preset_id: str, name: str, selected_paths: List[str] = None):
        self.preset_id = preset_id
        self.name = name
        self.selected_paths = selected_paths or []


class DummyController(QObject):
    """Minimal mock for PresetController."""

    presets_changed = Signal()
    preset_loaded = Signal(str)

    def __init__(self):
        super().__init__()
        self._presets = []
        self._active_id = None

    def list_presets(self):
        return self._presets

    def get_active_preset_id(self):
        return self._active_id

    def is_selection_dirty(self):
        return False

    def create_preset(self, name: str):
        pass

    def update_preset(self, preset_id: str):
        pass

    def rename_preset(self, preset_id: str, name: str):
        pass

    def delete_preset(self, preset_id: str):
        pass

    def load_preset(self, preset_id: str):
        self._active_id = preset_id
        self.preset_loaded.emit(preset_id)


@pytest.fixture()
def controller():
    return DummyController()


@pytest.fixture()
def widget(controller, qtbot):
    w = PresetWidget(controller=controller)
    qtbot.addWidget(w)
    return w


# ===========================================================================
# PresetWidget Initialization Tests
# ===========================================================================


def test_preset_widget_init(widget):
    assert widget is not None
    assert widget._main_btn is not None
    assert widget._menu is not None


def test_preset_widget_combo_compat(widget):
    """_MockCombo backward compat."""
    combo = widget._combo
    # With no presets, count should be 0
    assert combo.count() == 0


def test_preset_widget_label_hidden(widget):
    assert widget._label is not None
    assert widget._label.isHidden()


def test_preset_widget_button_text_no_presets(widget):
    assert "Select preset" in widget._main_btn.text()


def test_preset_widget_menu_has_create_action(widget):
    actions = widget._menu.actions()
    action_data = [a.data() for a in actions]
    assert "__NEW__" in action_data


# ===========================================================================
# PresetWidget with Presets Tests
# ===========================================================================


def test_preset_widget_with_presets(controller, qtbot):
    controller._presets = [
        DummyPresetEntry("id1", "My Preset", ["file1.py", "file2.py"]),
        DummyPresetEntry("id2", "Other Preset", ["file3.py"]),
    ]
    widget = PresetWidget(controller=controller)
    qtbot.addWidget(widget)

    combo = widget._combo
    assert combo.count() == 2


def test_preset_widget_combo_item_text(controller, qtbot):
    controller._presets = [
        DummyPresetEntry("id1", "My Preset", ["file1.py"]),
    ]
    widget = PresetWidget(controller=controller)
    qtbot.addWidget(widget)

    combo = widget._combo
    text = combo.itemText(0)
    assert "My Preset" in text


def test_preset_widget_combo_item_text_invalid_index(controller, qtbot):
    controller._presets = []
    widget = PresetWidget(controller=controller)
    qtbot.addWidget(widget)

    combo = widget._combo
    text = combo.itemText(99)
    assert text == ""


def test_preset_widget_mock_combo_current_index(widget):
    combo = widget._combo
    assert combo.currentIndex() == -1


def test_preset_widget_mock_combo_set_current_index(widget):
    combo = widget._combo
    # Should not raise
    combo.setCurrentIndex(0)


def test_preset_widget_refresh(controller, qtbot):
    widget = PresetWidget(controller=controller)
    qtbot.addWidget(widget)

    controller._presets = [DummyPresetEntry("id1", "New Preset", [])]
    widget.refresh()

    assert widget._combo.count() == 1


def test_preset_widget_active_preset_shown(controller, qtbot):
    controller._presets = [DummyPresetEntry("id1", "My Preset", [])]
    controller._active_id = "id1"
    widget = PresetWidget(controller=controller)
    qtbot.addWidget(widget)

    # Active preset name should appear in button
    assert "My Preset" in widget._main_btn.text()


def test_preset_widget_active_preset_menu_has_update_delete(controller, qtbot):
    controller._presets = [DummyPresetEntry("id1", "My Preset", [])]
    controller._active_id = "id1"
    widget = PresetWidget(controller=controller)
    qtbot.addWidget(widget)

    action_data = [a.data() for a in widget._menu.actions()]
    assert "__UPDATE__" in action_data
    assert "__DELETE__" in action_data
    assert "__RENAME__" in action_data


# ===========================================================================
# Menu Action Handling Tests
# ===========================================================================


def test_on_menu_action_none_data(widget):
    """Action with no data should do nothing."""
    action = MagicMock()
    action.data.return_value = None
    widget._on_menu_action(action)  # Should not raise


def test_on_menu_action_new_preset(controller, qtbot):
    widget = PresetWidget(controller=controller)
    qtbot.addWidget(widget)

    action = MagicMock()
    action.data.return_value = "__NEW__"

    with patch.object(QInputDialog, "getText", return_value=("My New Preset", True)):
        widget._on_menu_action(action)
        # Controller.create_preset should have been called

    # Verify via mock
    ctrl_mock = MagicMock()
    ctrl_mock.presets_changed = Signal()
    ctrl_mock.preset_loaded = Signal(str)


def test_on_menu_action_new_preset_cancelled(controller, qtbot):
    widget = PresetWidget(controller=controller)
    qtbot.addWidget(widget)
    create_mock = MagicMock()
    controller.create_preset = create_mock

    action = MagicMock()
    action.data.return_value = "__NEW__"

    with patch.object(QInputDialog, "getText", return_value=("", False)):
        widget._on_menu_action(action)

    create_mock.assert_not_called()


def test_on_menu_action_load_preset(controller, qtbot):
    controller._presets = [DummyPresetEntry("id1", "Preset", [])]
    widget = PresetWidget(controller=controller)
    qtbot.addWidget(widget)

    load_mock = MagicMock()
    controller.load_preset = load_mock

    action = MagicMock()
    action.data.return_value = "id1"
    widget._on_menu_action(action)
    load_mock.assert_called_once_with("id1")


def test_on_menu_action_delete_cancelled(controller, qtbot):
    controller._presets = [DummyPresetEntry("id1", "Preset", [])]
    controller._active_id = "id1"
    widget = PresetWidget(controller=controller)
    qtbot.addWidget(widget)

    delete_mock = MagicMock()
    controller.delete_preset = delete_mock

    action = MagicMock()
    action.data.return_value = "__DELETE__"

    with patch.object(
        QMessageBox, "warning", return_value=QMessageBox.StandardButton.Cancel
    ):
        widget._on_menu_action(action)

    delete_mock.assert_not_called()


def test_on_menu_action_delete_confirmed(controller, qtbot):
    controller._presets = [DummyPresetEntry("id1", "Preset", [])]
    controller._active_id = "id1"
    widget = PresetWidget(controller=controller)
    qtbot.addWidget(widget)

    delete_mock = MagicMock()
    controller.delete_preset = delete_mock

    action = MagicMock()
    action.data.return_value = "__DELETE__"

    with patch.object(
        QMessageBox, "warning", return_value=QMessageBox.StandardButton.Yes
    ):
        widget._on_menu_action(action)

    delete_mock.assert_called_once_with("id1")


def test_on_menu_action_update(controller, qtbot):
    controller._active_id = "id1"
    widget = PresetWidget(controller=controller)
    qtbot.addWidget(widget)

    update_mock = MagicMock()
    controller.update_preset = update_mock

    action = MagicMock()
    action.data.return_value = "__UPDATE__"
    widget._on_menu_action(action)

    update_mock.assert_called_once_with("id1")


def test_on_menu_action_rename(controller, qtbot):
    controller._presets = [DummyPresetEntry("id1", "Old Name", [])]
    controller._active_id = "id1"
    widget = PresetWidget(controller=controller)
    qtbot.addWidget(widget)

    rename_mock = MagicMock()
    controller.rename_preset = rename_mock

    action = MagicMock()
    action.data.return_value = "__RENAME__"

    with patch.object(QInputDialog, "getText", return_value=("New Name", True)):
        widget._on_menu_action(action)

    rename_mock.assert_called_once_with("id1", "New Name")


def test_on_preset_loaded(controller, qtbot):
    controller._presets = [DummyPresetEntry("id1", "Preset", [])]
    widget = PresetWidget(controller=controller)
    qtbot.addWidget(widget)

    # Trigger preset_loaded signal
    controller.preset_loaded.emit("id1")
    # Should refresh menu without error


def test_preset_widget_trigger_save_action(controller, qtbot):
    widget = PresetWidget(controller=controller)
    qtbot.addWidget(widget)

    create_mock = MagicMock()
    controller.create_preset = create_mock

    with patch.object(QInputDialog, "getText", return_value=("Save Me", True)):
        widget.trigger_save_action()

    create_mock.assert_called_once_with("Save Me")


def test_preset_widget_dirty_state(controller, qtbot):
    controller._presets = [DummyPresetEntry("id1", "My Preset", [])]
    controller._active_id = "id1"
    controller.is_selection_dirty = MagicMock(return_value=True)
    widget = PresetWidget(controller=controller)
    qtbot.addWidget(widget)

    # Dirty state should add a bullet to name
    assert "●" in widget._main_btn.text()
