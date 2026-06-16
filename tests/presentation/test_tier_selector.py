"""
Tests cho TierSelector component.
"""

from PySide6.QtCore import Qt
from presentation.components.tier_selector import TierSelector


def test_tier_selector_initial_state(qtbot):
    # Default is lite
    selector = TierSelector()
    qtbot.addWidget(selector)
    assert selector.get_tier() == "lite"
    assert selector._lite_btn.property("active") == "true"
    assert selector._pro_btn.property("active") == "false"

    # Initial pro
    selector_pro = TierSelector("pro")
    qtbot.addWidget(selector_pro)
    assert selector_pro.get_tier() == "pro"
    assert selector_pro._lite_btn.property("active") == "false"
    assert selector_pro._pro_btn.property("active") == "true"

    # Invalid initial value falls back to lite
    selector_inv = TierSelector("invalid")
    qtbot.addWidget(selector_inv)
    assert selector_inv.get_tier() == "lite"


def test_tier_selector_click(qtbot):
    selector = TierSelector()
    qtbot.addWidget(selector)

    # Track signal emission
    emitted = []
    selector.tier_changed.connect(lambda t: emitted.append(t))

    # Click PRO
    qtbot.mouseClick(selector._pro_btn, Qt.MouseButton.LeftButton)
    assert selector.get_tier() == "pro"
    assert emitted == ["pro"]
    assert selector._lite_btn.property("active") == "false"
    assert selector._pro_btn.property("active") == "true"

    # Click LITE
    qtbot.mouseClick(selector._lite_btn, Qt.MouseButton.LeftButton)
    assert selector.get_tier() == "lite"
    assert emitted == ["pro", "lite"]
    assert selector._lite_btn.property("active") == "true"
    assert selector._pro_btn.property("active") == "false"


def test_tier_selector_set_tier(qtbot):
    selector = TierSelector()
    qtbot.addWidget(selector)

    # set_tier without emit
    emitted = []
    selector.tier_changed.connect(lambda t: emitted.append(t))

    selector.set_tier("pro")
    assert selector.get_tier() == "pro"
    assert len(emitted) == 0

    # set_tier with emit
    selector.set_tier("lite", emit=True)
    assert selector.get_tier() == "lite"
    assert emitted == ["lite"]

    # set same tier should return early
    selector.set_tier("lite", emit=True)
    assert len(emitted) == 1

    # set invalid tier should return early
    selector.set_tier("invalid", emit=True)
    assert selector.get_tier() == "lite"
    assert len(emitted) == 1
