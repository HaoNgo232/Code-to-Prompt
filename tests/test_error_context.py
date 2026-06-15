"""
Tests cho module Error Context Builder trong application/services/error_context/
"""

import pytest
from pathlib import Path
from typing import List

from application.services.preview_analyzer import PreviewData, PreviewRow, ChangeSummary
from application.services.error_context import (
    build_error_context_for_ai,
    build_general_error_context,
)
from application.services.error_context.formatters import (
    ApplyRowResult,
    build_success_section,
    build_failed_section,
    read_current_file_content,
    extract_file_paths_from_opx,
)


@pytest.fixture
def sample_preview_data() -> PreviewData:
    """Tạo PreviewData mẫu phục vụ kiểm thử."""
    row1 = PreviewRow(
        path="main.py",
        action="modify",
        description="Fix import",
        changes=ChangeSummary(added=1, removed=1),
        change_blocks=[{
            "description": "Block 1",
            "search": "import os",
            "content": "import os\nimport sys"
        }]
    )
    row2 = PreviewRow(
        path="domain/model.py",
        action="modify",
        description="Add class field",
        changes=ChangeSummary(added=1, removed=0),
        change_blocks=[{
            "description": "Block 1",
            "search": "class Model:\n    pass",
            "content": "class Model:\n    name: str"
        }]
    )
    return PreviewData(rows=[row1, row2])


def test_apply_row_result_dataclass():
    """Test thuộc tính của ApplyRowResult."""
    res = ApplyRowResult(
        row_index=0,
        path="main.py",
        action="modify",
        success=False,
        message="Search pattern not found",
        is_cascade_failure=True
    )
    assert res.row_index == 0
    assert res.path == "main.py"
    assert res.success is False
    assert res.is_cascade_failure is True


def test_read_current_file_content(tmp_path: Path):
    """Test đọc file hiện tại với các điều kiện khác nhau."""
    # File hợp lệ
    test_file = tmp_path / "test.py"
    test_file.write_text("print('hello')", encoding="utf-8")
    
    content = read_current_file_content("test.py", str(tmp_path))
    assert content == "print('hello')"

    # File không tồn tại
    assert read_current_file_content("nonexistent.py", str(tmp_path)) is None

    # File quá lớn (giả lập > 100KB)
    large_file = tmp_path / "large.py"
    large_file.write_text("x" * 100005, encoding="utf-8")
    assert read_current_file_content("large.py", str(tmp_path)) is None


def test_extract_file_paths_from_opx():
    """Test trích xuất file paths từ OPX XML format."""
    opx = """
<opx>
  <edit file="main.py">
    some search/replace
  </edit>
  <edit file="domain/model.py">
    other search/replace
  </edit>
  <edit file="main.py">
    duplicate file
  </edit>
</opx>
"""
    paths = extract_file_paths_from_opx(opx)
    assert paths == ["main.py", "domain/model.py"]


def test_build_error_context_for_ai_focused(tmp_path: Path, sample_preview_data: PreviewData):
    """Test build error context ở chế độ FOCUSED."""
    # Ghi file test để test việc đọc file content
    main_file = tmp_path / "main.py"
    main_file.write_text("import os", encoding="utf-8")

    results = [
        ApplyRowResult(row_index=0, path="main.py", action="modify", success=False, message="Not found", is_cascade_failure=True),
        ApplyRowResult(row_index=1, path="domain/model.py", action="modify", success=True, message="Success")
    ]

    context = build_error_context_for_ai(
        preview_data=sample_preview_data,
        row_results=results,
        focused_mode=True,
        workspace_path=str(tmp_path),
        include_file_content=True
    )

    assert "OPX APPLY FAILED - FIX REQUIRED" in context
    assert "1 operation(s) failed." in context
    assert "**ERROR:** `Not found`" in context
    assert "CASCADE FAILURE" in context
    assert "CURRENT FILE CONTENT" in context
    assert "import os" in context  # từ file content
    assert "Search block that FAILED to match:" in context
    assert "Successfully Applied" in context


def test_build_error_context_for_ai_full(tmp_path: Path, sample_preview_data: PreviewData):
    """Test build error context ở chế độ FULL (legacy)."""
    results = [
        ApplyRowResult(row_index=0, path="main.py", action="modify", success=False, message="Not found"),
        ApplyRowResult(row_index=1, path="domain/model.py", action="modify", success=True, message="Success")
    ]

    context = build_error_context_for_ai(
        preview_data=sample_preview_data,
        row_results=results,
        original_opx="<opx></opx>",
        include_opx=True,
        focused_mode=False,
        workspace_path=str(tmp_path)
    )

    assert "Apply Results Summary" in context
    assert "Successful operations: 1" in context
    assert "Failed operations: 1" in context
    assert "Successfully Applied Operations" in context
    assert "FAILED Operations" in context
    assert "Original OPX (For Reference)" in context


def test_build_general_error_context(tmp_path: Path):
    """Test tạo ngữ cảnh lỗi chung trong ứng dụng."""
    # Tạo mock file
    test_file = tmp_path / "main.py"
    test_file.write_text("print('core')", encoding="utf-8")

    opx_text = '<edit file="main.py"></edit>'

    context = build_general_error_context(
        error_type="Parse Error",
        error_message="Invalid tags",
        file_path="main.py",
        additional_context=opx_text,
        workspace_path=str(tmp_path)
    )

    assert "PARSE ERROR - FIX REQUIRED" in context
    assert "**Error:** `Invalid tags`" in context
    assert "**Related File:** `main.py`" in context
    assert "Current File Contents" in context
    assert "print('core')" in context
    assert "Original OPX (Failed)" in context
    assert "ACTION REQUIRED" in context
