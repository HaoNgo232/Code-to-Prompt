"""
Tests cho TagChipsWidget, ChipWidget, và FlowLayout.
"""

import pytest
from unittest.mock import MagicMock
from PySide6.QtCore import Qt, QRect, QSize

from domain.ports.registry import DomainRegistry
from domain.config.app_settings import AppSettings
from presentation.components.tag_chips_widget import (
    TagChipsWidget,
    ChipWidget,
    FlowLayout,
)


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
# FlowLayout Tests
# ===========================================================================


def test_flow_layout_empty(qtbot):
    from PySide6.QtWidgets import QWidget

    container = QWidget()
    layout = FlowLayout(container, spacing=8)
    assert layout.count() == 0


def test_flow_layout_add_item(qtbot):
    from PySide6.QtWidgets import QWidget, QPushButton

    container = QWidget()
    layout = FlowLayout(container, spacing=8)
    btn = QPushButton("test")
    layout.addWidget(btn)
    assert layout.count() == 1


def test_flow_layout_item_at(qtbot):
    from PySide6.QtWidgets import QWidget, QPushButton

    container = QWidget()
    layout = FlowLayout(container, spacing=8)
    btn = QPushButton("test")
    layout.addWidget(btn)
    item = layout.itemAt(0)
    assert item is not None


def test_flow_layout_item_at_invalid(qtbot):
    from PySide6.QtWidgets import QWidget

    container = QWidget()
    layout = FlowLayout(container, spacing=8)
    assert layout.itemAt(0) is None
    assert layout.itemAt(-1) is None


def test_flow_layout_take_at(qtbot):
    from PySide6.QtWidgets import QWidget, QPushButton

    container = QWidget()
    layout = FlowLayout(container, spacing=8)
    btn = QPushButton("test")
    layout.addWidget(btn)
    item = layout.takeAt(0)
    assert item is not None
    assert layout.count() == 0


def test_flow_layout_has_height_for_width(qtbot):
    from PySide6.QtWidgets import QWidget

    container = QWidget()
    layout = FlowLayout(container, spacing=8)
    assert layout.hasHeightForWidth() is True


def test_flow_layout_height_for_width_empty(qtbot):
    from PySide6.QtWidgets import QWidget

    container = QWidget()
    layout = FlowLayout(container, spacing=8)
    height = layout.heightForWidth(300)
    assert height >= 0


def test_flow_layout_size_hint(qtbot):
    from PySide6.QtWidgets import QWidget

    container = QWidget()
    layout = FlowLayout(container, spacing=8)
    size = layout.sizeHint()
    assert isinstance(size, QSize)


def test_flow_layout_minimum_size(qtbot):
    from PySide6.QtWidgets import QWidget

    container = QWidget()
    layout = FlowLayout(container, spacing=8)
    size = layout.minimumSize()
    assert isinstance(size, QSize)


def test_flow_layout_expanding_directions(qtbot):
    from PySide6.QtWidgets import QWidget

    container = QWidget()
    layout = FlowLayout(container, spacing=8)
    result = layout.expandingDirections()
    assert result == Qt.Orientation(0)


def test_flow_layout_set_geometry(qtbot):
    from PySide6.QtWidgets import QWidget, QPushButton

    container = QWidget()
    container.setFixedSize(400, 200)
    qtbot.addWidget(container)
    layout = FlowLayout(container, spacing=8)
    btn = QPushButton("test chip")
    btn.setParent(container)
    layout.addWidget(btn)
    layout.setGeometry(QRect(0, 0, 400, 200))
    # Should not raise


# ===========================================================================
# ChipWidget Tests
# ===========================================================================


def test_chip_widget_init(qtbot):
    chip = ChipWidget("python")
    qtbot.addWidget(chip)
    assert chip.text == "python"


def test_chip_widget_removed_signal(qtbot):
    chip = ChipWidget("node_modules")
    qtbot.addWidget(chip)

    emitted = []
    chip.removed.connect(lambda t: emitted.append(t))

    # Find and click the close button
    from PySide6.QtWidgets import QPushButton

    close_btn = chip.findChild(QPushButton)
    assert close_btn is not None
    close_btn.click()
    assert emitted == ["node_modules"]


def test_chip_widget_hover_style(qtbot):
    chip = ChipWidget("dist")
    qtbot.addWidget(chip)
    chip.show()

    chip.enterEvent(MagicMock())
    assert chip._hovered is True

    chip.leaveEvent(MagicMock())
    assert chip._hovered is False


# ===========================================================================
# TagChipsWidget Tests
# ===========================================================================


def test_tag_chips_widget_init_empty(qtbot):
    widget = TagChipsWidget()
    qtbot.addWidget(widget)
    assert widget.get_patterns() == []


def test_tag_chips_widget_init_with_patterns(qtbot):
    patterns = ["node_modules", "dist", "__pycache__"]
    widget = TagChipsWidget(patterns=patterns)
    qtbot.addWidget(widget)
    assert set(widget.get_patterns()) == set(patterns)


def test_tag_chips_widget_add_pattern(qtbot):
    widget = TagChipsWidget()
    qtbot.addWidget(widget)

    result = widget.add_pattern("build")
    assert result is True
    assert "build" in widget.get_patterns()


def test_tag_chips_widget_add_duplicate_pattern(qtbot):
    widget = TagChipsWidget(["node_modules"])
    qtbot.addWidget(widget)

    result = widget.add_pattern("node_modules")
    assert result is False  # Duplicate not added


