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
