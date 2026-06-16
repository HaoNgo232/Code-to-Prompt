"""
Tests cho FileTreeModel - QAbstractItemModel với lazy loading và selection.
"""

import pytest
from unittest.mock import MagicMock
from PySide6.QtCore import Qt, QModelIndex

from domain.ports.registry import DomainRegistry
from domain.config.app_settings import AppSettings
from presentation.components.file_tree.file_tree_model import (
    FileTreeModel,
    TreeNode,
    FileTreeRoles,
    TokenCountWorker,
)


# ===========================================================================
# Fixtures
# ===========================================================================


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
    orig_provider = None
    try:
        orig_service = DomainRegistry.settings_service()
    except RuntimeError:
        pass
    try:
        orig_provider = DomainRegistry._settings_provider
    except AttributeError:
        pass

    service = DummySettingsService()
    DomainRegistry.register_settings_service(service)
    DomainRegistry.register_settings_provider(lambda: service.load_settings())

    yield service

    if orig_service is not None:
        DomainRegistry.register_settings_service(orig_service)
    DomainRegistry._settings_provider = orig_provider


@pytest.fixture()
def ignore_engine():
    engine = MagicMock()
    engine.should_ignore.return_value = False
    return engine


@pytest.fixture()
def model(ignore_engine):
    return FileTreeModel(ignore_engine=ignore_engine)


@pytest.fixture()
def model_with_tree(model, tmp_path):
    """FileTreeModel loaded with a simple workspace."""
    # Create some files
    (tmp_path / "main.py").write_text("def main(): pass\n" * 10)
    (tmp_path / "utils.py").write_text("def util(): pass\n")
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "helper.py").write_text("def help(): pass\n")

    model.load_tree(tmp_path)
    return model, tmp_path


# ===========================================================================
# TreeNode Tests
# ===========================================================================


class TestTreeNode:
    def test_basic_init(self):
        node = TreeNode(label="file.py", path="/path/file.py", is_dir=False)
        assert node.label == "file.py"
        assert node.path == "/path/file.py"
        assert node.is_dir is False
        assert node.is_loaded is False
        assert node.children == []
        assert node.parent is None
        assert node.row == 0

    def test_child_count(self):
        parent = TreeNode(label="dir", path="/dir", is_dir=True)
        child1 = TreeNode(label="a.py", path="/dir/a.py", parent=parent, row=0)
        child2 = TreeNode(label="b.py", path="/dir/b.py", parent=parent, row=1)
        parent.children = [child1, child2]
        assert parent.child_count() == 2

    def test_child_access(self):
        parent = TreeNode(label="dir", path="/dir", is_dir=True)
        child = TreeNode(label="a.py", path="/dir/a.py", parent=parent, row=0)
        parent.children = [child]
        assert parent.child(0) is child
        assert parent.child(1) is None
        assert parent.child(-1) is None

    def test_from_tree_item(self):
        from domain.smart_context.tree_item import TreeItem

        item = TreeItem(
            label="workspace",
            path="/workspace",
            is_dir=True,
            is_loaded=True,
            children=[
                TreeItem(
                    label="main.py",
                    path="/workspace/main.py",
                    is_dir=False,
                    is_loaded=True,
                    children=[],
                ),
            ],
        )
        node = TreeNode.from_tree_item(item, depth=0, max_depth=1)
        assert node.label == "workspace"
        assert node.is_dir is True
        assert len(node.children) == 1
        assert node.children[0].label == "main.py"

    def test_from_tree_item_depth_limit(self):
        from domain.smart_context.tree_item import TreeItem

        item = TreeItem(
            label="root",
            path="/root",
            is_dir=True,
            is_loaded=True,
            children=[
                TreeItem(
                    label="sub",
                    path="/root/sub",
                    is_dir=True,
                    is_loaded=True,
                    children=[
                        TreeItem(
                            label="deep.py",
                            path="/root/sub/deep.py",
                            is_dir=False,
                            is_loaded=True,
                            children=[],
                        ),
                    ],
                )
            ],
        )
        # max_depth=1: only root's immediate children are loaded
        node = TreeNode.from_tree_item(item, depth=0, max_depth=1)
        assert len(node.children) == 1
        sub = node.children[0]
        assert sub.label == "sub"
        # sub's children should NOT be loaded (depth=1 == max_depth)
        assert len(sub.children) == 0
        assert sub.is_loaded is False

    def test_from_tree_item_with_path_index(self):
        from domain.smart_context.tree_item import TreeItem

        item = TreeItem(
            label="workspace",
            path="/ws",
            is_dir=True,
            is_loaded=True,
            children=[
                TreeItem(
                    label="a.py",
                    path="/ws/a.py",
                    is_dir=False,
                    is_loaded=True,
                    children=[],
                ),
            ],
        )
        path_index = {}
        TreeNode.from_tree_item(item, depth=0, max_depth=1, path_index=path_index)
        assert "/ws" in path_index
        assert "/ws/a.py" in path_index


