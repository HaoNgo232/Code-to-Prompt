"""
Tests for domain/prompt/formatters/xml.py and domain/prompt/formatters/plain.py.

Targets missing coverage:
- xml.py line 46 (error branch), 52-55 (dependencies block), 74 (empty returns)
- plain.py lines 33-38 (error branches), 43 (dependencies), 48 (None content no error), 56 (empty)
"""

from pathlib import Path


from shared.types.prompt_types import FileEntry
from domain.prompt.formatters.xml import (
    format_files_xml,
    format_files_xml_elements,
    generate_file_summary_xml,
    generate_smart_summary_xml,
    generate_file_summary_xml_minimal,
)
from domain.prompt.formatters.plain import format_files_plain


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(
    display_path: str = "file.py",
    content: str | None = "x = 1",
    error: str | None = None,
    language: str = "python",
    dependencies: list[str] | None = None,
) -> FileEntry:
    """Build a FileEntry with sane defaults."""
    return FileEntry(
        path=Path(display_path),
        display_path=display_path,
        content=content,
        error=error,
        language=language,
        dependencies=dependencies,
    )


# ===========================================================================
# XML Formatter Tests
# ===========================================================================


class TestFormatFilesXml:
    """Tests for format_files_xml() and format_files_xml_elements()."""

    def test_empty_list_returns_empty_tag(self):
        """format_files_xml with no entries returns '<files></files>' (line 74)."""
        result = format_files_xml([])
        assert result == "<files></files>"

    def test_error_entry_renders_skipped_attribute(self):
        """Entry with error renders skipped='true' (line 46)."""
        entry = _make_entry(
            display_path="error.py", content=None, error="File not found"
        )
        result = format_files_xml([entry])
        assert 'skipped="true"' in result
        assert "File not found" in result
        assert "error.py" in result

    def test_error_entry_skips_content_block(self):
        """Error entries must NOT contain a <content> element."""
        entry = _make_entry(
            display_path="bad.py", content=None, error="Permission denied"
        )
        result = format_files_xml([entry])
        assert "<content>" not in result

    def test_dependencies_block_rendered_when_non_empty(self):
        """Dependencies block is rendered when entry.dependencies is non-empty (lines 52-55)."""
        entry = _make_entry(
            display_path="app.py",
            content="import os",
            dependencies=["os", "sys"],
        )
        result = format_files_xml([entry])
        assert "<dependencies>" in result
        assert "<import>os</import>" in result
        assert "<import>sys</import>" in result

    def test_dependencies_block_absent_when_empty(self):
        """No <dependencies> element when entry.dependencies is None."""
        entry = _make_entry(display_path="app.py", content="x = 1", dependencies=None)
        result = format_files_xml([entry])
        assert "<dependencies>" not in result

    def test_cdata_escape_replaces_end_sequence(self):
        """CDATA end sequence ']]>' is escaped inside content (safe_content logic)."""
        entry = _make_entry(display_path="test.py", content="x = ']]>'")
        result = format_files_xml([entry])
        # The escape strategy replaces ']]>' with ']]]]><![CDATA[>'
        # so the original ']]>' sequence is split across two CDATA blocks.
        assert "]]]]><![CDATA[>" in result

    def test_file_path_is_html_escaped(self):
        """display_path with HTML special chars is escaped in output."""
        entry = _make_entry(display_path="a<b>.py", content="x = 1")
        result = format_files_xml([entry])
        assert "a<b>.py" not in result  # raw < not present
        assert "a&lt;b&gt;.py" in result

    def test_multiple_entries_all_rendered(self):
        """Multiple entries are all included in output."""
        entries = [
            _make_entry(display_path="a.py", content="a = 1"),
            _make_entry(display_path="b.py", content="b = 2"),
        ]
        result = format_files_xml(entries)
        assert "a.py" in result
        assert "b.py" in result

    def test_entry_with_none_content_and_no_error_skipped(self):
        """Entry with content=None and error=None produces no <file> element."""
        entry = _make_entry(display_path="empty.py", content=None, error=None)
        result = format_files_xml([entry])
        # Neither error branch nor content branch fires → no element added
        assert result == "<files></files>"

    def test_format_files_xml_elements_returns_list(self):
        """format_files_xml_elements returns a list of strings."""
        entry = _make_entry(display_path="x.py", content="pass")
        elements = format_files_xml_elements([entry])
        assert isinstance(elements, list)
        assert len(elements) == 1

    def test_generate_file_summary_xml_contains_expected_tags(self):
        """generate_file_summary_xml returns non-empty XML string."""
        result = generate_file_summary_xml()
        assert "<file_summary>" in result
        assert "</file_summary>" in result

    def test_generate_smart_summary_xml_contains_expected_tags(self):
        """generate_smart_summary_xml returns non-empty XML string."""
        result = generate_smart_summary_xml()
        assert "<file_summary>" in result
        assert "</file_summary>" in result

    def test_generate_file_summary_xml_minimal_contains_expected_tags(self):
        """generate_file_summary_xml_minimal returns non-empty XML string."""
        result = generate_file_summary_xml_minimal()
        assert "<file_summary>" in result
        assert "</file_summary>" in result


