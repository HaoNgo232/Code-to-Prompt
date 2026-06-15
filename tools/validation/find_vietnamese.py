import os
import ast
import re

# Regex matching Vietnamese characters (both uppercase and lowercase)
VIETNAMESE_REGEX = re.compile(
    r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễđòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹ]", re.IGNORECASE
)


def contains_vietnamese(text):
    if not isinstance(text, str):
        return False
    return bool(VIETNAMESE_REGEX.search(text))


class VietnameseStringFinder(ast.NodeVisitor):
    def __init__(self, filepath):
        self.filepath = filepath
        self.matches = []
        self.ignored_nodes = set()

    def _mark_docstring(self, body):
        if body and isinstance(body[0], ast.Expr):
            val = body[0].value
            if isinstance(val, (ast.Constant, ast.Str)):
                self.ignored_nodes.add(val)

    def visit_Module(self, node):
        self._mark_docstring(node.body)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self._mark_docstring(node.body)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self._mark_docstring(node.body)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self._mark_docstring(node.body)
        self.generic_visit(node)

    def visit_Constant(self, node):
        if node in self.ignored_nodes:
            self.generic_visit(node)
            return
        if isinstance(node.value, str) and contains_vietnamese(node.value):
            self.matches.append(
                {
                    "file": self.filepath,
                    "line": node.lineno,
                    "col": node.col_offset,
                    "value": node.value,
                }
            )
        self.generic_visit(node)

    def visit_Str(self, node):
        if node in self.ignored_nodes:
            self.generic_visit(node)
            return
        if contains_vietnamese(node.s):
            self.matches.append(
                {
                    "file": self.filepath,
                    "line": node.lineno,
                    "col": node.col_offset,
                    "value": node.s,
                }
            )
        self.generic_visit(node)


def scan_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content, filename=filepath)
        finder = VietnameseStringFinder(filepath)
        finder.visit(tree)
        # Filter out standalone expression statements that are string constants (most likely undocumented/unreached docstrings or leftover strings)
        return finder.matches
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return []


def main():
    exclude_dirs = {
        ".venv",
        ".git",
        ".pytest_cache",
        "__pycache__",
        ".ruff_cache",
        "build",
        "dist",
        "tests",
        "scratch",
    }
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    all_matches = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Exclude directories in-place
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for filename in filenames:
            if filename.endswith(".py"):
                filepath = os.path.join(dirpath, filename)
                matches = scan_file(filepath)
                all_matches.extend(matches)

    output_path = os.path.join(root_dir, "scratch", "vietnamese_matches.txt")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"Found {len(all_matches)} Vietnamese string constants:\n")
        for match in all_matches:
            f.write(
                f"{match['file']}:{match['line']}:{match['col']} -> {repr(match['value'])}\n"
            )
    print(f"Wrote {len(all_matches)} matches to {output_path}")


if __name__ == "__main__":
    main()
