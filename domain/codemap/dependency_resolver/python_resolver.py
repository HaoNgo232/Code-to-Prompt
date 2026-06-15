import os
from pathlib import Path
from typing import Optional, Dict


def resolve_python_import(
    import_name: str,
    source_dir: Path,
    module_index: Dict[str, Path],
    workspace_root: Path,
) -> Optional[Path]:
    """
    Resolve Python import thành file path.

    Strategies:
    1. Relative imports (.module, ..module)
    2. Absolute imports via module index
    3. Direct file search

    Args:
        import_name: Python module name (dotted notation)
        source_dir: Directory của file đang import
        module_index: Index mapping module_name -> file_path
        workspace_root: Root path của workspace

    Returns:
        Resolved Path hoặc None
    """
    # 1. Relative imports
    if import_name.startswith("."):
        return resolve_python_relative(import_name, source_dir)

    # 2. Absolute import - check module index
    if import_name in module_index:
        return module_index[import_name]

    # 3. Có thể là submodule - try prefix matching
    # Ví dụ: core.utils có thể match core/utils/__init__.py hoặc core/utils.py
    parts = import_name.split(".")

    # Try as file path trực tiếp
    for i in range(len(parts), 0, -1):
        partial_module = ".".join(parts[:i])
        if partial_module in module_index:
            return module_index[partial_module]

    # 4. Search trong workspace theo path
    path_parts = import_name.replace(".", os.sep)

    # Try as .py file
    candidate = workspace_root / (path_parts + ".py")
    if candidate.exists():
        return candidate

    # Try as package với __init__.py
    candidate = workspace_root / path_parts / "__init__.py"
    if candidate.exists():
        return candidate.parent  # Return package dir

    return None


def resolve_python_relative(
    import_name: str,
    source_dir: Path,
) -> Optional[Path]:
    """
    Resolve relative Python import.

    Examples:
    - .utils -> source_dir/utils.py
    - ..models -> source_dir/../models.py

    Args:
        import_name: Relative import (bắt đầu với .)
        source_dir: Directory của file đang import

    Returns:
        Resolved Path hoặc None
    """
    # Đếm số dấu . ở đầu
    dot_count = 0
    for char in import_name:
        if char == ".":
            dot_count += 1
        else:
            break

    # Phần còn lại sau các dấu .
    module_part = import_name[dot_count:]

    # Navigate up directories
    target_dir = source_dir
    for _ in range(dot_count - 1):  # -1 vì . đầu tiên = current dir
        target_dir = target_dir.parent

    if not module_part:
        # from . import something - chỉ reference current package
        return None

    # Chuyển đổi module path thành file path
    path_parts = module_part.replace(".", os.sep)

    # Try as .py file
    candidate = target_dir / (path_parts + ".py")
    if candidate.exists():
        return candidate

    # Try as package với __init__.py
    candidate = target_dir / path_parts / "__init__.py"
    if candidate.exists():
        return candidate

    return None