# ===========================================================================
# Plain Formatter Tests
# ===========================================================================


class TestFormatFilesPlain:
    """Tests for format_files_plain()."""

    def test_empty_list_returns_no_files_message(self):
        """format_files_plain([]) returns 'No files selected.' (line 56)."""
        result = format_files_plain([])
        assert result == "No files selected."

    def test_binary_file_error_branch(self):
        """'Binary file' error maps to 'Binary file (skipped)' (line 33-34)."""
        entry = _make_entry(display_path="image.png", content=None, error="Binary file")
        result = format_files_plain([entry])
        assert "Binary file (skipped)" in result

    def test_file_too_large_error_branch(self):
        """'File too large' prefix error appends ' (skipped)' (line 35-36)."""
        entry = _make_entry(
            display_path="huge.log",
            content=None,
            error="File too large: 10MB",
        )
        result = format_files_plain([entry])
        assert "File too large: 10MB (skipped)" in result

    def test_other_error_branch_raw_message(self):
        """Generic error string is used verbatim as content_display (line 37-38)."""
        entry = _make_entry(
            display_path="broken.py", content=None, error="Permission denied"
        )
        result = format_files_plain([entry])
        assert "Permission denied" in result
        # Must NOT add '(skipped)' suffix for generic errors
        assert "(skipped)" not in result

    def test_dependencies_rendered_in_meta_block(self):
        """DEPENDS ON line is inserted when entry.dependencies is non-empty (line 43)."""
        entry = _make_entry(
            display_path="app.py",
            content="import os",
            dependencies=["os", "sys"],
        )
        result = format_files_plain([entry])
        assert "DEPENDS ON: os, sys" in result

    def test_no_depends_on_when_dependencies_none(self):
        """No DEPENDS ON line when entry.dependencies is None."""
        entry = _make_entry(
            display_path="app.py", content="import os", dependencies=None
        )
        result = format_files_plain([entry])
        assert "DEPENDS ON" not in result

    def test_none_content_no_error_uses_empty_display(self):
        """entry with content=None and error=None renders empty content_display (line 48)."""
        entry = _make_entry(display_path="empty.py", content=None, error=None)
        result = format_files_plain([entry])
        # FILE header should be present
        assert "FILE: empty.py" in result
        # The content block after separator should be empty / just whitespace
        lines = result.splitlines()
        header_idx = next(
            i for i, l in enumerate(lines) if l.startswith("FILE: empty.py")
        )
        # After header + separator, remaining lines should contain no actual code
        rest = "\n".join(lines[header_idx + 2 :])
        assert rest.strip() == ""

    def test_normal_content_included_in_output(self):
        """Regular content is rendered in output."""
        entry = _make_entry(display_path="script.py", content="print('hello')")
        result = format_files_plain([entry])
        assert "FILE: script.py" in result
        assert "print('hello')" in result

    def test_separator_line_matches_path_length(self):
        """Separator dashes length equals len(display_path) + 6."""
        path = "src/main.py"
        entry = _make_entry(display_path=path, content="pass")
        result = format_files_plain([entry])
        expected_sep = "-" * (len(path) + 6)
        assert expected_sep in result

    def test_multiple_entries_joined_by_double_newline(self):
        """Multiple entries are joined with '\\n\\n'."""
        entries = [
            _make_entry(display_path="a.py", content="a = 1"),
            _make_entry(display_path="b.py", content="b = 2"),
        ]
        result = format_files_plain(entries)
        assert "a.py" in result
        assert "b.py" in result
        assert "\n\n" in result
