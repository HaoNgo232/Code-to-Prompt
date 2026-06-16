import unittest
from pathlib import Path
from domain.prompt.assembler import (
    assemble_prompt,
    assemble_smart_prompt,
    _strip_xml_simple,
)
from domain.config.output_format import OutputStyle
from shared.types.git_types import GitDiffResult, GitLogResult


class TestPromptAssemblerExtra(unittest.TestCase):
    def test_assemble_prompt_fallback(self):
        # Trigger fallback to XML style when OutputStyle is unknown
        prompt = assemble_prompt(
            file_map="src/",
            file_contents="print('hello')",
            user_instructions="Fix bug",
            output_style=999,  # Invalid style
        )
        self.assertIn("<project>", prompt)
        self.assertIn("<file_summary>", prompt)

    def test_assemble_prompt_legacy_strip(self):
        # Test legacy format clean
        user_inst = "My instructions\n## Output format\nLegacy detail"
        prompt = assemble_prompt(
            file_map="src/",
            file_contents="print('hello')",
            user_instructions=user_inst,
            output_style=OutputStyle.XML,
        )
        self.assertIn("My instructions", prompt)
        self.assertNotIn("Legacy detail", prompt)

        user_inst_2 = "My instructions 2\n## REPORT STRUCTURE\nLegacy structure"
        prompt_2 = assemble_prompt(
            file_map="src/",
            file_contents="print('hello')",
            user_instructions=user_inst_2,
            output_style=OutputStyle.XML,
        )
        self.assertIn("My instructions 2", prompt_2)
        self.assertNotIn("Legacy structure", prompt_2)

    def test_assemble_smart_prompt_plain(self):
        prompt = assemble_smart_prompt(
            smart_contents="class A:",
            file_map="src/",
            user_instructions="Do something",
            output_style=OutputStyle.PLAIN,
        )
        self.assertIn("SYSTEM INSTRUCTION (SMART CONTEXT)", prompt)
        self.assertIn("COMPRESSED FILE CONTEXT", prompt)

    def test_assemble_smart_prompt_instructions_at_top(self):
        prompt = assemble_smart_prompt(
            smart_contents="class A:",
            file_map="src/",
            user_instructions="Do something",
            project_rules="Rule A",
            semantic_index="<index>index_val</index>",
            instructions_at_top=True,
            output_style=OutputStyle.XML,
        )
        self.assertTrue(
            prompt.startswith("<user_instructions>\nDo something\n</user_instructions>")
        )
        self.assertIn("<project_rules>\nRule A\n</project_rules>", prompt)
        self.assertIn("<index>index_val</index>", prompt)

    def test_assemble_smart_prompt_instructions_at_bottom(self):
        prompt = assemble_smart_prompt(
            smart_contents="class A:",
            file_map="src/",
            user_instructions="Do something",
            project_rules="Rule A",
            semantic_index="<index>index_val</index>",
            instructions_at_top=False,
            output_style=OutputStyle.XML,
        )
        self.assertTrue(prompt.endswith("</user_instructions>"))
        self.assertIn("<project_rules>\nRule A\n</project_rules>", prompt)
        self.assertIn("<index>index_val</index>", prompt)

    def test_assemble_smart_plain_with_options(self):
        git_diffs = GitDiffResult(work_tree_diff="diff1", staged_diff="diff2")
        prompt = assemble_smart_prompt(
            smart_contents="class A:",
            file_map="src/",
            user_instructions="Do something",
            project_rules="Rule A",
            semantic_index='<index total_files="5">index_val</index>',
            instructions_at_top=True,
            git_diffs=git_diffs,
            output_style=OutputStyle.PLAIN,
        )
        self.assertIn("PROJECT RULES", prompt)
        self.assertIn("SEMANTIC INDEX", prompt)
        self.assertIn("GIT CHANGES", prompt)

    def test_assemble_smart_plain_instructions_bottom(self):
        prompt = assemble_smart_prompt(
            smart_contents="class A:",
            file_map="src/",
            user_instructions="Do something",
            project_rules="Rule A",
            instructions_at_top=False,
            output_style=OutputStyle.PLAIN,
        )
        self.assertTrue(prompt.endswith("Do something"))

    def test_assemble_xml_with_options(self):
        git_diffs = GitDiffResult(work_tree_diff="diff1", staged_diff="diff2")
        git_logs = GitLogResult(log_content="log1", commits=[])
        prompt = assemble_prompt(
            file_map="src/",
            file_contents="print('hello')",
            user_instructions="Do something",
            project_rules="Rule A",
            semantic_index="<index>index_val</index>",
            instructions_at_top=True,
            git_diffs=git_diffs,
            git_logs=git_logs,
            output_style=OutputStyle.XML,
            include_xml_formatting=True,
            workspace_root=Path("/workspace"),
        )
        self.assertIn("<git_diff_staged>\ndiff2\n</git_diff_staged>", prompt)
        self.assertIn("<reminder>\n    REITERATION:", prompt)
        self.assertIn("<name>workspace</name>", prompt)

    def test_assemble_xml_instructions_at_bottom(self):
        prompt = assemble_prompt(
            file_map="src/",
            file_contents="print('hello')",
            user_instructions="Do something",
            project_rules="Rule A",
            semantic_index="<index>index_val</index>",
            instructions_at_top=False,
            output_style=OutputStyle.XML,
        )
        self.assertIn("<project_rules>\nRule A\n  </project_rules>", prompt)
        self.assertIn(
            "<user_instructions>\nDo something\n  </user_instructions>", prompt
        )
        self.assertIn("<index>index_val</index>", prompt)

    def test_assemble_plain_with_options(self):
        git_diffs = GitDiffResult(work_tree_diff="diff1", staged_diff="diff2")
        git_logs = GitLogResult(log_content="log1", commits=[])
        prompt = assemble_prompt(
            file_map="src/",
            file_contents="print('hello')",
            user_instructions="Do something",
            project_rules="Rule A",
            semantic_index="<index>index_val</index>",
            instructions_at_top=True,
            git_diffs=git_diffs,
            git_logs=git_logs,
            output_style=OutputStyle.PLAIN,
            include_xml_formatting=True,
        )
        self.assertIn("Work Tree Diff:\ndiff1", prompt)
        self.assertIn("Staged Diff:\ndiff2", prompt)
        self.assertIn("Git Logs:\nlog1", prompt)
        self.assertIn("REMINDER", prompt)

    def test_assemble_plain_instructions_bottom(self):
        prompt = assemble_prompt(
            file_map="src/",
            file_contents="print('hello')",
            user_instructions="Do something",
            project_rules="Rule A",
            semantic_index="<index>index_val</index>",
            instructions_at_top=False,
            output_style=OutputStyle.PLAIN,
        )
        self.assertIn("PROJECT RULES", prompt)
        self.assertIn("USER INSTRUCTIONS", prompt)
        self.assertIn("SEMANTIC INDEX", prompt)

    def test_strip_xml_simple(self):
        # Empty input
        self.assertEqual(_strip_xml_simple(""), "")
        # Attribute only
        self.assertEqual(
            _strip_xml_simple('<tag total_files="5"/>'), "Metadata: total_files: 5"
        )
        self.assertEqual(
            _strip_xml_simple('<tag path="a.py" dependents="2"/>'),
            "Metadata: path: a.py, dependents: 2",
        )
        # Mixed content
        self.assertEqual(_strip_xml_simple("<tag>hello</tag>"), "hello")
        # Multi newline cleanup
        self.assertEqual(_strip_xml_simple("hello\n\n\n\nworld"), "hello\n\nworld")
