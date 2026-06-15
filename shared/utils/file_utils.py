import os
import stat
from pathlib import Path
from shared.constants import BINARY_EXTENSIONS

# Optimization: Module-level constants (tạo 1 lần duy nhất)
_TEXT_EXTENSIONS = frozenset(
    {
        ".py",
        ".js",
        ".ts",
        ".html",
        ".css",
        ".md",
        ".txt",
        ".json",
        ".yaml",
        ".yml",
        ".xml",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".go",
        ".rs",
        ".java",
        ".kt",
        ".rb",
        ".sh",
        ".sql",
        ".mod",
        ".sum",
        ".toml",
        ".cfg",
        ".ini",
        ".env",
        ".jsx",
        ".tsx",
        ".vue",
        ".svelte",
        ".scss",
        ".less",
        ".graphql",
        ".proto",
        ".tf",
        ".dockerfile",
    }
)


def is_binary_file(path_or_str: Path | str) -> bool:
    """
    Check xem một file có phải là binary không.
    Hàm này hỗ trợ cả Path object và string path để tối ưu hiệu năng trong vòng lặp lớn.

    Optimization:
    1. Kiểm tra extension trước (fast whitelist/blacklist)
    2. Chỉ đọc nội dung nếu extension không xác định.
    """
    # Convert to string for suffix check
    path_str = str(path_or_str)
    _, ext = os.path.splitext(path_str)
    ext = ext.lower()

    # 1. Fast check by extension
    if ext in BINARY_EXTENSIONS:
        return True

    # Whitelist các extension text phổ biến để skip I/O
    if ext in _TEXT_EXTENSIONS:
        return False

    # 2. Fallback to magic bytes check
    try:
        # Kiểm tra loại file bằng lstat trước khi mở để tránh bị treo (blocking) khi gặp Named Pipe (FIFO)
        stat_result = os.lstat(path_str)
        if not stat.S_ISREG(stat_result.st_mode):
            return False

        # Kiểm tra file size trước, file cực lớn (>5MB) mà không có extension
        # text thì khả năng cao là binary (ví dụ dump file).
        if stat_result.st_size > 5 * 1024 * 1024:
            return True

        with open(path_str, "rb") as f:
            chunk = f.read(1024)
            # Nếu chứa null byte thì khả năng cao là binary
            return b"\x00" in chunk
    except (PermissionError, OSError):
        return False


def is_binary_by_extension(file_path: Path) -> bool:
    """
    Check if file is binary based on extension (legacy function).
    Use is_binary_file() for more accurate detection.
    """
    return file_path.suffix.lower() in BINARY_EXTENSIONS
