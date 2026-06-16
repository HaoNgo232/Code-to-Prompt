"""
Tests cho EditPatternsDialog.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton
from presentation.components.dialogs.edit_patterns_dialog import EditPatternsDialog


def test_edit_patterns_dialog_initial_state(qtbot):
    patterns = ["node_modules", "dist", "   ", "temp"]
    dialog = EditPatternsDialog(patterns)
    qtbot.addWidget(dialog)
    dialog.show()

    # Editor should contain non-empty patterns joined by newline
    # wait, edit_patterns_dialog does not filter during init: self._editor.setPlainText("\n".join(self._initial_patterns))
    assert dialog._editor.toPlainText() == "node_modules\ndist\n   \ntemp"

    # get_patterns filters empty and strips whitespace
    res = dialog.get_patterns()
    assert res == ["node_modules", "dist", "temp"]


def test_edit_patterns_dialog_cancel(qtbot):
    dialog = EditPatternsDialog([])
    qtbot.addWidget(dialog)
    dialog.show()

    cancel_btn = None
    for btn in dialog.findChildren(QPushButton):
        if btn.text() == "Cancel":
            cancel_btn = btn
            break

    assert cancel_btn is not None

    # Click cancel should reject the dialog
    with qtbot.waitSignal(dialog.rejected):
        qtbot.mouseClick(cancel_btn, Qt.MouseButton.LeftButton)


def test_edit_patterns_dialog_apply(qtbot):
    dialog = EditPatternsDialog(["old"])
    qtbot.addWidget(dialog)
    dialog.show()

    # Edit the text
    dialog._editor.setPlainText("new_pattern1\n\n  new_pattern2  \n")

    apply_btn = None
    for btn in dialog.findChildren(QPushButton):
        if btn.text() == "Apply Changes":
            apply_btn = btn
            break

    assert apply_btn is not None

    # Click apply should accept the dialog
    with qtbot.waitSignal(dialog.accepted):
        qtbot.mouseClick(apply_btn, Qt.MouseButton.LeftButton)

    assert dialog.get_patterns() == ["new_pattern1", "new_pattern2"]
