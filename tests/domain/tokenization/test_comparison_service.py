"""
Test Token Comparison Service.

Các test này mô tả contract cho service thuần Python dùng bởi token counter UI.
"""

from concurrent.futures import ThreadPoolExecutor
from time import perf_counter

from domain.tokenization.comparison_service import (
    TokenComparison,
    compare_token_counts,
)


def _write_python_file(path, index: int = 0) -> None:
    """Tạo file Python có body đủ dài để Smart Context có thể tiết kiệm token."""
    path.write_text(
        "\n".join(
            [
                f"class Example{index}:",
                "    def compute(self, value: int) -> int:",
                '        """Tinh toan gia tri mau cho test."""',
                "        total = 0",
                *[f"        total += value + {i}" for i in range(20)],
                "        return total",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_smart_always_lte_full_for_python_files(tmp_path):
    """smart_tokens không được vượt full_tokens với file Python hợp lệ."""
    file_path = tmp_path / "example.py"
    _write_python_file(file_path)

    result = compare_token_counts([str(file_path)])

    assert isinstance(result, TokenComparison)
    assert result.full_tokens > 0
    assert result.smart_tokens <= result.full_tokens


def test_savings_pct_formula_correct(tmp_path):
    """savings_pct phải làm tròn 1 chữ số thập phân theo công thức đã chốt."""
    file_path = tmp_path / "formula.py"
    _write_python_file(file_path)

    result = compare_token_counts([str(file_path)])

    expected = round(
        ((result.full_tokens - result.smart_tokens) / result.full_tokens) * 100,
        1,
    )
    assert result.savings_pct == expected


def test_binary_file_fallback_to_full(tmp_path):
    """File binary không làm crash và Smart fallback bằng Full."""
    file_path = tmp_path / "image.png"
    file_path.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

    result = compare_token_counts([str(file_path)])

    assert result.smart_tokens == result.full_tokens
    assert result.savings_pct == 0.0


def test_unsupported_extension_fallback(tmp_path):
    """Extension không support Tree-sitter phải fallback Smart bằng Full."""
    file_path = tmp_path / "notes.md"
    file_path.write_text(
        "# Notes\n\nThis file is not parsed as smart context.\n", encoding="utf-8"
    )

    result = compare_token_counts([str(file_path)])

    assert result.full_tokens > 0
    assert result.smart_tokens == result.full_tokens
    assert result.savings_pct == 0.0


def test_empty_list_returns_zeros():
    """Input rỗng trả về zeros và không raise exception."""
    result = compare_token_counts([])

    assert result == TokenComparison(
        full_tokens=0,
        smart_tokens=0,
        tree_map_tokens=0,
        savings_pct=0.0,
    )


def test_performance_50_files_under_2s(tmp_path):
    """Service hoàn thành dưới 2 giây với 50 file Python thông thường."""
    paths: list[str] = []
    for index in range(50):
        file_path = tmp_path / f"file_{index}.py"
        _write_python_file(file_path, index=index)
        paths.append(str(file_path))

    start = perf_counter()
    result = compare_token_counts(paths)
    elapsed = perf_counter() - start

    assert result.full_tokens > 0
    assert result.smart_tokens <= result.full_tokens
    assert elapsed < 2.0


def test_thread_safe_concurrent_calls(tmp_path):
    """Nhiều thread gọi service cùng lúc phải trả kết quả nhất quán."""
    paths: list[str] = []
    for index in range(5):
        file_path = tmp_path / f"threaded_{index}.py"
        _write_python_file(file_path, index=index)
        paths.append(str(file_path))

    expected = compare_token_counts(paths)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: compare_token_counts(paths), range(16)))

    assert results == [expected] * 16


# ---------------------------------------------------------------------------
# Additional tests for missing coverage
# ---------------------------------------------------------------------------

from pathlib import Path
from unittest.mock import patch, MagicMock

from domain.tokenization.comparison_service import (
    TokenComparisonService,
    _normalize_existing_files,
    _read_text_file,
    _count_smart_tokens,
    _count_tree_map_tokens,
    _build_tree,
    _common_parent,
    _insert_path,
    _find_child,
)
from domain.smart_context.tree_item import TreeItem


# -- TokenComparisonService.compare_paths (line 56) --------------------------

def test_token_comparison_service_compare_paths(tmp_path):
    """TokenComparisonService.compare_paths() delegates to compare_token_counts (line 56)."""
    file_path = tmp_path / "test.py"
    file_path.write_text("def foo(): pass\n", encoding="utf-8")
    service = TokenComparisonService()
    result = service.compare_paths([str(file_path)])
    assert isinstance(result, TokenComparison)
    assert result.full_tokens > 0


# -- _normalize_existing_files (lines 108-109, 112) --------------------------

def test_normalize_existing_files_skips_oserror_path():
    """_normalize_existing_files skips paths where Path.resolve() raises OSError (lines 108-109)."""
    with patch("domain.tokenization.comparison_service.Path") as MockPath:
        instance = MagicMock()
        instance.resolve.side_effect = OSError("bad path")
        MockPath.return_value = instance
        result = _normalize_existing_files(["bad_path"])
    assert result == []


def test_normalize_existing_files_skips_runtime_error_path():
    """_normalize_existing_files skips paths where Path.resolve() raises RuntimeError (lines 108-109)."""
    with patch("domain.tokenization.comparison_service.Path") as MockPath:
        instance = MagicMock()
        instance.resolve.side_effect = RuntimeError("bad path")
        MockPath.return_value = instance
        result = _normalize_existing_files(["bad_path"])
    assert result == []


def test_normalize_existing_files_skips_duplicate(tmp_path):
    """_normalize_existing_files deduplicates paths (line 112)."""
    file_path = tmp_path / "file.py"
    file_path.write_text("x = 1", encoding="utf-8")
    result = _normalize_existing_files([str(file_path), str(file_path)])
    assert len(result) == 1


def test_normalize_existing_files_skips_nonexistent():
    """_normalize_existing_files skips non-existent paths (line 112)."""
    result = _normalize_existing_files(["/nonexistent/path/xyz123_unique.py"])
    assert result == []


def test_normalize_existing_files_skips_directory(tmp_path):
    """_normalize_existing_files skips directories (line 112)."""
    result = _normalize_existing_files([str(tmp_path)])
    assert result == []


# -- _read_text_file (lines 124-125) -----------------------------------------

def test_read_text_file_returns_none_for_binary(tmp_path):
    """_read_text_file returns None for binary files (line 122 -> None)."""
    file_path = tmp_path / "image.png"
    file_path.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
    result = _read_text_file(file_path)
    assert result is None


def test_read_text_file_returns_none_for_oserror(tmp_path):
    """_read_text_file returns None when read_text raises OSError (lines 124-125)."""
    file_path = tmp_path / "test.py"
    file_path.write_text("hello", encoding="utf-8")
    with patch("domain.tokenization.comparison_service.is_binary_file", return_value=False), \
         patch.object(Path, "read_text", side_effect=OSError("read error")):
        result = _read_text_file(file_path)
    assert result is None


# -- _count_smart_tokens (lines 136-137) -------------------------------------

def test_count_smart_tokens_exception_returns_full_count(tmp_path):
    """_count_smart_tokens returns full_count when smart_parse raises (lines 136-137)."""
    file_path = tmp_path / "test.py"
    file_path.write_text("x = 1", encoding="utf-8")
    with patch("domain.tokenization.comparison_service.smart_parse", side_effect=RuntimeError("parse error")):
        result = _count_smart_tokens(file_path, "x = 1", 42)
    assert result == 42


# -- _count_tree_map_tokens (line 150) ----------------------------------------

def test_count_tree_map_tokens_empty_list_returns_zero():
    """_count_tree_map_tokens returns 0 when paths list is empty (line 150)."""
    result = _count_tree_map_tokens([])
    assert result == 0


# -- _build_tree (line 165) ---------------------------------------------------

def test_build_tree_returns_none_for_empty_list():
    """_build_tree returns None for empty path list (line 165)."""
    result = _build_tree([])
    assert result is None


def test_build_tree_returns_tree_item_for_single_file(tmp_path):
    """_build_tree returns a TreeItem for a single file."""
    file_path = tmp_path / "file.py"
    file_path.write_text("x = 1", encoding="utf-8")
    result = _build_tree([file_path])
    assert result is not None
    assert isinstance(result, TreeItem)


# -- _common_parent (lines 185-186) -------------------------------------------

def test_common_parent_single_file(tmp_path):
    """_common_parent works with single path."""
    file_path = tmp_path / "file.py"
    result = _common_parent([file_path])
    assert result == file_path.parent


def test_common_parent_common_directory(tmp_path):
    """_common_parent returns the common ancestor directory."""
    a = tmp_path / "a" / "file.py"
    b = tmp_path / "b" / "file.py"
    result = _common_parent([a, b])
    assert result == tmp_path


def test_common_parent_value_error_returns_first_parent(tmp_path):
    """_common_parent returns first parent when ValueError occurs (lines 185-186)."""
    # On Linux, paths on different roots are hard to achieve without mocking.
    # Simulate ValueError by patching os.path.commonpath.
    parents = [tmp_path / "a", tmp_path / "b"]
    paths = [p / "file.py" for p in parents]
    with patch("domain.tokenization.comparison_service.os.path.commonpath", side_effect=ValueError("no common path")):
        result = _common_parent(paths)
    # Should return first parent
    assert result == paths[0].parent


# -- _insert_path (lines 193-194, 199-204) ------------------------------------

def test_insert_path_creates_nested_dirs(tmp_path):
    """_insert_path correctly builds nested TreeItem structure (lines 199-204)."""
    root_item = TreeItem(label="root", path=str(tmp_path), is_dir=True)
    nested_file = tmp_path / "sub" / "dir" / "file.py"
    _insert_path(root_item, tmp_path, nested_file)
    assert len(root_item.children) == 1
    sub = root_item.children[0]
    assert sub.label == "sub"
    assert sub.is_dir
    assert len(sub.children) == 1
    dir_item = sub.children[0]
    assert dir_item.label == "dir"
    assert len(dir_item.children) == 1
    assert dir_item.children[0].label == "file.py"


def test_insert_path_reuses_existing_directory(tmp_path):
    """_insert_path reuses existing directory node (lines 199-204)."""
    root_item = TreeItem(label="root", path=str(tmp_path), is_dir=True)
    file1 = tmp_path / "sub" / "a.py"
    file2 = tmp_path / "sub" / "b.py"
    _insert_path(root_item, tmp_path, file1)
    _insert_path(root_item, tmp_path, file2)
    # Should have only one 'sub' dir with two children
    assert len(root_item.children) == 1
    sub = root_item.children[0]
    assert sub.label == "sub"
    assert len(sub.children) == 2


def test_insert_path_outside_root(tmp_path):
    """_insert_path handles file outside root gracefully (lines 193-194)."""
    root_item = TreeItem(label="root", path=str(tmp_path), is_dir=True)
    outside_file = Path("/tmp/outside_file_xyz_unique.py")
    # file.relative_to(tmp_path) raises ValueError → uses filename only
    _insert_path(root_item, tmp_path, outside_file)
    assert len(root_item.children) == 1
    assert root_item.children[0].label == "outside_file_xyz_unique.py"


# -- _find_child (lines 213-216) ----------------------------------------------

def test_find_child_returns_matching_child():
    """_find_child returns the child matching the given path."""
    root = TreeItem(label="root", path="/root", is_dir=True)
    child = TreeItem(label="child", path="/root/child", is_dir=False)
    root.children.append(child)
    result = _find_child(root, "/root/child")
    assert result is child


def test_find_child_returns_none_when_not_found():
    """_find_child returns None when no child matches path (lines 213-216)."""
    root = TreeItem(label="root", path="/root", is_dir=True)
    root.children.append(TreeItem(label="child", path="/root/child", is_dir=False))
    result = _find_child(root, "/root/nonexistent")
    assert result is None


def test_find_child_returns_none_for_empty_children():
    """_find_child returns None when item has no children."""
    root = TreeItem(label="root", path="/root", is_dir=True)
    result = _find_child(root, "/root/anything")
    assert result is None