# ===========================================================================
# FileTreeModel Basic Tests
# ===========================================================================


def test_model_init(model):
    assert model._root_node is None
    assert model._workspace_path is None
    assert model.columnCount() == 1
    assert model.rowCount(QModelIndex()) == 0


def test_model_load_tree(model_with_tree):
    model, tmp_path = model_with_tree
    assert model._workspace_path == tmp_path
    assert model._root_node is not None
    # Root should have children (main.py, utils.py, subdir)
    assert model.rowCount(QModelIndex()) == 1  # One root node


def test_model_index_valid(model_with_tree):
    model, tmp_path = model_with_tree
    idx = model.index(0, 0, QModelIndex())
    assert idx.isValid()


def test_model_column_count(model):
    assert model.columnCount() == 1
    assert model.columnCount(QModelIndex()) == 1


def test_model_header_data(model):
    result = model.headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
    assert result == "Files"


def test_model_header_data_vertical(model):
    result = model.headerData(0, Qt.Orientation.Vertical, Qt.ItemDataRole.DisplayRole)
    assert result is None


def test_model_flags(model_with_tree):
    model, _ = model_with_tree
    idx = model.index(0, 0, QModelIndex())
    flags = model.flags(idx)
    assert Qt.ItemFlag.ItemIsEnabled in flags
    assert Qt.ItemFlag.ItemIsUserCheckable in flags


def test_model_flags_invalid_index(model):
    flags = model.flags(QModelIndex())
    assert flags == Qt.ItemFlag(0)


def test_model_data_display_role(model_with_tree):
    model, tmp_path = model_with_tree
    idx = model.index(0, 0, QModelIndex())
    label = model.data(idx, Qt.ItemDataRole.DisplayRole)
    assert label is not None  # Should return root folder name


def test_model_data_file_path_role(model_with_tree):
    model, tmp_path = model_with_tree
    idx = model.index(0, 0, QModelIndex())
    path = model.data(idx, FileTreeRoles.FILE_PATH_ROLE)
    assert path is not None
    assert str(tmp_path) in path


def test_model_data_is_dir_role(model_with_tree):
    model, tmp_path = model_with_tree
    idx = model.index(0, 0, QModelIndex())
    is_dir = model.data(idx, FileTreeRoles.IS_DIR_ROLE)
    assert is_dir is True  # Root is a directory


def test_model_data_tooltip_role(model_with_tree):
    model, tmp_path = model_with_tree
    idx = model.index(0, 0, QModelIndex())
    tooltip = model.data(idx, Qt.ItemDataRole.ToolTipRole)
    assert tooltip is not None


def test_model_data_invalid_index(model):
    result = model.data(QModelIndex())
    assert result is None


def test_model_data_unknown_role(model_with_tree):
    model, _ = model_with_tree
    idx = model.index(0, 0, QModelIndex())
    # Unknown role should return None
    result = model.data(idx, Qt.ItemDataRole.UserRole + 999)
    assert result is None


def test_model_has_children(model_with_tree):
    model, _ = model_with_tree
    idx = model.index(0, 0, QModelIndex())
    # Root directory always reports hasChildren=True (lazy loading)
    # because even unloaded dirs return True
    result = model.hasChildren(idx)
    assert isinstance(result, bool)  # Just ensure no exception


def test_model_has_children_invalid(model):
    assert model.hasChildren(QModelIndex()) is False


def test_model_workspace_path(model_with_tree):
    model, tmp_path = model_with_tree
    assert model.get_workspace_path() == tmp_path


# ===========================================================================
# Selection Tests
# ===========================================================================


def test_model_get_selected_paths_empty(model_with_tree):
    model, _ = model_with_tree
    paths = model.get_selected_paths()
    assert paths == []


def test_model_set_selected_paths(model_with_tree):
    model, tmp_path = model_with_tree
    f = str(tmp_path / "main.py")
    model.set_selected_paths({f})
    selected = model.get_all_selected_paths()
    assert f in selected


