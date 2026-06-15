import unittest
from unittest.mock import MagicMock, patch
from domain.prompt.context_trimmer import ContextTrimmer, PromptComponents
from domain.ports.tokenization_port import ITokenizationService

class DummyTokenizationService(ITokenizationService):
    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        return max(1, len(text) // 4)

    def count_tokens_for_file(self, path: str, use_cache: bool = True) -> int:
        return 0

    def count_tokens_batch_parallel(self, texts: list[str]) -> list[int]:
        return [self.count_tokens(t) for t in texts]

    def clear_cache(self) -> None:
        pass

    def clear_file_from_cache(self, path: str) -> None:
        pass

    def reset_encoder(self) -> None:
        pass

    def set_model_config(self, model_name: str) -> None:
        pass

class TestContextTrimmerExtra(unittest.TestCase):
    def setUp(self):
        self.tok = DummyTokenizationService()

    def test_trim_level0_fit(self):
        # Prompt fits the budget immediately
        comp = PromptComponents(
            instructions="User instruction",
            project_rules="Rules of the project",
            file_map="src/\n  main.py",
            file_contents={"src/main.py": "print('hello')"},
            structure_overhead=10
        )
        trimmer = ContextTrimmer(tokenization_service=self.tok, max_tokens=1000)
        result = trimmer.trim(comp)
        self.assertEqual(result.levels_applied, 0)
        self.assertEqual(result.components.instructions, "User instruction")

    def test_trim_level1_dependencies_removed(self):
        # Large dependency file that should be removed
        comp = PromptComponents(
            instructions="Analyze",
            file_contents={
                "src/main.py": "print('hello')",
                "dep/lib.py": "def large_dep():\n" * 100
            },
            dependency_paths={"dep/lib.py"},
            structure_overhead=5
        )
        # Total tokens will be large due to dep/lib.py
        trimmer = ContextTrimmer(tokenization_service=self.tok, max_tokens=50)
        result = trimmer.trim(comp)
        self.assertEqual(result.levels_applied, 1)
        self.assertNotIn("dep/lib.py", result.components.file_contents)
        self.assertIn("Removed 1 dependency files", result.notes[0])

    def test_trim_level1_dependencies_protected(self):
        # Dependency is protected, shouldn't be removed
        comp = PromptComponents(
            instructions="Analyze",
            file_contents={
                "dep/lib.py": "def large_dep():\n" * 100
            },
            dependency_paths={"dep/lib.py"},
            protected_paths={"dep/lib.py"},
            structure_overhead=5
        )
        trimmer = ContextTrimmer(tokenization_service=self.tok, max_tokens=10)
        result = trimmer.trim(comp)
        self.assertIn("dep/lib.py", result.components.file_contents)

    @patch("domain.smart_context.is_supported")
    @patch("domain.smart_context.smart_parse")
    def test_trim_level1_remove_git_logs_and_diffs(self, mock_smart_parse, mock_is_supported):
        mock_is_supported.return_value = False
        comp = PromptComponents(
            instructions="Analyze",
            file_contents={"src/main.py": "print('hello')"},
            git_logs_text="commit 1\ncommit 2\n" * 20,
            git_diffs_text="diff --git a/src/main.py\n" * 20,
            structure_overhead=5
        )
        # Set max_tokens to fit main.py but not git logs/diffs
        trimmer = ContextTrimmer(tokenization_service=self.tok, max_tokens=20)
        result = trimmer.trim(comp)
        self.assertEqual(result.levels_applied, 1)
        self.assertEqual(result.components.git_logs_text, "")
        self.assertEqual(result.components.git_diffs_text, "")
        self.assertIn("Removed git logs to fit budget.", result.notes)
        self.assertIn("Removed git diffs to fit budget.", result.notes)

    def test_trim_level1_remove_git_logs_only_fit(self):
        # Test line 255: fit after removing git logs only
        comp = PromptComponents(
            instructions="Analyze",
            file_contents={"src/main.py": "print('hello')"}, # ~4 tokens
            git_logs_text="commit 1\n" * 40, # ~40 tokens
            git_diffs_text="diff 1\n" * 4, # ~4 tokens
            structure_overhead=5
        )
        # Total: ~53 tokens. Set max_tokens = 25.
        # After removing logs: ~13 tokens <= 25. Fits!
        trimmer = ContextTrimmer(tokenization_service=self.tok, max_tokens=25)
        result = trimmer.trim(comp)
        self.assertEqual(result.levels_applied, 1)
        self.assertEqual(result.components.git_logs_text, "")
        self.assertNotEqual(result.components.git_diffs_text, "")

    @patch("domain.smart_context.is_supported")
    @patch("domain.smart_context.smart_parse")
    def test_trim_level2_smart_degrade(self, mock_smart_parse, mock_is_supported):
        mock_is_supported.return_value = True
        mock_smart_parse.return_value = "def foo(): pass"

        # Python file supporting smart parse
        comp = PromptComponents(
            instructions="Analyze",
            file_contents={"src/main.py": "def foo():\n    pass\n" * 50},
            structure_overhead=5
        )
        # 1000 chars python file. After smart degrade, it has AST (few lines) + note.
        # Max tokens 100 is enough to fit the degraded file but not the original 250 tokens file.
        trimmer = ContextTrimmer(tokenization_service=self.tok, max_tokens=100)
        result = trimmer.trim(comp)
        self.assertEqual(result.levels_applied, 2)
        # Verify it converted to smart context
        self.assertIn("Smart Context src/main.py", result.notes[0])
        self.assertIn("Converted to Smart Context", comp.file_contents["src/main.py"])

    @patch("domain.smart_context.is_supported")
    def test_trim_level2_truncate_unsupported(self, mock_is_supported):
        mock_is_supported.return_value = False
        # File type not supported by smart parse (e.g. txt)
        comp = PromptComponents(
            instructions="Analyze",
            file_contents={"docs/readme.txt": "A very long readme file...\n" * 100},
            structure_overhead=5
        )
        # Length is ~2600 chars (~650 tokens). Degraded to 30% is ~870 chars (~220 tokens).
        # max_tokens=300 allows it to fit after level 2 degrade.
        trimmer = ContextTrimmer(tokenization_service=self.tok, max_tokens=300)
        result = trimmer.trim(comp)
        self.assertEqual(result.levels_applied, 2)
        self.assertIn("Trimmed docs/readme.txt", result.notes[0])
        self.assertIn("File content trimmed to ~30%", comp.file_contents["docs/readme.txt"])

    @patch("domain.smart_context.is_supported")
    @patch("domain.smart_context.smart_parse")
    def test_trim_level2_smart_degrade_exception(self, mock_smart_parse, mock_is_supported):
        mock_is_supported.return_value = True
        mock_smart_parse.side_effect = Exception("AST parse error")
        # Python file supporting smart parse but raises exception, so fallbacks to truncate
        comp = PromptComponents(
            instructions="Analyze",
            file_contents={"src/main.py": "def foo():\n    pass\n" * 50},
            structure_overhead=5
        )
        # 1000 chars. Truncate 30% + note ~ 114 tokens.
        # Set max_tokens = 150 (exceeds original 256, but fits 114).
        trimmer = ContextTrimmer(tokenization_service=self.tok, max_tokens=150)
        result = trimmer.trim(comp)
        self.assertEqual(result.levels_applied, 2)
        self.assertIn("Trimmed src/main.py", result.notes[0])

    def test_trim_level3_severe_truncate(self):
        # Severe truncate when level 2 wasn't enough
        comp = PromptComponents(
            instructions="Analyze",
            file_contents={"src/main.py": "def foo():\n    pass\n" * 200},
            structure_overhead=5
        )
        # Extreme budget limitation
        trimmer = ContextTrimmer(tokenization_service=self.tok, max_tokens=15)
        result = trimmer.trim(comp)
        self.assertEqual(result.levels_applied, 3)
        self.assertIn("Severely truncated src/main.py to fit budget.", result.notes)
        self.assertIn("File severely truncated", comp.file_contents["src/main.py"])

    def test_trim_level3_warning_over_budget(self):
        comp = PromptComponents(
            instructions="Analyze " * 500,  # Very long instructions (protected)
            file_contents={"src/main.py": "print('hello')"},
            protected_paths={"src/main.py"},
            structure_overhead=5
        )
        trimmer = ContextTrimmer(tokenization_service=self.tok, max_tokens=10)
        result = trimmer.trim(comp)
        self.assertEqual(result.levels_applied, 3)
        # We should get a warning because we cannot fit even after severe truncate
        self.assertTrue(any("WARNING: Could not fit within" in note for note in result.notes))

    def test_trim_level3_early_exit(self):
        comp3 = PromptComponents(
            instructions="Analyze",
            file_contents={
                "src/a.txt": "a" * 4000, # 1000 tokens
                "src/b.txt": "b" * 4000  # 1000 tokens
            },
            structure_overhead=5
        )
        # Level 2 degrades to 30% = 1200 chars (~300 tokens). Total: ~600 tokens (324 each + 6).
        # Set max_tokens = 590.
        # In Level 3:
        # File 1 (src/a.txt) truncated to 800 chars (~200 tokens). New total: 224 + 324 + 6 = 554 <= 590.
        # Loop breaks early on line 361!
        trimmer = ContextTrimmer(tokenization_service=self.tok, max_tokens=590)
        result = trimmer.trim(comp3)
        self.assertEqual(result.levels_applied, 3)
        self.assertIn("Severely truncated src/a.txt to fit budget.", result.notes)
        self.assertNotIn("Severely truncated src/b.txt to fit budget.", result.notes)

    def test_estimate_total_no_cache(self):
        comp = PromptComponents(
            instructions="Inst",
            project_rules="Rules",
            file_map="map",
            file_contents={"a.py": "print(1)", "b.py": "print(2)"}
        )
        trimmer = ContextTrimmer(tokenization_service=self.tok, max_tokens=100)
        # Calling estimate_total directly without cache
        total = trimmer._estimate_total(comp, file_token_cache=None)
        expected = trimmer._count("Inst") + trimmer._count("Rules") + trimmer._count("map") + trimmer._count("print(1)") + trimmer._count("print(2)")
        self.assertEqual(total, expected)

    @patch("domain.smart_context.is_supported")
    @patch("domain.smart_context.smart_parse")
    def test_trim_early_exit_loops(self, mock_smart_parse, mock_is_supported):
        mock_is_supported.return_value = True
        mock_smart_parse.return_value = "def foo(): pass"

        # Test early break in loops when budget is met mid-way
        comp = PromptComponents(
            instructions="Analyze",
            file_contents={
                "src/a.py": "def foo():\n    pass\n" * 50,
                "src/b.py": "def bar():\n    pass\n" * 50
            },
            structure_overhead=5
        )
        # Initial: 2 files * 250 tokens = 500 tokens.
        # Set max_tokens = 400. Degrade src/a.py (first file, ~35 tokens). New total: 285 tokens <= 400.
        # Loops should break and levels_applied = 2.
        trimmer = ContextTrimmer(tokenization_service=self.tok, max_tokens=400)
        result = trimmer.trim(comp)
        self.assertEqual(result.levels_applied, 2)
        # Verify one file is degraded and the other is not
        self.assertTrue(
            ("Smart Context src/a.py" in "".join(result.notes) and "Smart Context src/b.py" not in "".join(result.notes)) or
            ("Smart Context src/b.py" in "".join(result.notes) and "Smart Context src/a.py" not in "".join(result.notes))
        )

        # Early exit from level 3
        comp2 = PromptComponents(
            instructions="Analyze",
            file_contents={
                "src/a.py": "a" * 1000, # 250 tokens
                "src/b.py": "b" * 1000  # 250 tokens
            },
            protected_paths={"src/b.py"},
            structure_overhead=5
        )
        # Initial: 500 tokens. Max tokens: 350.
        # Degrade level 2 for src/a.py -> 30% = 300 chars = 75 tokens. New total: 330 <= 350.
        # So we need another scenario for level 3 early exit.
        # Let's say max_tokens is very small but one file is protected and we exit early.
        comp3 = PromptComponents(
            instructions="Analyze",
            file_contents={
                "src/a.py": "a" * 1000, # 250 tokens
                "src/b.py": "b" * 1000, # 250 tokens
                "src/c.py": "c" * 1000  # 250 tokens
            },
            structure_overhead=5
        )
        # Initial: 750 tokens. Set max_tokens = 400.
        # Level 2 degrades all files: 3 * 75 tokens = 225 tokens <= 400. Fits.
        # Let's force level 3. Let's make max_tokens = 60.
        # Level 2: all files degraded to 75 tokens. Total 225 > 60.
        # Level 3: c.py truncated.
        trimmer3 = ContextTrimmer(tokenization_service=self.tok, max_tokens=60)
        result3 = trimmer3.trim(comp3)
        self.assertEqual(result3.levels_applied, 3)
