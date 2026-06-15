import abc
from pathlib import Path
from domain.smart_context.tree_item import TreeItem


class IDirectoryScanner(abc.ABC):
    """
    Interface cho directory scanning o Domain layer.
    """

    @abc.abstractmethod
    def scan_directory(self, root_path: Path) -> TreeItem:
        """Scan a directory recursively and build its TreeItem structure, respecting ignore rules."""
        pass