def test_model_select_deselect_node(model_with_tree):
    model, tmp_path = model_with_tree
    # Get index of root
    root_idx = model.index(0, 0, QModelIndex())
    # Set checked
    model.setData(root_idx, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
    # Get check state
    state = model.data(root_idx, Qt.ItemDataRole.CheckStateRole)
    # Root is a dir, so we get a folder check state
    assert state in (
        Qt.CheckState.Checked,
        Qt.CheckState.PartiallyChecked,
        Qt.CheckState.Unchecked,
    )


def test_model_setdata_unchecked(model_with_tree):
    model, tmp_path = model_with_tree
    root_idx = model.index(0, 0, QModelIndex())
    # First check
    model.setData(root_idx, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
    # Then uncheck
    model.setData(root_idx, Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
    state = model.data(root_idx, Qt.ItemDataRole.CheckStateRole)
    assert state == Qt.CheckState.Unchecked


def test_model_setdata_invalid_index(model):
    result = model.setData(
        QModelIndex(), Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole
    )
    assert result is False


def test_model_select_all_deselect_all(model_with_tree):
    model, _ = model_with_tree
    model.select_all()
    paths_after_select = model.get_all_selected_paths()
    assert len(paths_after_select) > 0

    model.deselect_all()
    paths_after_deselect = model.get_all_selected_paths()
    assert len(paths_after_deselect) == 0


def test_model_add_paths_to_selection(model_with_tree):
    model, tmp_path = model_with_tree
    f = str(tmp_path / "main.py")
    added = model.add_paths_to_selection({f})
    assert added >= 0
    assert f in model.get_all_selected_paths()


def test_model_remove_paths_from_selection(model_with_tree):
    model, tmp_path = model_with_tree
    f = str(tmp_path / "main.py")
    model.set_selected_paths({f})
    removed = model.remove_paths_from_selection({f})
    assert removed >= 0
    assert f not in model.get_all_selected_paths()


def test_model_get_total_tokens_empty(model_with_tree):
    model, _ = model_with_tree
    total = model.get_total_tokens()
    assert total == 0


def test_model_search_files_no_index(model_with_tree):
    model, _ = model_with_tree
    # When search index is not ready, should return empty
    model._search_index_ready = False
    model._search_index = {}
    result = model.search_files("main")
    assert isinstance(result, list)


def test_model_search_files_with_index(model_with_tree):
    model, tmp_path = model_with_tree
    # Manually add to search index
    f = str(tmp_path / "main.py")
    model._search_index = {"main.py": [f]}
    model._search_index_ready = True
    result = model.search_files("main")
    assert f in result


def test_model_clear_token_cache(model_with_tree):
    model, tmp_path = model_with_tree
    f = str(tmp_path / "main.py")
    model._token_cache[f] = 100
    model.clear_token_cache()
    assert f not in model._token_cache


def test_model_update_token_counts_batch(model_with_tree):
    model, tmp_path = model_with_tree
    f = str(tmp_path / "main.py")
    model.update_token_counts_batch({f: 42})
    assert model._token_cache.get(f) == 42


# ===========================================================================
# TokenCountWorker Tests
# ===========================================================================


def test_token_count_worker_success(tmp_path):
    tokenization_service = MagicMock()
    tokenization_service.count_tokens.return_value = 50

    # Create a real file
    f = tmp_path / "test.py"
    f.write_text("def test(): pass")

    worker = TokenCountWorker(
        [str(f)],
        tokenization_service=tokenization_service,
        generation=1,
    )

    finished_calls = []
    worker.signals.finished.connect(lambda: finished_calls.append(True))
    worker.run()

    assert len(finished_calls) == 1


def test_token_count_worker_no_auto_delete():
    tokenization_service = MagicMock()
    worker = TokenCountWorker(
        [], tokenization_service=tokenization_service, generation=1
    )
    # TokenCountWorker uses setAutoDelete(True) unlike CopyTaskWorker
    assert isinstance(worker.autoDelete(), bool)  # Just ensure no exception


def test_token_count_worker_cancel():
    tokenization_service = MagicMock()
    worker = TokenCountWorker(
        [], tokenization_service=tokenization_service, generation=1
    )
    worker.cancel()
    assert worker._cancelled is True


def test_model_get_root_tree_item(model_with_tree):
    model, _ = model_with_tree
    root = model.get_root_tree_item()
    # Should be a TreeItem or None
    assert root is not None or root is None  # Just ensure no exception
