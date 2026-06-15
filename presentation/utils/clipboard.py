import logging
from PySide6.QtGui import QGuiApplication

logger = logging.getLogger(__name__)


def copy_to_clipboard(text: str) -> tuple[bool, str]:
    """
    Copy text to system clipboard using QGuiApplication.

    Args:
        text: Text to copy

    Returns:
        (success, error_message)
    """
    try:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
            return True, ""
        return False, "Clipboard not available"
    except Exception as e:
        logger.exception("Failed to copy to clipboard")
        return False, str(e)
