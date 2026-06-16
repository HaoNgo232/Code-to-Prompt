"""
Unit tests cho domain/tokenization/counter.py (Pure functions).
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from domain.tokenization.counter import (
    _estimate_tokens,
    count_tokens,
    _read_file_mmap,
    _count_tokens_for_file_no_cache,
    count_tokens_for_file,
    MAX_BYTES,
)
from domain.tokenization.cache import TokenCache


def test_estimate_tokens():
    """Test uớc lượng tokens khi không có encoder."""
    assert _estimate_tokens("") == 0
    assert _estimate_tokens(None) == 0
    assert _estimate_tokens("Hi") == 1
    assert _estimate_tokens("a" * 100) == 25


def test_count_tokens_no_encoder():
    """Test count_tokens khi encoder=None."""
    assert count_tokens("hello world", encoder=None) == 2


def test_count_tokens_hf_encoder():
    """Test count_tokens với hf (HuggingFace) encoder type."""
    mock_encoder = MagicMock()
    mock_encoder.encode.return_value.ids = [1, 2, 3]

    result = count_tokens("test text", encoder=mock_encoder, encoder_type="hf")
    assert result == 3
    mock_encoder.encode.assert_called_once_with("test text")


def test_count_tokens_tiktoken_encoder():
    """Test count_tokens với tiktoken/rs_bpe encoder type."""
    mock_encoder = MagicMock()
    mock_encoder.encode.return_value = [10, 20, 30, 40]

    result = count_tokens("test text", encoder=mock_encoder, encoder_type="tiktoken")
    assert result == 4
    mock_encoder.encode.assert_called_once_with("test text")


def test_count_tokens_exception_fallback():
    """Test count_tokens khi encoder bị ném lỗi."""
    mock_encoder = MagicMock()
    mock_encoder.encode.side_effect = Exception("error")

    result = count_tokens("hello world", encoder=mock_encoder, encoder_type="tiktoken")
    assert result == 2  # fallback to estimate (11 // 4 = 2)


def test_read_file_mmap_nonexistent():
    """Test _read_file_mmap với file không tồn tại."""
    assert _read_file_mmap(Path("/nonexistent/file.txt")) is None


def test_read_file_mmap_empty(tmp_path):
    """Test _read_file_mmap với file rỗng."""
    empty_file = tmp_path / "empty.txt"
    empty_file.write_text("")
    assert _read_file_mmap(empty_file) == ""


def test_read_file_mmap_normal(tmp_path):
    """Test _read_file_mmap với file text bình thường."""
    normal_file = tmp_path / "normal.txt"
    normal_file.write_text("hello world", encoding="utf-8")
    assert _read_file_mmap(normal_file) == "hello world"


def test_read_file_mmap_fallback_read_text(tmp_path):
    """Test _read_file_mmap khi mmap bị ném exception thì fallback sang read_text."""
    normal_file = tmp_path / "normal.txt"
    normal_file.write_text("hello world from read_text", encoding="utf-8")

    # Mock open để ném exception nhằm trigger fallback read_text
    with patch("builtins.open", side_effect=OSError("mmap error")):
        assert _read_file_mmap(normal_file) == "hello world from read_text"


def test_read_file_mmap_total_failure(tmp_path):
    """Test _read_file_mmap khi cả mmap và read_text đều thất bại."""
    normal_file = tmp_path / "normal.txt"
    with (
        patch("builtins.open", side_effect=OSError("mmap error")),
        patch.object(Path, "read_text", side_effect=OSError("read error")),
    ):
        assert _read_file_mmap(normal_file) is None


def test_count_tokens_for_file_no_cache_edge_cases(tmp_path):
    """Test _count_tokens_for_file_no_cache với các cases biên."""
    # 1. File không tồn tại
    assert _count_tokens_for_file_no_cache(Path("/nonexistent/file.txt")) == 0

    # 2. File directory
    dir_path = tmp_path / "subdir"
    dir_path.mkdir()
    assert _count_tokens_for_file_no_cache(dir_path) == 0

    # 3. File quá lớn (> 5MB)
    large_file = tmp_path / "large.txt"
    import os
    import stat

    with patch.object(Path, "stat") as mock_stat:
        mock_stat.return_value = os.stat_result(
            (stat.S_IFREG, 0, 0, 0, 0, 0, MAX_BYTES + 1, 0, 0, 0)
        )
        assert _count_tokens_for_file_no_cache(large_file) == 0

    # 4. File rỗng (0 bytes)
    empty_file = tmp_path / "empty.txt"
    empty_file.write_text("")
    assert _count_tokens_for_file_no_cache(empty_file) == 0


def test_count_tokens_for_file_no_cache_with_cache_hit(tmp_path):
    """Test _count_tokens_for_file_no_cache khi có cache hit."""
    file_path = tmp_path / "test.py"
    file_path.write_text("print('hello')")

    cache = TokenCache()
    stat = file_path.stat()
    cache.put(str(file_path), stat.st_mtime, 150)

    # Gọi count no cache
    result = _count_tokens_for_file_no_cache(file_path, cache=cache)
    assert result == 150


def test_count_tokens_for_file_no_cache_binary(tmp_path):
    """Test _count_tokens_for_file_no_cache với file nhị phân."""
    bin_file = tmp_path / "test.png"
    bin_file.write_bytes(bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A]))  # PNG magic

    assert _count_tokens_for_file_no_cache(bin_file) == 0


def test_count_tokens_for_file_no_cache_success(tmp_path):
    """Test _count_tokens_for_file_no_cache chạy thành công hoàn toàn."""
    file_path = tmp_path / "test.py"
    file_path.write_text("print('hello world')", encoding="utf-8")

    result = _count_tokens_for_file_no_cache(file_path, encoder=None)
    assert result == 5  # 20 // 4 = 5


def test_count_tokens_for_file_no_cache_exception_handling(tmp_path):
    """Test _count_tokens_for_file_no_cache xử lý exception bên trong."""
    file_path = tmp_path / "test.py"
    file_path.write_text("print('hello')", encoding="utf-8")

    with patch(
        "domain.tokenization.counter.count_tokens", side_effect=Exception("error")
    ):
        assert _count_tokens_for_file_no_cache(file_path) == 0


def test_count_tokens_for_file_edge_cases(tmp_path):
    """Test count_tokens_for_file các cases biên."""
    # 1. File không tồn tại
    assert count_tokens_for_file(Path("/nonexistent/file.txt")) == 0

    # 2. File directory
    dir_path = tmp_path / "subdir"
    dir_path.mkdir()
    assert count_tokens_for_file(dir_path) == 0

    # 3. File quá lớn
    large_file = tmp_path / "large.txt"
    import os
    import stat

    with patch.object(Path, "stat") as mock_stat:
        mock_stat.return_value = os.stat_result(
            (stat.S_IFREG, 0, 0, 0, 0, 0, MAX_BYTES + 1, 0, 0, 0)
        )
        assert count_tokens_for_file(large_file) == 0

    # 4. File rỗng
    empty_file = tmp_path / "empty.txt"
    empty_file.write_text("")
    assert count_tokens_for_file(empty_file) == 0


def test_count_tokens_for_file_with_cache(tmp_path):
    """Test count_tokens_for_file sử dụng cache lưu trữ."""
    file_path = tmp_path / "test.py"
    file_path.write_text("print('hello')", encoding="utf-8")

    cache = TokenCache()

    # Lần 1: cache miss
    result1 = count_tokens_for_file(file_path, encoder=None, cache=cache)
    assert result1 == 3

    # Lần 2: cache hit
    result2 = count_tokens_for_file(file_path, encoder=None, cache=cache)
    assert result2 == 3

    # Verify cache chứa file
    stat = file_path.stat()
    assert cache.get(str(file_path), stat.st_mtime) == 3


def test_count_tokens_for_file_binary(tmp_path):
    """Test count_tokens_for_file với file nhị phân."""
    bin_file = tmp_path / "test.png"
    bin_file.write_bytes(bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A]))

    assert count_tokens_for_file(bin_file) == 0


def test_count_tokens_for_file_io_error(tmp_path):
    """Test count_tokens_for_file khi có lỗi I/O."""
    file_path = tmp_path / "test.py"
    file_path.write_text("print('hello')", encoding="utf-8")

    with patch.object(Path, "read_text", side_effect=OSError("Read error")):
        assert count_tokens_for_file(file_path) == 0
