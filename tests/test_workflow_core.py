"""
Tests cho các workflow cốt lõi trong domain/workflow/ và các module dùng chung.
"""

import os
from pathlib import Path
from typing import Dict, List
import pytest
from unittest.mock import MagicMock, patch

from domain.errors import DomainValidationError
from domain.workflow.refactor_workflow import run_refactor_discovery, run_refactor_planning, DiscoveryReport, RefactorPlan
from domain.workflow.code_reviewer import run_code_review, ReviewResult, _calculate_diff_stats, _extract_filename_from_diff_header
from domain.workflow.design_planner import run_design_planner, DesignResult, _identify_impacted_modules
from domain.workflow.shared.artifact_formatter import (
    ArtifactMetadata,
    build_artifact_metadata,
    format_artifact_with_metadata,
)
from domain.workflow.shared.handoff_formatter import (
    HandoffContext,
    format_handoff_xml,
    format_relationships_section,
)
from domain.workflow.shared.risk_engine import (
    analyze_blast_radius,
    BlastRadiusResult,
    _calculate_risk_score,
)
from domain.ports.registry import DomainRegistry
from shared.types.git_types import GitDiffResult


class DummyWorkspaceScanner:
    """Mock WorkspaceScanner để hỗ trợ kiểm thử file collection."""
    def collect_files(self, workspace_path: Path) -> List[str]:
        paths = []
        # Đi bộ qua thư mục và thu thập relative paths
        for root, dirs, files in os.walk(workspace_path):
            for file in files:
                full_path = Path(root) / file
                paths.append(str(full_path))
        return paths


@pytest.fixture(autouse=True)
def setup_workspace_scanner():
    """Tự động đăng ký DummyWorkspaceScanner nếu DomainRegistry chưa có."""
    try:
        DomainRegistry.workspace_scanner()
    except RuntimeError:
        DomainRegistry.register_workspace_scanner(DummyWorkspaceScanner())


