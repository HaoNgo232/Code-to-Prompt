import os
from pathlib import Path
from typing import Optional, Set, Dict, List
from tree_sitter import Parser, Query, QueryCursor, Language  # type: ignore

from domain.smart_context.loader import get_language
from domain.smart_context.tree_item import TreeItem
from domain.codemap.dependency_resolver.python_resolver import resolve_python_import
from domain.codemap.dependency_resolver.js_resolver import (
    load_ts_config,
    resolve_js_import,
)

# ========================================
# Import Queries cho từng ngôn ngữ
# Các queries này extract import module names từ AST
# ========================================

IMPORT_QUERIES: Dict[str, str] = {
    # Python: import statements và from ... import statements
    "python": """
        ; Standard import: import module_name
        (import_statement
            name: (dotted_name) @import.module)
        
        ; From import: from module_name import something
        (import_from_statement
            module_name: (dotted_name) @import.module)
        
        ; Relative import: from . import something hoặc from .. import something
        (import_from_statement
            module_name: (relative_import) @import.relative)
    """,
    # JavaScript/TypeScript
    "javascript": """
        ; ES6 import: import x from 'module'
        (import_statement
            source: (string) @import.source)
        
        ; ES6 re-export: export { x } from 'module' hoặc export * from 'module'
        (export_statement
            source: (string) @import.source)
        
        ; CommonJS require: require('module')
        (call_expression
            function: (identifier) @func (#eq? @func "require")
            arguments: (arguments (string) @import.source))
    """,
    "typescript": """
        ; ES6 import: import x from 'module'
        (import_statement
            source: (string) @import.source)
        
        ; ES6 re-export: export { x } from 'module' hoặc export * from 'module'
        (export_statement
            source: (string) @import.source)
        
        ; CommonJS require: require('module') - also used in some TS codebases
        (call_expression
            function: (identifier) @func (#eq? @func "require")
            arguments: (arguments (string) @import.source))
    """,
    "go": """
        (import_spec path: [(interpreted_string_literal) (raw_string_literal)] @import.source)
    """,
    "rust": """
        (use_declaration argument: (path_expression) @import.source)
        (extern_crate_declaration name: (identifier) @import.source)
    """,
    "ruby": """
        (call
            method: (identifier) @func (#match? @func "require(_relative)?")
            arguments: (argument_list (string) @import.source))
    """,
    "java": """
        (import_declaration name: (dotted_name) @import.module)
    """,
    "cpp": """
        (preproc_include path: [(string_literal) (system_lib_string) (header_name)] @import.source)
    """,
    "c_sharp": """
        (using_directive name: [(identifier) (qualified_name)] @import.module)
    """,
}


