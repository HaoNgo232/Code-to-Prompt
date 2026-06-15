import re
import json
from pathlib import Path
from typing import Optional, List, Dict, Tuple


def load_ts_config(workspace_root: Path) -> Tuple[Dict[str, List[str]], Optional[Path]]:
    """
    Load tsconfig.json hoặc jsconfig.json để lấy path aliases.

    Đọc compilerOptions.paths và compilerOptions.baseUrl.
    Tìm kiếm trong root và các subfolder phổ biến (frontend/, src/, app/).

    Args:
        workspace_root: Root path của workspace

    Returns:
        Tuple[ts_paths, ts_base_url]
    """
    ts_paths: Dict[str, List[str]] = {}
    ts_base_url: Optional[Path] = None

    # Tìm config file - ưu tiên root, sau đó các subfolder phổ biến
    config_names = ["tsconfig.json", "jsconfig.json"]
    search_dirs = [
        workspace_root,
        workspace_root / "frontend",
        workspace_root / "src",
        workspace_root / "app",
        workspace_root / "client",
        workspace_root / "web",
    ]

    config_path: Path | None = None
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for name in config_names:
            candidate = search_dir / name
            if candidate.exists():
                config_path = candidate
                break
        if config_path:
            break

    if not config_path:
        return ts_paths, ts_base_url

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            # Handle JSON with comments (trailing commas, // comments)
            content = f.read()
            # Simple cleanup: remove single-line comments
            content = re.sub(r"//.*$", "", content, flags=re.MULTILINE)
            # Remove trailing commas before } or ]
            content = re.sub(r",(\s*[}\]])", r"\1", content)

            config = json.loads(content)

        compiler_options = config.get("compilerOptions", {})

        # Extract baseUrl - nếu không có thì dùng thư mục chứa tsconfig
        base_url = compiler_options.get("baseUrl", ".")
        ts_base_url = (config_path.parent / base_url).resolve()

        # Extract paths và normalize (bỏ ./ prefix nếu có)
        paths = compiler_options.get("paths", {})
        for alias_pattern, target_paths in paths.items():
            if isinstance(target_paths, list):
                # Normalize: bỏ ./ prefix
                normalized_paths: List[str] = []
                for p in target_paths:
                    path_str = str(p)
                    if path_str.startswith("./"):
                        path_str = path_str[2:]
                    normalized_paths.append(path_str)
                ts_paths[alias_pattern] = normalized_paths

    except Exception:
        # Nếu parse lỗi thì bỏ qua, không break flow
        pass

    return ts_paths, ts_base_url


def resolve_js_import(
    import_path: str,
    source_dir: Path,
    workspace_root: Path,
    file_index: Dict[str, Path],
    ts_paths: Dict[str, List[str]],
    ts_base_url: Optional[Path],
) -> Optional[Path]:
    """
    Resolve JavaScript/TypeScript import thành file path.

    Hỗ trợ:
    1. Relative imports: ./module, ../module
    2. Path aliases từ tsconfig.json/jsconfig.json: @/components, @utils

    Node modules (lodash, react, etc.) không được resolve.

    Args:
        import_path: Import path (relative hoặc absolute)
        source_dir: Directory của file đang import
        workspace_root: Root path của workspace
        file_index: Index mapping filename -> path
        ts_paths: TS path aliases mapping
        ts_base_url: TS base url Path

    Returns:
        Resolved Path hoặc None
    """
    possible_extensions = [".ts", ".tsx", ".js", ".jsx", ""]

    # 1. Handle relative imports
    if import_path.startswith("."):
        for ext in possible_extensions:
            candidate = (source_dir / (import_path + ext)).resolve()
            if candidate.exists() and candidate.is_file():
                return candidate

            # Try index file
            if ext == "":
                for index_name in [
                    "index.ts",
                    "index.tsx",
                    "index.js",
                    "index.jsx",
                ]:
                    index_candidate = (source_dir / import_path / index_name).resolve()
                    if index_candidate.exists():
                        return index_candidate
        return None

    # 2. Tìm theo filename cuối cùng trong import path (strategy chính cho JS/TS)
    # Ví dụ: '@/infrastructure/cleanup/kpack-cleanup.service'
    #   -> tìm file 'kpack-cleanup.service.ts' trong file index
    resolved = resolve_js_by_filename(
        import_path, possible_extensions, file_index, workspace_root
    )
    if resolved:
        return resolved

    # 3. Fallback: thử path aliases từ tsconfig.json/jsconfig.json
    if ts_paths and ts_base_url:
        resolved = resolve_ts_alias(
            import_path, possible_extensions, workspace_root, ts_paths, ts_base_url
        )
        if resolved:
            return resolved

    # 4. Non-relative, non-alias imports (node_modules) - skip
    return None