@pytest.fixture
def test_ws(tmp_path: Path) -> Path:
    """Tạo workspace mẫu chứa một vài file mã nguồn để test."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    
    # Tạo cấu trúc thư mục
    app_dir = ws / "application"
    app_dir.mkdir()
    domain_dir = ws / "domain"
    domain_dir.mkdir()
    
    (ws / "main.py").write_text("import domain.model\ndef main():\n    pass", encoding="utf-8")
    (domain_dir / "model.py").write_text("class Model:\n    def __init__(self):\n        pass", encoding="utf-8")
    (app_dir / "service.py").write_text("from domain.model import Model\nclass Service:\n    pass", encoding="utf-8")
    
    # Python tests
    tests_dir = ws / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_model.py").write_text("def test_model():\n    assert True", encoding="utf-8")

    return ws


# ===========================================================================
# Risk Engine Tests
# ===========================================================================

def test_risk_engine_logic(test_ws: Path):
    """Test đánh giá mức độ rủi ro dựa trên tệp thay đổi và độ sâu dependency."""
    # Test low risk
    result_low = BlastRadiusResult(
        changed=["tests/test_model.py"],
        first_order_dependents=[],
        transitive_dependents=[],
        related_tests=[]
    )
    score_low = _calculate_risk_score(result_low)
    # 0.2 vì không có test files related
    assert score_low == 0.2

    # Test high risk
    result_high = BlastRadiusResult(
        changed=["domain/model.py", "main.py"],
        first_order_dependents=["main.py", "app/service.py"],
        transitive_dependents=[("other.py", 2)],
        related_tests=[]
    )
    score_high = _calculate_risk_score(result_high)
    assert score_high > 0.3

    # Test analyze_blast_radius thực tế
    analysis = analyze_blast_radius(
        workspace_root=test_ws,
        target_files=[test_ws / "domain/model.py"],
        max_depth=2
    )
    assert isinstance(analysis, BlastRadiusResult)
    # Changed files trả về relative path
    assert len(analysis.changed) > 0


# ===========================================================================
# Artifact Formatter Tests
# ===========================================================================

def test_artifact_formatter(test_ws: Path):
    """Test xây dựng metadata và định dạng artifact với metadata."""
    metadata = build_artifact_metadata(
        workspace_root=test_ws,
        workflow_name="rp_review",
        task_description="Test task description",
    )
    
    assert metadata.workflow_name == "rp_review"
    assert metadata.task_description == "Test task description"
    assert metadata.memory_summary is not None
    assert metadata.memory_summary["total_entries"] == 0

    # Test format JSON
    json_out = format_artifact_with_metadata("artifact code content", metadata, format_type="json")
    assert '"content": "artifact code content"' in json_out
    assert '"workflow_name": "rp_review"' in json_out

    # Test format XML
    xml_out = format_artifact_with_metadata("artifact code content", metadata, format_type="xml")
    assert "<artifact>" in xml_out
    assert "<workflow>rp_review</workflow>" in xml_out
    assert "artifact code content" in xml_out


# ===========================================================================
# Handoff Formatter Tests
# ===========================================================================

def test_handoff_formatter(test_ws: Path):
    """Test handoff formatter xml generation và relationships parser."""
    context = HandoffContext(
        task_description="Explain layout",
        file_contents={"main.py": "import auth"},
        file_map="src/\n  main.py",
        relationships="main.py -> auth",
        action_instructions="Analyze main",
        metadata={"tokens": 100},
        extra_sections={"test_section": "<data>val</data>"}
    )

    prompt = format_handoff_xml(context)
    assert "<synapse_context>" in prompt
    assert "<task>" in prompt
    assert "Explain layout" in prompt
    assert '<file path="main.py">' in prompt
    assert "<instructions>" in prompt
    assert "Analyze main" in prompt
    assert "<test_section>\n<data>val</data>\n</test_section>" in prompt
    assert "tokens: 100" in prompt

    # Relationships section
    rel_section = format_relationships_section(test_ws, ["application/service.py", "domain/model.py"])
    # Cần tìm thấy dependencies
    assert "application/service.py" in rel_section or "domain/model.py" in rel_section


# ===========================================================================
# Refactor Workflow Tests
# ===========================================================================

def test_refactor_discovery_basic(test_ws: Path):
    """Test Pass 1 - Refactor Discovery."""
    # Run discovery với symbol tìm kiếm có heuristic
    report = run_refactor_discovery(
        workspace_path=str(test_ws),
        refactor_scope="Refactor 'Model' in model.py",
        file_paths=["domain/model.py"]
    )
    
    assert isinstance(report, DiscoveryReport)
    assert "domain/model.py" in report.scope_files
    assert "<synapse_context>" in report.prompt


def test_refactor_discovery_no_files(test_ws: Path):
    """Test Discovery khi không tìm thấy file nào phù hợp."""
    report = run_refactor_discovery(
        workspace_path=str(test_ws),
        refactor_scope="Do nothing scope",
        file_paths=[]
    )
    assert len(report.scope_files) == 0
    assert "Error" in report.prompt


def test_refactor_discovery_invalid_dir():
    """Test Discovery lỗi khi workspace không hợp lệ."""
    with pytest.raises(DomainValidationError):
        run_refactor_discovery(
            workspace_path="/nonexistent/path/dir",
            refactor_scope="Test"
        )


def test_refactor_planning_basic(test_ws: Path):
    """Test Pass 2 - Refactor Planning."""
    report_text = "Here is the discovery report mentioning domain/model.py and main.py."
    plan = run_refactor_planning(
        workspace_path=str(test_ws),
        refactor_scope="Refactor Model",
        discovery_report_text=report_text,
        file_paths=["domain/model.py"]
    )
    
    assert isinstance(plan, RefactorPlan)
    assert plan.files_to_modify == ["domain/model.py"]
    assert "<synapse_context>" in plan.prompt


def test_refactor_planning_heuristic_extract(test_ws: Path):
    """Test planning tự động trích xuất file từ discovery report."""
    report_text = "Modify file domain/model.py to change Model class."
    plan = run_refactor_planning(
        workspace_path=str(test_ws),
        refactor_scope="Refactor Model",
        discovery_report_text=report_text
    )
    assert "domain/model.py" in plan.files_to_modify


def test_refactor_planning_no_files_found(test_ws: Path):
    """Test planning khi không trích xuất được file nào."""
    plan = run_refactor_planning(
        workspace_path=str(test_ws),
        refactor_scope="Refactor Model",
        discovery_report_text="No files referenced here"
    )
    assert plan.files_to_modify == []
    assert "Error" in plan.prompt


# ===========================================================================
# Design Planner Workflow Tests
# ===========================================================================

def test_design_planner_basic(test_ws: Path):
    """Test Design Planner workflow."""
    result = run_design_planner(
        workspace_path=str(test_ws),
        task_description="Design database integration",
        file_paths=["domain/model.py"]
    )
    
    assert isinstance(result, DesignResult)
    assert result.files_included >= 1
    assert "domain" in result.impacted_modules
    assert result.scope_summary != ""


def test_design_planner_path_traversal(test_ws: Path):
    """Test path traversal của output_file trong design planner."""
    with pytest.raises(DomainValidationError, match="path traversal"):
        run_design_planner(
            workspace_path=str(test_ws),
            task_description="Test",
            output_file="../outside.xml"
        )


def test_design_planner_no_files(test_ws: Path):
    """Test design planner khi scope trống."""
    # Dùng list rỗng
    result = run_design_planner(
        workspace_path=str(test_ws),
        task_description="Test empty",
        file_paths=[]
    )
    assert "Error" in result.prompt


def test_identify_impacted_modules():
    """Test helper _identify_impacted_modules."""
    files = ["domain/model.py", "application/service.py", "main.py"]
    modules = _identify_impacted_modules(files)
    assert modules == ["(root)", "application", "domain"]


# ===========================================================================
# Code Reviewer Workflow Tests
# ===========================================================================

def test_calculate_diff_stats():
    """Test helper tính toán insertions/deletions từ diff."""
    diff_text = """