def test_tag_chips_widget_add_empty_pattern(qtbot):
    widget = TagChipsWidget()
    qtbot.addWidget(widget)

    result = widget.add_pattern("")
    assert result is False


def test_tag_chips_widget_add_whitespace_pattern(qtbot):
    widget = TagChipsWidget()
    qtbot.addWidget(widget)

    result = widget.add_pattern("   ")
    assert result is False


def test_tag_chips_widget_remove_pattern(qtbot):
    widget = TagChipsWidget(["node_modules", "dist"])
    qtbot.addWidget(widget)

    result = widget.remove_pattern("node_modules")
    assert result is True
    assert "node_modules" not in widget.get_patterns()


def test_tag_chips_widget_remove_nonexistent_pattern(qtbot):
    widget = TagChipsWidget(["node_modules"])
    qtbot.addWidget(widget)

    result = widget.remove_pattern("build")
    assert result is False


def test_tag_chips_widget_set_patterns(qtbot):
    widget = TagChipsWidget(["old"])
    qtbot.addWidget(widget)

    new_patterns = ["new1", "new2"]
    widget.set_patterns(new_patterns)
    assert widget.get_patterns() == new_patterns


def test_tag_chips_widget_clear_all(qtbot):
    widget = TagChipsWidget(["a", "b", "c"])
    qtbot.addWidget(widget)

    emitted = []
    widget.patterns_changed.connect(lambda p: emitted.append(p))

    widget.clear_all()
    assert widget.get_patterns() == []
    assert len(emitted) == 1
    assert emitted[0] == []


def test_tag_chips_widget_clear_all_empty(qtbot):
    widget = TagChipsWidget()
    qtbot.addWidget(widget)
    # clear_all on empty widget should be no-op
    widget.clear_all()
    assert widget.get_patterns() == []


def test_tag_chips_widget_undo(qtbot):
    widget = TagChipsWidget(["a"])
    qtbot.addWidget(widget)

    # Use _add_from_input which calls _save_state_to_history
    widget._input.setText("b")
    widget._add_from_input()
    assert "b" in widget.get_patterns()

    widget.undo()
    assert "b" not in widget.get_patterns()
    assert "a" in widget.get_patterns()


def test_tag_chips_widget_undo_empty_history(qtbot):
    widget = TagChipsWidget(["a"])
    qtbot.addWidget(widget)
    # No history, undo should be no-op
    widget.undo()
    assert "a" in widget.get_patterns()


def test_tag_chips_widget_patterns_changed_on_add(qtbot):
    widget = TagChipsWidget()
    qtbot.addWidget(widget)

    emitted = []
    widget.patterns_changed.connect(lambda p: emitted.append(p))

    widget.add_pattern("test")
    assert len(emitted) == 1
    assert "test" in emitted[0]


def test_tag_chips_widget_patterns_changed_on_remove(qtbot):
    widget = TagChipsWidget(["node_modules"])
    qtbot.addWidget(widget)

    emitted = []
    widget.patterns_changed.connect(lambda p: emitted.append(p))

    widget.remove_pattern("node_modules")
    assert len(emitted) == 1
    assert "node_modules" not in emitted[0]


def test_tag_chips_widget_add_from_input(qtbot):
    widget = TagChipsWidget()
    qtbot.addWidget(widget)

    emitted = []
    widget.patterns_changed.connect(lambda p: emitted.append(p))

    widget._input.setText("new_pattern")
    widget._add_from_input()

    assert "new_pattern" in widget.get_patterns()
    assert len(emitted) == 1


def test_tag_chips_widget_add_multiple_from_input(qtbot):
    """Test batch add via comma-separated input."""
    widget = TagChipsWidget()
    qtbot.addWidget(widget)

    widget._input.setText("a, b, c")
    widget._add_from_input()

    patterns = widget.get_patterns()
    assert "a" in patterns
    assert "b" in patterns
    assert "c" in patterns


def test_tag_chips_widget_add_from_input_empty(qtbot):
    widget = TagChipsWidget()
    qtbot.addWidget(widget)

    emitted = []
    widget.patterns_changed.connect(lambda p: emitted.append(p))

    widget._input.setText("")
    widget._add_from_input()

    assert len(emitted) == 0


def test_tag_chips_widget_add_from_input_duplicate(qtbot):
    widget = TagChipsWidget(["existing"])
    qtbot.addWidget(widget)

    widget._input.setText("existing")
    widget._add_from_input()

    # Duplicate should not be added
    patterns = widget.get_patterns()
    assert patterns.count("existing") == 1


def test_tag_chips_widget_history_limit(qtbot):
    widget = TagChipsWidget()
    qtbot.addWidget(widget)

    # Add 55 items to exceed the 50 history limit
    for i in range(55):
        widget.add_pattern(f"pattern_{i}")

    # History should be capped at 50
    assert len(widget._history) <= 50


def test_tag_chips_widget_remove_by_chip_signal(qtbot):
    widget = TagChipsWidget(["node_modules", "dist"])
    qtbot.addWidget(widget)
    widget.show()

    emitted = []
    widget.patterns_changed.connect(lambda p: emitted.append(p))

    # Trigger remove via internal callback
    widget._remove_pattern("node_modules")

    assert "node_modules" not in widget.get_patterns()
    assert len(emitted) == 1
