"""
Tests cho các UI components nhỏ: ToggleSwitch, create_colored_icon, etc.
"""

import pytest
from unittest.mock import MagicMock

from PySide6.QtCore import Qt, QSize

from domain.ports.registry import DomainRegistry
from domain.config.app_settings import AppSettings
from presentation.components.toggle_switch import ToggleSwitch
from presentation.components.qt_utils import create_colored_icon


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
# ToggleSwitch Tests
# ===========================================================================


def test_toggle_switch_init_unchecked(qtbot):
    switch = ToggleSwitch(checked=False)
    qtbot.addWidget(switch)
    assert switch.isChecked() is False


def test_toggle_switch_init_checked(qtbot):
    switch = ToggleSwitch(checked=True)
    qtbot.addWidget(switch)
    assert switch.isChecked() is True


def test_toggle_switch_set_checked(qtbot):
    switch = ToggleSwitch(checked=False)
    qtbot.addWidget(switch)
    switch.setChecked(True)
    assert switch.isChecked() is True


def test_toggle_switch_set_checked_no_change(qtbot):
    switch = ToggleSwitch(checked=True)
    qtbot.addWidget(switch)
    # Setting same state should not cause issues
    switch.setChecked(True)
    assert switch.isChecked() is True


def test_toggle_switch_toggle(qtbot):
    switch = ToggleSwitch(checked=False)
    qtbot.addWidget(switch)
    emitted = []
    switch.toggled.connect(lambda v: emitted.append(v))
    switch.toggle()
    assert switch.isChecked() is True
    assert emitted == [True]


def test_toggle_switch_toggle_twice(qtbot):
    switch = ToggleSwitch(checked=False)
    qtbot.addWidget(switch)
    emitted = []
    switch.toggled.connect(lambda v: emitted.append(v))
    switch.toggle()
    switch.toggle()
    assert switch.isChecked() is False
    assert emitted == [True, False]


def test_toggle_switch_size_hint(qtbot):
    switch = ToggleSwitch()
    qtbot.addWidget(switch)
    hint = switch.sizeHint()
    assert hint == QSize(ToggleSwitch.WIDTH, ToggleSwitch.HEIGHT)


def test_toggle_switch_mouse_press(qtbot):
    switch = ToggleSwitch(checked=False)
    qtbot.addWidget(switch)
    switch.show()
    emitted = []
    switch.toggled.connect(lambda v: emitted.append(v))
    qtbot.mouseClick(switch, Qt.MouseButton.LeftButton)
    assert switch.isChecked() is True
    assert emitted == [True]


def test_toggle_switch_hover_events(qtbot):
    switch = ToggleSwitch(checked=False)
    qtbot.addWidget(switch)
    switch.show()
    # Simulate enter event
    switch._hovered = False
    switch.enterEvent(MagicMock())
    assert switch._hovered is True
    # Simulate leave event
    switch.leaveEvent(MagicMock())
    assert switch._hovered is False


def test_toggle_switch_paint_event(qtbot):
    """Just ensure paintEvent doesn't crash."""
    switch = ToggleSwitch(checked=False)
    qtbot.addWidget(switch)
    switch.show()
    switch.update()
    qtbot.wait(50)


def test_toggle_switch_paint_event_checked(qtbot):
    """Test paint with checked=True."""
    switch = ToggleSwitch(checked=True)
    qtbot.addWidget(switch)
    switch.show()
    switch.update()
    qtbot.wait(50)


def test_toggle_switch_knob_position(qtbot):
    switch = ToggleSwitch(checked=False)
    qtbot.addWidget(switch)
    # Unchecked: knob should be at KNOB_MARGIN
    assert switch._get_knob_position() == float(ToggleSwitch.KNOB_MARGIN)


def test_toggle_switch_set_knob_position(qtbot):
    switch = ToggleSwitch(checked=False)
    qtbot.addWidget(switch)
    switch._set_knob_position(20.0)
    assert switch._knob_x == 20.0


# ===========================================================================
# create_colored_icon Tests
# ===========================================================================


def test_create_colored_icon_nonexistent_file(qtbot):
    """With nonexistent SVG file, fallback to QIcon(path) which is empty icon."""
    icon = create_colored_icon("/nonexistent/icon.svg", "#FF0000")
    # Should not raise, returns empty QIcon as fallback
    assert icon is not None


def test_create_colored_icon_with_valid_svg(qtbot, tmp_path):
    """Test with a real SVG file containing currentColor."""
    svg_path = tmp_path / "test.svg"
    svg_path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24">'
        '<path stroke="currentColor" d="M0 0h24v24H0z"/>'
        "</svg>",
        encoding="utf-8",
    )
    icon = create_colored_icon(str(svg_path), "#7C6FFF")
    assert icon is not None
    assert not icon.isNull()


def test_create_colored_icon_with_black_stroke(qtbot, tmp_path):
    """Test SVG with black stroke color replacement."""
    svg_path = tmp_path / "test.svg"
    svg_path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24">'
        '<path stroke="black" d="M0 0h24v24H0z"/>'
        "</svg>",
        encoding="utf-8",
    )
    icon = create_colored_icon(str(svg_path), "#FF0000")
    assert icon is not None


def test_create_colored_icon_with_path_no_stroke(qtbot, tmp_path):
    """Test SVG with path but no explicit stroke (should add stroke attribute)."""
    svg_path = tmp_path / "test.svg"
    svg_path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24">'
        '<path d="M0 0h24v24H0z"/>'
        "</svg>",
        encoding="utf-8",
    )
    icon = create_colored_icon(str(svg_path), "#00FF00")
    assert icon is not None