def resolve_ts_alias(
    import_path: str,
    extensions: List[str],
    workspace_root: Path,
    ts_paths: Dict[str, List[str]],
    ts_base_url: Optional[Path],
) -> Optional[Path]:
    """
    Resolve import path sử dụng path aliases từ tsconfig.json.

    Ví dụ:
    - "@/components/Button" với paths {"@/*": ["src/*"]}
      -> src/components/Button.tsx

    Args:
        import_path: Import path (e.g., "@/components/Button")
        extensions: List of extensions to try
        workspace_root: Workspace root path
        ts_paths: TS path aliases mapping
        ts_base_url: TS base url Path

    Returns:
        Resolved Path hoặc None
    """
    for alias_pattern, target_paths in ts_paths.items():
        # Tạo regex-like check
        if alias_pattern.endswith("/*"):
            # Wildcard pattern: @/* matches @/anything
            prefix = alias_pattern[:-2]  # Bỏ /*
            if import_path.startswith(prefix + "/"):
                # Match! Extract phần sau prefix
                suffix = import_path[len(prefix) + 1 :]

                # Try each target path
                for target in target_paths:
                    if "*" in target:
                        target_prefix = target.replace("*", suffix)
                        suffix_to_append = ""
                    else:
                        target_prefix = target
                        suffix_to_append = suffix

                    # Build full path
                    if ts_base_url:
                        base = ts_base_url / target_prefix / suffix_to_append
                    else:
                        base = workspace_root / target_prefix / suffix_to_append

                    # Try with extensions
                    for ext in extensions:
                        candidate = Path(str(base) + ext)
                        if candidate.exists() and candidate.is_file():
                            return candidate

                        # Try index file
                        if ext == "":
                            for index_name in [
                                "index.ts",
                                "index.tsx",
                                "index.js",
                                "index.jsx",
                            ]:
                                index_candidate = base / index_name
                                if index_candidate.exists():
                                    return index_candidate

        elif alias_pattern == import_path:
            # Exact match (không có wildcard)
            for target in target_paths:
                if ts_base_url:
                    candidate = ts_base_url / target
                else:
                    candidate = workspace_root / target

                for ext in extensions:
                    full_candidate = Path(str(candidate) + ext)
                    if full_candidate.exists() and full_candidate.is_file():
                        return full_candidate

    return None


def resolve_js_by_filename(
    import_path: str,
    extensions: List[str],
    file_index: Dict[str, Path],
    workspace_root: Path,
) -> Optional[Path]:
    """
    Fallback: resolve JS/TS import bằng cách tìm filename cuối cùng trong file index.

    Args:
        import_path: Import path string
        extensions: Extensions to try
        file_index: Index of filenames -> Paths
        workspace_root: Workspace root path

    Returns:
        Resolved Path or None
    """
    if not file_index:
        return None

    # Lấy basename từ import path
    basename = import_path.rsplit("/", 1)[-1] if "/" in import_path else import_path
    if not basename:
        return None

    # Skip node_module-like imports (không có / hoặc chỉ có scope prefix)
    segments = import_path.split("/")
    if not import_path.startswith(("@/", "~/", "~", "#")):
        # Nếu bắt đầu bằng @ (scoped package) vd: @nestjs/common
        if import_path.startswith("@") and len(segments) <= 2:
            return None
        # Nếu chỉ có 1 segment (vd: 'react', 'lodash')
        if len(segments) == 1:
            return None

    # Tìm trong file index theo basename + extensions
    for ext in extensions:
        if ext == "":
            continue  # Skip empty extension, đã thử ở các ext khác
        target_name = basename + ext
        if target_name in file_index:
            candidate = file_index[target_name]
            # Verify: path suffix phải chứa import path segments
            if path_suffix_matches(candidate, import_path, workspace_root):
                return candidate

    # Nếu strict match không tìm thấy, thử relaxed match (chỉ theo tên file)
    for ext in extensions:
        if ext == "":
            continue
        target_name = basename + ext
        if target_name in file_index:
            return file_index[target_name]

    # Thử tìm index file trong folder
    for ext in extensions:
        if ext == "":
            for index_name in ["index.ts", "index.tsx", "index.js", "index.jsx"]:
                if index_name in file_index:
                    # Chỉ match nếu parent folder đúng
                    candidate = file_index[index_name]
                    if candidate.parent.name == basename:
                        return candidate

    return None


def path_suffix_matches(
    file_path: Path, import_path: str, workspace_root: Path
) -> bool:
    """
    Kiểm tra xem file path có chứa các segments từ import path không.

    Args:
        file_path: Actual file path
        import_path: Import path string
        workspace_root: Workspace root path

    Returns:
        True nếu path suffix match
    """
    # Bỏ prefix alias (@/, ~/, etc.)
    clean_import = import_path
    for prefix in ["@/", "~/", "#/"]:
        if clean_import.startswith(prefix):
            clean_import = clean_import[len(prefix) :]
            break
    if clean_import.startswith("@"):
        # Scoped: @scope/rest -> rest
        parts = clean_import.split("/", 1)
        if len(parts) > 1:
            clean_import = parts[1]

    # Lấy các segments (bỏ segment cuối vì đã match qua filename)
    import_segments = clean_import.split("/")[:-1]

    if not import_segments:
        return True  # Không có parent segments để verify, accept

    # Kiểm tra file path có chứa các segments này không
    try:
        rel_path = file_path.relative_to(workspace_root)
        file_parts = list(rel_path.parts)
    except ValueError:
        file_parts = list(file_path.parts)

    # Tìm xem import_segments có xuất hiện liên tiếp trong file_parts không
    for i in range(len(file_parts) - len(import_segments) + 1):
        if file_parts[i : i + len(import_segments)] == import_segments:
            return True

    return False
