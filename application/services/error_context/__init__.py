"""
Error Context Builder - Tao context loi cho AI de fix

Tao error context day du de AI co the hieu va fix ngay:
- Thong tin loi chi tiet
- Previous operations da thanh cong
- Search patterns that failed
- Instructions ro rang de fix
"""

from typing import List, Optional

from application.services.preview_analyzer import PreviewData
from application.services.error_context.formatters import (
    ApplyRowResult,
    build_focused_error_context,
    build_success_section,
    build_failed_section,
    build_fix_instructions,
    read_current_file_content,
    extract_file_paths_from_opx,
)
from infrastructure.adapters.clipboard_utils import copy_to_clipboard


def build_error_context_for_ai(
    preview_data: PreviewData,
    row_results: List[ApplyRowResult],
    original_opx: str = "",
    include_opx: bool = True,
    focused_mode: bool = True,
    workspace_path: Optional[str] = None,
    include_file_content: bool = True,
) -> str:
    """
    Build context day du de AI hieu va fix loi.

    FOCUSED MODE (default): Chỉ cung cấp thông tin cần thiết để fix,
    giảm context không liên quan để AI tập trung hơn.

    ENHANCED: Include current file content để AI có thể fix ngay mà không cần
    hỏi thêm về nội dung file.

    Args:
        preview_data: Preview data tu analyzer
        row_results: Ket qua apply cac rows
        original_opx: OPX goc (optional)
        include_opx: Co bao gom OPX instructions khong
        focused_mode: Neu True, chi hien thi thong tin can thiet de fix
        workspace_path: Path to workspace (for reading current file content)
        include_file_content: Include current content of failed files

    Returns:
        String context cho AI
    """
    sections: List[str] = []

    # Header summary
    success_count = sum(1 for r in row_results if r.success)
    failed_count = sum(1 for r in row_results if not r.success)

    # FOCUSED MODE: Ngắn gọn, đi thẳng vào vấn đề
    if focused_mode and failed_count > 0:
        sections.extend(
            build_focused_error_context(
                row_results,
                preview_data,
                original_opx,
                include_opx,
                workspace_path,
                include_file_content,
            )
        )
        return "\n".join(sections)

    # FULL MODE: Chi tiết đầy đủ (legacy behavior)
    sections.extend(
        [
            "## Apply Results Summary",
            f"- Successful operations: {success_count}",
            f"- Failed operations: {failed_count}",
            f"- Total operations: {len(row_results)}",
            "",
            "---",
            "",
        ]
    )

    # Successful operations (important for context)
    success_rows = [r for r in row_results if r.success]
    if success_rows:
        sections.extend(build_success_section(success_rows, preview_data))

    # Failed operations (need fixing)
    failed_rows = [r for r in row_results if not r.success]
    if failed_rows:
        sections.extend(build_failed_section(failed_rows, preview_data, row_results))

    # Original OPX reference
    if include_opx and original_opx:
        sections.extend(
            [
                "",
                "---",
                "",
                "## Original OPX (For Reference)",
                "",
                "```xml",
                original_opx.strip(),
                "```",
                "",
            ]
        )

    # Fix instructions
    sections.extend(build_fix_instructions(include_opx))

    return "\n".join(sections)


def build_general_error_context(
    error_type: str,
    error_message: str,
    file_path: Optional[str] = None,
    additional_context: Optional[str] = None,
    workspace_path: Optional[str] = None,
) -> str:
    """
    Build context day du cho loi bat ky trong app.

    Cung cap du thong tin de AI co the fix ngay ma khong can hoi lai:
    - Error details
    - File content hien tai (neu co OPX -> extract file paths -> doc content)
    - OPX goc duoc format trong code block
    - Prompt ro rang yeu cau respond bang OPX format

    Args:
        error_type: Loai loi (e.g., "Parse Error", "Apply Error")
        error_message: Message loi
        file_path: File lien quan (optional)
        additional_context: Context them, thuong la OPX goc (optional)
        workspace_path: Workspace root path de doc file content (optional)

    Returns:
        String context day du cho AI fix ngay
    """
    sections = [
        f"# {error_type.upper()} - FIX REQUIRED",
        "",
        f"**Error:** `{error_message}`",
        "",
    ]

    if file_path:
        sections.extend(
            [
                f"**Related File:** `{file_path}`",
                "",
            ]
        )

    # Neu additional_context la OPX, extract file paths va doc content hien tai
    if additional_context and workspace_path:
        affected_files = extract_file_paths_from_opx(additional_context)
        if affected_files:
            sections.append("## Current File Contents")
            sections.append("")
            sections.append(
                "Below are the CURRENT contents of files that need to be fixed. "
                "Use these to locate the exact code sections that need changes."
            )
            sections.append("")
            for fp in affected_files:
                content = read_current_file_content(fp, workspace_path)
                if content:
                    sections.append(f"### `{fp}`")
                    sections.append("```")
                    content_lines = content.split("\n")
                    if len(content_lines) > 300:
                        sections.append("\n".join(content_lines[:300]))
                        sections.append(f"... ({len(content_lines) - 300} more lines)")
                    else:
                        sections.append(content)
                    sections.append("```")
                    sections.append("")

    # OPX goc (format trong code block)
    if additional_context:
        sections.extend(
            [
                "## Original OPX (Failed)",
                "",
                "```xml",
                additional_context.strip(),
                "```",
                "",
            ]
        )

    # Prompt huong dan cho IDE agent (da co edit tool san, khong can OPX)
    sections.extend(
        [
            "---",
            "",
            "# ACTION REQUIRED",
            "",
            "Fix the failed operations based on the error and current file contents above.",
            "All information you need is provided. Do NOT ask questions - start fixing immediately.",
            "",
            "**For each failed operation:**",
            "1. Open the affected file",
            "2. Find the section that needs to be changed (use the current file contents "
            "and the original OPX intent as reference)",
            "3. Apply the intended change directly using your edit tools",
            "",
            "**IMPORTANT:** Only fix the FAILED operations. "
            "Successful operations (if any) are already applied - do NOT touch them.",
            "",
        ]
    )

    return "\n".join(sections)


def copy_error_to_clipboard(context: str) -> bool:
    """
    Copy error context to clipboard.

    Returns:
        True neu thanh cong, False neu that bai
    """
    success, _ = copy_to_clipboard(context)
    return success