--- a/main.py
+++ b/main.py
@@ -1,3 +1,4 @@
-old line
+new line 1
+new line 2
    unchanged line
"""
    stats = _calculate_diff_stats(diff_text)
    assert stats == {"insertions": 2, "deletions": 1}


def test_extract_filename_from_diff_header():
    """Test helper trích xuất file name từ git diff header."""
    assert _extract_filename_from_diff_header("diff --git a/src/main.py b/src/main.py") == "src/main.py"
    assert _extract_filename_from_diff_header("diff --git a/old.py b/new.py") == "new.py"
    assert _extract_filename_from_diff_header("diff --git a/sub/b/test.py b/sub/b/test.py") == "sub/b/test.py"
    assert _extract_filename_from_diff_header("diff --git a/invalid") is None


def test_code_reviewer_basic(test_ws: Path):
    """Test Code Reviewer workflow với mock git diff."""
    mock_git = MagicMock()
    mock_git.get_diffs.return_value = GitDiffResult(
        work_tree_diff="diff --git a/domain/model.py b/domain/model.py\n+new line",
        staged_diff=""
    )
    
    result = run_code_review(
        workspace_path=str(test_ws),
        review_focus="security",
        git_service=mock_git
    )
    
    assert isinstance(result, ReviewResult)
    # files_changed của ReviewResult được tính từ scope.primary_files
    # do changed_files trong detect_scope_from_git_diff là ["domain/model.py"]
    # và file này tồn tại trên đĩa nên files_changed phải bằng 1
    assert result.files_changed == 1
    assert result.diff_stats == {"insertions": 1, "deletions": 0}
    assert "<synapse_context>" in result.prompt


def test_code_reviewer_no_changes(test_ws: Path):
    """Test Code Reviewer khi git diff trống."""
    mock_git = MagicMock()
    mock_git.get_diffs.return_value = None
    
    result = run_code_review(
        workspace_path=str(test_ws),
        git_service=mock_git
    )
    assert result.files_changed == 0
    assert "No changes" in result.prompt


def test_code_reviewer_invalid_dir():
    """Test Code Reviewer khi workspace path sai."""
    with pytest.raises(DomainValidationError):
        run_code_review(
            workspace_path="/nonexistent/path/dir"
        )
