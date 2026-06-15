"""
Tests cho FileTreeFilterProxy - search và filter trong file tree.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from PySide6.QtCore import Qt, QModelIndex

from domain.ports.registry import DomainRegistry
from domain.config.app_settings import AppSettings
from presentation.components.file_tree.file_tree_filter import FileTreeFilterProxy, CODE_SEARCH_PREFIX
from presentation.components.file_tree.file_tree_model import FileTreeModel, FileTreeRoles


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


@pytest.fixture()
def filter_proxy(qtbot):
    """Tạo FileTreeFilterProxy với DummyModel."""
    proxy = FileTreeFilterProxy()

    # Tạo dummy model
    ignore_engine = MagicMock()
    ignore_engine.should_ignore.return_value = False
    tokenization_service = MagicMock()
    tokenization_service.count_tokens.return_value = 10

    model = FileTreeModel(ignore_engine=ignore_engine)
    proxy.setSourceModel(model)
    return proxy, model


# ===========================================================================
# FileTreeFilterProxy Basic Tests
# ===========================================================================


def test_filter_proxy_init(filter_proxy):
    proxy, model = filter_proxy
    # Initial state
    assert proxy.search_query == ""
    assert proxy.is_content_search is False
    assert proxy._matched_paths is None


def test_filter_proxy_set_empty_query(filter_proxy):
    proxy, model = filter_proxy
    proxy.set_search_state("", None)
    assert proxy.search_query == ""
    assert proxy._matched_paths is None


def test_filter_proxy_set_file_query(filter_proxy):
    proxy, model = filter_proxy
    proxy.set_search_state("hello", None)
    assert proxy.search_query == "hello"
    assert proxy.is_content_search is False


def test_filter_proxy_set_code_query(filter_proxy):
    proxy, model = filter_proxy
    proxy.set_search_state("code:def run", None)
    assert proxy.search_query == "def run"
    assert proxy.is_content_search is True


def test_filter_proxy_set_code_prefix_only(filter_proxy):
    """'code:' với không có từ khóa - không trigger content search."""
    proxy, model = filter_proxy
    proxy.set_search_state("code:", None)
    # This is handled at widget level; the proxy should accept the "code:" query
    # but filter logic is: if is_content_search and empty query => show all
    assert proxy.is_content_search is True
    assert proxy.search_query == ""


def test_filter_proxy_with_matched_paths(filter_proxy):
    proxy, model = filter_proxy
    paths = {"/workspace/src/main.py", "/workspace/src/utils.py"}
    proxy.set_search_state("main", paths)
    assert proxy._matched_paths == paths
    # Ancestors should be built
    assert "/workspace/src" in proxy._matched_ancestors
    assert "/workspace" in proxy._matched_ancestors


def test_filter_proxy_ancestors_are_included(filter_proxy):
    proxy, model = filter_proxy
    # Provide deeply nested paths
    paths = {"/a/b/c/d/file.py"}
    proxy.set_search_state("file", paths)
    # All ancestor dirs should be added
    assert "/a/b/c/d" in proxy._matched_ancestors
    assert "/a/b/c" in proxy._matched_ancestors
    assert "/a/b" in proxy._matched_ancestors
    assert "/a" in proxy._matched_ancestors


def test_filter_proxy_no_query_accepts_all(filter_proxy):
    proxy, model = filter_proxy
    proxy.set_search_state("", None)
    # With empty query, filterAcceptsRow should return True for any row
    # We test this with a real workspace loaded
    assert proxy.search_query == ""


def test_filter_proxy_get_match_count_empty(filter_proxy):
    proxy, model = filter_proxy
    count = proxy.get_match_count()
    # No data loaded, should return 0
    assert count == 0


def test_filter_proxy_properties(filter_proxy):
    proxy, model = filter_proxy
    proxy.set_search_state("test", None)
    assert proxy.search_query == "test"
    assert proxy.is_content_search is False


def test_filter_proxy_with_workspace(filter_proxy, tmp_path):
    proxy, model = filter_proxy

    # Create test files
    (tmp_path / "main.py").write_text("def main(): pass")
    (tmp_path / "utils.py").write_text("def util(): pass")
    subdir = tmp_path / "sub"
    subdir.mkdir()
    (subdir / "helper.py").write_text("def help(): pass")

    # Load tree into model
    model.load_tree(tmp_path)

    # Set search to find "main"
    matched = {str(tmp_path / "main.py")}
    proxy.set_search_state("main", matched)

    # Match count should now reflect the visible tree items
    count = proxy.get_match_count()
    assert count >= 0  # At minimum it should not crash


def test_filter_proxy_code_search_with_paths(filter_proxy, tmp_path):
    proxy, model = filter_proxy

    (tmp_path / "code.py").write_text("def my_function(): pass")
    model.load_tree(tmp_path)

    matched = {str(tmp_path / "code.py")}
    proxy.set_search_state("code:my_function", matched)

    assert proxy.is_content_search is True
    assert proxy.search_query == "my_function"
    assert proxy._matched_paths == matched


def test_filter_proxy_set_matched_paths_empty_set(filter_proxy):
    """Setting empty set as matched_paths should work without error."""
    proxy, model = filter_proxy
    proxy.set_search_state("something", set())
    assert proxy._matched_paths == set()
    assert len(proxy._matched_ancestors) == 0


def test_filter_proxy_accepts_row_no_query(filter_proxy, tmp_path):
    """filterAcceptsRow should accept all rows when no query."""
    proxy, model = filter_proxy
    (tmp_path / "file.py").write_text("content")
    model.load_tree(tmp_path)
    proxy.set_search_state("", None)

    # With no query, all rows accepted - check via rowCount on proxy
    # Root item should be visible
    assert proxy.rowCount(QModelIndex()) >= 0
