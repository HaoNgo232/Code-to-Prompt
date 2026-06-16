from domain.codemap.graph_builder import CodeMapBuilder
from domain.smart_context.tree_item import TreeItem
from domain.codemap.types import (
    CodeMap,
    Symbol,
    Relationship,
    RelationshipKind,
    SymbolKind,
)


class TestCodeMapBuilder:
    def test_build_for_file_read_error(self, tmp_path):
        builder = CodeMapBuilder(workspace_root=tmp_path)
        # 1. Non-existent file path should raise Exception when open() is called, returning None (lines 61-62)
        non_existent = str(tmp_path / "ghost.py")
        res = builder.build_for_file(non_existent)
        assert res is None

    def test_build_for_file_with_content(self, tmp_path):
        builder = CodeMapBuilder(workspace_root=tmp_path)
        test_file = tmp_path / "dummy.py"
        test_file.write_text("def my_func():\n    pass", encoding="utf-8")

        # 2. Build with explicit content
        codemap = builder.build_for_file(
            str(test_file), content="def custom_func():\n    pass"
        )
        assert codemap is not None
        assert codemap.file_path == str(test_file)
        assert len(codemap.symbols) > 0
        assert builder.get_codemap(str(test_file)) == codemap

    def test_build_for_workspace_and_collect_files(self, tmp_path):
        # Create directory tree structure:
        # root/
        #   ├── main.py
        #   └── src/
        #        └── helper.py
        main_path = tmp_path / "main.py"
        main_path.write_text(
            "import src.helper\ndef run():\n    pass", encoding="utf-8"
        )

        src_dir = tmp_path / "src"
        src_dir.mkdir()
        helper_path = src_dir / "helper.py"
        helper_path.write_text("def help_me():\n    pass", encoding="utf-8")

        tree = TreeItem(
            label="root",
            path=str(tmp_path),
            is_dir=True,
            children=[
                TreeItem(label="main.py", path=str(main_path), is_dir=False),
                TreeItem(
                    label="src",
                    path=str(src_dir),
                    is_dir=True,
                    children=[
                        TreeItem(label="helper.py", path=str(helper_path), is_dir=False)
                    ],
                ),
            ],
        )

        builder = CodeMapBuilder(workspace_root=tmp_path)
        result = builder.build_for_workspace(tree)

        # Check that both files are indexed
        assert str(main_path) in result
        assert str(helper_path) in result
        assert builder.get_codemap(str(main_path)) is not None
        assert builder.get_codemap(str(helper_path)) is not None

    def test_get_related_symbols_and_traversal(self, tmp_path):
        builder = CodeMapBuilder(workspace_root=tmp_path)
        file_path = str(tmp_path / "prog.py")
        empty_file_path = str(tmp_path / "empty.py")

        # Construct a manual CodeMap with specific symbols and relationships to test traversal logic
        # A simple chain: funcA -> funcB -> funcC
        sym1 = Symbol(
            name="funcA",
            kind=SymbolKind.FUNCTION,
            file_path=file_path,
            line_start=1,
            line_end=2,
        )
        sym2 = Symbol(
            name="funcB",
            kind=SymbolKind.FUNCTION,
            file_path=file_path,
            line_start=5,
            line_end=6,
        )
        sym3 = Symbol(
            name="funcC",
            kind=SymbolKind.FUNCTION,
            file_path=file_path,
            line_start=10,
            line_end=11,
        )

        rel1 = Relationship(
            source="funcA", target="funcB", kind=RelationshipKind.CALLS, source_line=2
        )
        rel2 = Relationship(
            source="funcB", target="funcC", kind=RelationshipKind.CALLS, source_line=6
        )

        codemap = CodeMap(
            file_path=file_path, symbols=[sym1, sym2, sym3], relationships=[rel1, rel2]
        )

        builder.codemaps[file_path] = codemap
        builder.codemaps[empty_file_path] = CodeMap(
            file_path=empty_file_path, symbols=[], relationships=[]
        )

        # Update builder indexes manually for caller/callee testing
        builder._callers_index["funcB"] = ["funcA"]
        builder._callers_index["funcC"] = ["funcB"]
        builder._callees_index["funcA"] = ["funcB"]
        builder._callees_index["funcB"] = ["funcC"]

        # 1. Depth = 0 traversal from funcA (direct relationships only)
        # Should only contain direct callee/caller (funcB), not funcC
        related_d0 = builder.get_related_symbols("funcA", depth=0)
        assert "funcB" in related_d0
        assert "funcC" not in related_d0

        # 2. Depth = 1 traversal from funcA
        # Starts at funcA (depth 0), traverses to funcB (depth 1), adding funcC.
        related_d1 = builder.get_related_symbols("funcA", depth=1)
        assert "funcB" in related_d1
        assert "funcC" in related_d1

        # 3. Depth = 2 traversal from funcC (reverse traversal target -> source)
        # Starts at funcC (depth 0), traverses reverse to funcB (depth 1), then to funcA (depth 2).
        related_rev = builder.get_related_symbols("funcC", depth=2)
        assert "funcB" in related_rev
        assert "funcA" in related_rev

        # 4. Search with specific file_path limit
        related_scoped = builder.get_related_symbols(
            "funcA", depth=1, file_path=file_path
        )
        assert "funcB" in related_scoped

        # 5. Search with non-existent file_path scoped limit (falls back to all codemaps)
        related_scoped_none = builder.get_related_symbols(
            "funcA", depth=1, file_path="nonexistent.py"
        )
        assert len(related_scoped_none) > 0

        # 6. Search with a valid but empty file scope (searches only that file, resulting in 0 matches)
        related_scoped_empty = builder.get_related_symbols(
            "funcA", depth=1, file_path=empty_file_path
        )
        assert len(related_scoped_empty) == 0

        # Test callers and callees APIs
        assert builder.get_callers("funcB") == ["funcA"]
        assert builder.get_callees("funcA") == ["funcB"]
        assert builder.get_callers("funcX") == []
        assert builder.get_callees("funcX") == []

    def test_get_related_symbols_cycle_detection(self, tmp_path):
        builder = CodeMapBuilder(workspace_root=tmp_path)
        file_path = str(tmp_path / "prog.py")

        sym1 = Symbol(
            name="funcA",
            kind=SymbolKind.FUNCTION,
            file_path=file_path,
            line_start=1,
            line_end=2,
        )
        sym2 = Symbol(
            name="funcB",
            kind=SymbolKind.FUNCTION,
            file_path=file_path,
            line_start=5,
            line_end=6,
        )

        # Cycle: funcA -> funcB and funcB -> funcA
        rel1 = Relationship(
            source="funcA", target="funcB", kind=RelationshipKind.CALLS, source_line=2
        )
        rel2 = Relationship(
            source="funcB", target="funcA", kind=RelationshipKind.CALLS, source_line=6
        )

        codemap = CodeMap(
            file_path=file_path, symbols=[sym1, sym2], relationships=[rel1, rel2]
        )

        builder.codemaps[file_path] = codemap
        builder._callers_index["funcB"] = ["funcA"]
        builder._callers_index["funcA"] = ["funcB"]
        builder._callees_index["funcA"] = ["funcB"]
        builder._callees_index["funcB"] = ["funcA"]

        # Depth = 2 traversal to trigger cycle:
        # traverse(funcA, 0) -> calls traverse(funcB, 1) -> calls traverse(funcA, 2)
        # Inside traverse(funcA, 2), name in visited is True, which triggers return (line 149)
        related = builder.get_related_symbols("funcA", depth=2)
        assert "funcB" in related

    def test_clear_cache(self, tmp_path):
        builder = CodeMapBuilder(workspace_root=tmp_path)
        builder.codemaps["a.py"] = CodeMap("a.py", [], [])
        builder._callers_index["b"] = ["a"]
        builder._callees_index["a"] = ["b"]

        builder.clear_cache()
        assert len(builder.codemaps) == 0
        assert len(builder._callers_index) == 0
        assert len(builder._callees_index) == 0

    def test_invalidate_file(self, tmp_path):
        builder = CodeMapBuilder(workspace_root=tmp_path)
        file_path = str(tmp_path / "main.py")

        sym1 = Symbol(
            name="funcA",
            kind=SymbolKind.FUNCTION,
            file_path=file_path,
            line_start=1,
            line_end=2,
        )
        sym2 = Symbol(
            name="funcB",
            kind=SymbolKind.FUNCTION,
            file_path=file_path,
            line_start=5,
            line_end=6,
        )
        rel = Relationship(
            source="funcA", target="funcB", kind=RelationshipKind.CALLS, source_line=2
        )

        codemap = CodeMap(
            file_path=file_path, symbols=[sym1, sym2], relationships=[rel]
        )

        builder.codemaps[file_path] = codemap
        builder._callers_index["funcB"] = ["funcA"]
        builder._callees_index["funcA"] = ["funcB"]

        # Invalidate file not in cache (should do nothing, line 213 no-op)
        builder.invalidate_file("other.py")
        assert file_path in builder.codemaps

        # Invalidate file in cache
        builder.invalidate_file(file_path)
        assert file_path not in builder.codemaps
        assert (
            "funcA" not in builder._callees_index
            or "funcB" not in builder._callees_index["funcA"]
        )
        assert (
            "funcB" not in builder._callers_index
            or "funcA" not in builder._callers_index["funcB"]
        )

    def test_invalidate_file_removal_exceptions(self, tmp_path):
        # Trigger the ValueError try-except blocks inside invalidate_file (lines 221-222, 226-227)
        builder = CodeMapBuilder(workspace_root=tmp_path)
        file_path = str(tmp_path / "main.py")

        rel = Relationship(
            source="funcA", target="funcB", kind=RelationshipKind.CALLS, source_line=2
        )
        codemap = CodeMap(file_path=file_path, symbols=[], relationships=[rel])

        builder.codemaps[file_path] = codemap
        # Setup index so key exists, but value lists do NOT contain funcA or funcB (triggers ValueError on remove)
        builder._callers_index["funcB"] = ["someOtherFunc"]
        builder._callees_index["funcA"] = ["someOtherFunc"]

        # Calling invalidate_file should not raise ValueError but gracefully pass
        builder.invalidate_file(file_path)
        assert file_path not in builder.codemaps
        assert builder._callers_index["funcB"] == ["someOtherFunc"]
        assert builder._callees_index["funcA"] == ["someOtherFunc"]
