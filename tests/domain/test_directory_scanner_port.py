"""Tests for domain/ports/directory_scanner.py - covers IDirectoryScanner ABC."""

from pathlib import Path
from typing import List, Optional
from unittest.mock import MagicMock

from domain.ports.directory_scanner import IDirectoryScanner
from domain.ports.ignore_engine_port import IIgnoreEngine
from domain.smart_context.tree_item import TreeItem


class DummyScanner(IDirectoryScanner):
    """Concrete implementation of IDirectoryScanner for testing purposes."""

    def scan_directory(
        self,
        root_path: Path,
        excluded_patterns: Optional[List[str]] = None,
        use_gitignore: bool = True,
    ) -> TreeItem:
        return TreeItem(label="root", path=str(root_path), is_dir=True)

    def scan_directory_shallow(
        self,
        root_path: Path,
        ignore_engine: IIgnoreEngine,
        depth: int = 1,
        excluded_patterns: Optional[List[str]] = None,
    ) -> TreeItem:
        return TreeItem(label="root", path=str(root_path), is_dir=True)

    def load_folder_children(
        self,
        node: TreeItem,
        ignore_engine: IIgnoreEngine,
        excluded_patterns: Optional[List[str]] = None,
        use_gitignore: bool = True,
        workspace_root: Optional[Path] = None,
    ) -> None:
        pass


def test_dummy_scanner_scan_directory() -> None:
    """DummyScanner.scan_directory returns a valid TreeItem."""
    scanner = DummyScanner()
    root = Path(".")
    result = scanner.scan_directory(root)
    assert result.is_dir is True
    assert result.label == "root"


def test_dummy_scanner_scan_directory_with_options() -> None:
    """DummyScanner.scan_directory accepts optional parameters."""
    scanner = DummyScanner()
    result = scanner.scan_directory(
        Path("/tmp"),
        excluded_patterns=["*.pyc"],
        use_gitignore=False,
    )
    assert result.is_dir is True


def test_dummy_scanner_scan_directory_shallow() -> None:
    """DummyScanner.scan_directory_shallow returns a valid TreeItem."""
    scanner = DummyScanner()
    mock_engine = MagicMock(spec=IIgnoreEngine)
    result = scanner.scan_directory_shallow(Path("."), mock_engine)
    assert result.is_dir is True
    assert result.label == "root"


def test_dummy_scanner_scan_directory_shallow_with_options() -> None:
    """DummyScanner.scan_directory_shallow accepts depth and excluded_patterns."""
    scanner = DummyScanner()
    mock_engine = MagicMock(spec=IIgnoreEngine)
    result = scanner.scan_directory_shallow(
        Path("."),
        mock_engine,
        depth=3,
        excluded_patterns=["node_modules"],
    )
    assert result.is_dir is True


def test_dummy_scanner_load_folder_children() -> None:
    """DummyScanner.load_folder_children runs without errors."""
    scanner = DummyScanner()
    mock_engine = MagicMock(spec=IIgnoreEngine)
    node = TreeItem(label="node", path=".", is_dir=True)
    # Should not raise
    scanner.load_folder_children(node, mock_engine)


def test_dummy_scanner_load_folder_children_with_options() -> None:
    """DummyScanner.load_folder_children accepts all optional parameters."""
    scanner = DummyScanner()
    mock_engine = MagicMock(spec=IIgnoreEngine)
    node = TreeItem(label="node", path=".", is_dir=True)
    scanner.load_folder_children(
        node,
        mock_engine,
        excluded_patterns=["*.log"],
        use_gitignore=False,
        workspace_root=Path("/workspace"),
    )