class DependencyResolver:
    """
    Resolve imports trong file thành file paths trong workspace.

    Sử dụng Tree-sitter để parse code, extract imports,
    và resolve chúng thành actual file paths.

    Attributes:
        workspace_root: Root path của workspace
        _file_index: Index mapping filename -> full path
    """

    def __init__(self, workspace_root: Path):
        """
        Khởi tạo DependencyResolver.

        Args:
            workspace_root: Root path của workspace để resolve imports
        """
        self.workspace_root = workspace_root.resolve()
        self._file_index: Dict[str, Path] = {}
        self._module_index: Dict[str, Path] = {}  # module_name -> file_path

        # Alias support cho JS/TS (từ tsconfig.json/jsconfig.json)
        self._ts_paths: Dict[str, List[str]] = {}  # alias pattern -> list of paths
        self._ts_base_url: Optional[Path] = None
        self._ts_config_loaded: bool = False

    def build_file_index(self, tree: Optional[TreeItem]) -> None:
        """
        Build index tu TreeItem de ho tro resolve imports.

        Index bao gom:
        - filename -> full_path mapping
        - module_name -> file_path mapping (cho Python modules)

        Args:
            tree: TreeItem root cua file tree
        """
        # Load tsconfig/jsconfig for alias support (luon load, khong phu thuoc tree)
        self._load_ts_config()

        if not tree:
            return

        self._file_index.clear()
        self._module_index.clear()
        self._index_recursive(tree)

    def build_file_index_from_disk(self, workspace_root: Path) -> None:
        """
        Build file index truc tiep tu disk ma khong can TreeItem.

        Su dung DomainRegistry.workspace_scanner() de lay tat ca files.
        """
        # Load tsconfig/jsconfig for alias support
        self._load_ts_config()

        self._file_index.clear()
        self._module_index.clear()

        from domain.ports.registry import DomainRegistry

        all_files = DomainRegistry.workspace_scanner().collect_files(workspace_root)

        for file_path_str in all_files:
            file_path = Path(file_path_str)

            # Index by filename (cho fallback search)
            self._file_index[file_path.name] = file_path

            # Index by module path (cho Python imports)
            try:
                rel_path = file_path.relative_to(self.workspace_root)
                if file_path.suffix == ".py":
                    module_name = str(rel_path.with_suffix("")).replace(os.sep, ".")
                    self._module_index[module_name] = file_path
            except ValueError:
                pass

    def _load_ts_config(self) -> None:
        """
        Load tsconfig.json hoặc jsconfig.json để lấy path aliases.
        """
        if self._ts_config_loaded:
            return

        self._ts_config_loaded = True
        self._ts_paths, self._ts_base_url = load_ts_config(self.workspace_root)

    def _index_recursive(self, item: TreeItem) -> None:
        """Recursively index all files trong tree."""
        if not item.is_dir:
            file_path = Path(item.path)
            # Index by filename
            self._file_index[file_path.name] = file_path

            # Index by module path (cho Python)
            try:
                rel_path = file_path.relative_to(self.workspace_root)
                if file_path.suffix == ".py":
                    # Bỏ .py và chuyển / thành .
                    module_name = str(rel_path.with_suffix("")).replace(os.sep, ".")
                    self._module_index[module_name] = file_path
            except ValueError:
                pass

        # Recurse into children
        for child in item.children:
            self._index_recursive(child)

    def get_related_files(self, file_path: Path, max_depth: int = 1) -> Set[Path]:
        """
        Parse file và trả về set các files được import.

        Phân tích imports trong file và resolve chúng thành
        actual file paths trong workspace.

        Args:
            file_path: Path đến file cần analyze
            max_depth: Số cấp đệ quy để follow imports (default: 1 = chỉ direct imports)

        Returns:
            Set of resolved file paths trong workspace
        """
        if not file_path.exists():
            return set()

        ext = file_path.suffix.lstrip(".")
        lang_name = self._get_lang_name(ext)

        if lang_name not in IMPORT_QUERIES:
            return set()

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return set()

        language = get_language(ext)
        if not language:
            return set()

        # Parse và extract imports
        import_names = self._extract_imports(language, content, lang_name, file_path)

        # Resolve to actual file paths
        resolved = self._resolve_imports(import_names, file_path, lang_name)

        # Recursive resolution nếu max_depth > 1
        if max_depth > 1:
            for resolved_path in list(resolved):
                if resolved_path.exists() and resolved_path != file_path:
                    # Avoid adding source file and prevent infinite loops
                    nested = self.get_related_files(resolved_path, max_depth - 1)
                    resolved.update(nested)

        return resolved

    def get_related_files_with_depth(
        self, file_path: Path, max_depth: int = 1
    ) -> Dict[Path, int]:
        """
        Parse file va tra ve dict cac files duoc import kem theo depth level.

        Args:
            file_path: Path den file can analyze
            max_depth: So cap de quy de follow imports (default: 1)

        Returns:
            Dict mapping resolved file path -> depth level (1-based).
        """
        if not file_path.exists():
            return {}

        result: Dict[Path, int] = {}
        visited: Set[Path] = {file_path}
        source_file = file_path

        self._collect_with_depth(file_path, 1, max_depth, result, visited)

        # Remove source file from result if circular import added it
        result.pop(source_file, None)

        return result

    def _collect_with_depth(
        self,
        file_path: Path,
        current_depth: int,
        max_depth: int,
        result: Dict[Path, int],
        visited: Set[Path],
    ) -> None:
        """
        Recursively collect dependencies voi depth tracking.
        """
        if current_depth > max_depth:
            return

        ext = file_path.suffix.lstrip(".")
        lang_name = self._get_lang_name(ext)

        if lang_name not in IMPORT_QUERIES:
            return

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return

        language = get_language(ext)
        if not language:
            return

        import_names = self._extract_imports(language, content, lang_name, file_path)
        resolved = self._resolve_imports(import_names, file_path, lang_name)

        for resolved_path in resolved:
            if not resolved_path.exists():
                continue

            prev_depth = result.get(resolved_path)
            is_shorter = prev_depth is None or current_depth < prev_depth

            if is_shorter:
                result[resolved_path] = current_depth

            # Recurse neu: (a) chua visit, HOAC (b) tim duoc duong ngan hon
            if resolved_path not in visited or (
                is_shorter and current_depth + 1 <= max_depth
            ):
                visited.add(resolved_path)
                self._collect_with_depth(
                    resolved_path, current_depth + 1, max_depth, result, visited
                )

    def _extract_imports(
        self, language: Language, content: str, lang_name: str, source_file: Path
    ) -> Set[str]:
        """
        Extract import names từ file content sử dụng Tree-sitter queries.
        """
        import_names: Set[str] = set()

        try:
            parser = Parser(language)
            tree = parser.parse(bytes(content, "utf-8"))

            if not tree or not tree.root_node:
                return import_names

            query_string = IMPORT_QUERIES.get(lang_name, "")
            if not query_string:
                return import_names

            query = Query(language, query_string)
            query_cursor = QueryCursor(query)
            captures = query_cursor.captures(tree.root_node)

            # Xử lý captures
            for capture_name, nodes in captures.items():
                for node in nodes:
                    import_text = node.text.decode("utf-8") if node.text else ""

                    if not import_text:
                        continue

                    # Xử lý relative imports cho Python
                    if capture_name == "import.relative":
                        import_names.add(import_text)
                    elif capture_name == "import.module":
                        import_names.add(import_text)
                    elif capture_name == "import.source":
                        # JavaScript/TypeScript: Bỏ quotes
                        cleaned = import_text.strip("'\"")
                        import_names.add(cleaned)

        except Exception:
            pass

        return import_names

    def _resolve_imports(
        self, import_names: Set[str], source_file: Path, lang_name: str
    ) -> Set[Path]:
        resolved: Set[Path] = set()
        source_dir = source_file.parent

        for import_name in import_names:
            resolved_path = None

            if lang_name == "python":
                resolved_path = self._resolve_python_import(import_name, source_dir)
            elif lang_name in ("javascript", "typescript"):
                resolved_path = self.resolve_js_import(import_name, source_dir)

            if resolved_path and resolved_path.exists():
                resolved.add(resolved_path)

        return resolved

    def _resolve_python_import(
        self, import_name: str, source_dir: Path
    ) -> Optional[Path]:
        return resolve_python_import(
            import_name, source_dir, self._module_index, self.workspace_root
        )

    def resolve_js_import(self, import_path: str, source_dir: Path) -> Optional[Path]:
        return resolve_js_import(
            import_path,
            source_dir,
            self.workspace_root,
            self._file_index,
            self._ts_paths,
            self._ts_base_url,
        )

    def _resolve_python_relative(
        self, import_name: str, source_dir: Path
    ) -> Optional[Path]:
        from domain.codemap.dependency_resolver.python_resolver import (
            resolve_python_relative,
        )

        return resolve_python_relative(import_name, source_dir)

    def _get_lang_name(self, ext: str) -> str:
        """
        Map file extension sang language name cho query lookup.
        """
        ext_to_lang = {
            "py": "python",
            "pyw": "python",
            "js": "javascript",
            "jsx": "javascript",
            "mjs": "javascript",
            "cjs": "javascript",
            "ts": "typescript",
            "tsx": "typescript",
            "mts": "typescript",
            "cts": "typescript",
            "go": "go",
            "rs": "rust",
            "rb": "ruby",
            "java": "java",
            "cpp": "cpp",
            "hpp": "cpp",
            "c": "cpp",
            "h": "cpp",
            "cs": "c_sharp",
        }
        return ext_to_lang.get(ext.lower(), "")


def get_related_files_for_selection(
    workspace_root: Path,
    tree: Optional[TreeItem],
    selected_file: Path,
    max_depth: int = 1,
) -> Set[Path]:
    """
    Convenience function để lấy related files cho một file đã chọn.
    """
    resolver = DependencyResolver(workspace_root)
    resolver.build_file_index(tree)
    return resolver.get_related_files(selected_file, max_depth)
