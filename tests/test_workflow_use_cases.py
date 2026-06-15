"""
Tests cho Workflow Engine và Workflow Use Cases trong application/use_cases/
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from application.errors import UseCaseValidationError, WorkflowExecutionError
from application.use_cases.workflow_engine import (
    WorkflowContext,
    WorkflowEvent,
    WorkflowEngine,
    CallableWorkflowStep,
    IWorkflowObserver,
)
from application.use_cases.workflow_use_cases import (
    _ensure_workspace_dir,
    _ensure_output_inside_workspace,
    BuildContextCommand,
    BuildContextUseCase,
    CodeReviewCommand,
    CodeReviewUseCase,
    RefactorCommand,
    RefactorUseCase,
    InvestigateCommand,
    InvestigateUseCase,
    TestBuildCommand,
    TestBuildUseCase,
    DesignPlannerCommand,
    DesignPlannerUseCase,
)
from domain.errors import DomainValidationError


# ===========================================================================
# Workflow Engine Tests
# ===========================================================================

class DummyObserver(IWorkflowObserver):
    """Observer giả lập để kiểm tra telemetry events."""
    def __init__(self):
        self.events = []
        self.should_fail = False

    def on_event(self, event: WorkflowEvent) -> None:
        if self.should_fail:
            raise RuntimeError("Observer crashed")
        self.events.append(event)


def test_workflow_engine_basic_success(tmp_path: Path):
    """Test chạy engine thành công với các pipeline steps."""
    observer = DummyObserver()
    engine = WorkflowEngine(observers=[observer])
    
    context = WorkflowContext(workflow_id="test_flow", workspace_path=tmp_path)
    
    def step1(ctx: WorkflowContext):
        ctx.state["s1"] = "done"

    def step2(ctx: WorkflowContext):
        ctx.state["s2"] = 42

    steps = [
        CallableWorkflowStep(name="step_one", handler=step1, description="First step"),
        CallableWorkflowStep(name="step_two", handler=step2)
    ]

    out_ctx = engine.run(context, steps)
    
    assert out_ctx.state["s1"] == "done"
    assert out_ctx.state["s2"] == 42
    
    # Kiểm tra events emit
    assert len(observer.events) == 6  # workflow_start, step1_start, step1_complete, step2_start, step2_complete, workflow_complete
    assert observer.events[0].status == "started"
    assert observer.events[-1].status == "completed"


def test_workflow_engine_step_failure(tmp_path: Path):
    """Test engine khi một step bị crash."""
    observer = DummyObserver()
    engine = WorkflowEngine(observers=[observer])
    context = WorkflowContext(workflow_id="test_fail", workspace_path=tmp_path)

    def bad_step(ctx: WorkflowContext):
        raise ValueError("Step failed")

    steps = [
        CallableWorkflowStep(name="bad_step", handler=bad_step)
    ]

    with pytest.raises(ValueError, match="Step failed"):
        engine.run(context, steps)

    assert observer.events[-1].status == "failed"
    assert observer.events[-1].stage == "bad_step"


def test_workflow_engine_observer_subscription(tmp_path: Path):
    """Test đăng ký/hủy đăng ký observer."""
    observer1 = DummyObserver()
    observer2 = DummyObserver()
    
    engine = WorkflowEngine()
    engine.subscribe(observer1)
    engine.subscribe(observer2)
    
    context = WorkflowContext(workflow_id="test_sub", workspace_path=tmp_path)
    engine.run(context, [])
    
    assert len(observer1.events) == 2
    assert len(observer2.events) == 2

    # Unsubscribe observer2
    engine.unsubscribe(observer2)
    observer1.events.clear()
    observer2.events.clear()
    
    engine.run(context, [])
    assert len(observer1.events) == 2
    assert len(observer2.events) == 0  # observer2 đã bị gỡ bỏ


def test_workflow_engine_observer_crashes(tmp_path: Path):
    """Test lỗi của observer không gây crash cho engine chính."""
    observer = DummyObserver()
    observer.should_fail = True
    engine = WorkflowEngine(observers=[observer])
    
    context = WorkflowContext(workflow_id="test_crash_obs", workspace_path=tmp_path)
    # Chạy không lỗi
    engine.run(context, [])


# ===========================================================================
# Helpers Tests o Boundary
# ===========================================================================

def test_ensure_workspace_dir_invalid():
    """Test lỗi khi workspace không phải thư mục."""
    with pytest.raises(UseCaseValidationError, match="not a valid directory"):
        _ensure_workspace_dir(Path("/nonexistent/path"))


def test_ensure_output_inside_workspace(tmp_path: Path):
    """Test lỗi path traversal đối với output file."""
    # Hợp lệ
    _ensure_output_inside_workspace(tmp_path, "report.xml")
    _ensure_output_inside_workspace(tmp_path, "sub/dir/report.xml")
    
    # Không hợp lệ (path traversal)
    with pytest.raises(UseCaseValidationError, match="path traversal detected"):
        _ensure_output_inside_workspace(tmp_path, "../outside.xml")


# ===========================================================================
# Use Case Orchestrations Tests
# ===========================================================================

@pytest.fixture
def fake_ws(tmp_path: Path) -> Path:
    ws = tmp_path / "valid_ws"
    ws.mkdir()
    return ws


def test_build_context_use_case(fake_ws: Path):
    """Test BuildContextUseCase chạy thành công và quản lý ngoại lệ."""
    use_case = BuildContextUseCase()
    
    cmd = BuildContextCommand(
        workspace_path=fake_ws,
        task_description="Build test context description",
        file_paths=[]
    )
    
    # Mock run_context_builder để tránh chạy thực tế
    with patch("domain.workflow.context_builder.run_context_builder") as mock_run:
        mock_run.return_value = MagicMock(prompt="Mock XML Context")
        
        result = use_case.execute(cmd)
        assert result.prompt == "Mock XML Context"
        mock_run.assert_called_once()

    # Test map exception
    with patch("domain.workflow.context_builder.run_context_builder", side_effect=RuntimeError("System crash")):
        with pytest.raises(WorkflowExecutionError, match="Failed to execute rp_build"):
            use_case.execute(cmd)


def test_code_review_use_case(fake_ws: Path):
    """Test CodeReviewUseCase."""
    use_case = CodeReviewUseCase()
    cmd = CodeReviewCommand(
        workspace_path=fake_ws,
        review_focus="security"
    )

    with patch("domain.workflow.code_reviewer.run_code_review") as mock_run:
        mock_run.return_value = MagicMock(prompt="Mock Review Content")
        result = use_case.execute(cmd)
        assert result.prompt == "Mock Review Content"
        
    with patch("domain.workflow.code_reviewer.run_code_review", side_effect=RuntimeError("crashed")):
        with pytest.raises(WorkflowExecutionError):
            use_case.execute(cmd)


def test_refactor_use_case(fake_ws: Path):
    """Test RefactorUseCase cho cả hai phase discover và plan."""
    use_case = RefactorUseCase()
    
    # Test validation phase
    cmd_invalid_phase = RefactorCommand(workspace_path=fake_ws, refactor_scope="Refactor Model", phase="invalid")
    with pytest.raises(UseCaseValidationError, match="phase must be 'discover' or 'plan'"):
        use_case.execute(cmd_invalid_phase)

    cmd_missing_report = RefactorCommand(workspace_path=fake_ws, refactor_scope="Refactor Model", phase="plan", discovery_report="")
    with pytest.raises(UseCaseValidationError, match="discovery_report required"):
        use_case.execute(cmd_missing_report)

    # Test discover execution
    cmd_discover = RefactorCommand(workspace_path=fake_ws, refactor_scope="Refactor Model", phase="discover")
    with patch("domain.workflow.refactor_workflow.run_refactor_discovery") as mock_disc:
        mock_disc.return_value = MagicMock(prompt="Discovery prompt")
        result = use_case.execute(cmd_discover)
        assert result.prompt == "Discovery prompt"

    # Test plan execution
    cmd_plan = RefactorCommand(workspace_path=fake_ws, refactor_scope="Refactor Model", phase="plan", discovery_report="Done discovery")
    with patch("domain.workflow.refactor_workflow.run_refactor_planning") as mock_plan:
        mock_plan.return_value = MagicMock(prompt="Planning prompt")
        result = use_case.execute(cmd_plan)
        assert result.prompt == "Planning prompt"


def test_investigate_use_case(fake_ws: Path):
    """Test InvestigateUseCase."""
    use_case = InvestigateUseCase()
    cmd = InvestigateCommand(
        workspace_path=fake_ws,
        bug_description="IndexError in loop"
    )

    with patch("domain.workflow.bug_investigator.run_bug_investigation") as mock_run:
        mock_run.return_value = MagicMock(prompt="Bug investigation prompt")
        result = use_case.execute(cmd)
        assert result.prompt == "Bug investigation prompt"


def test_test_build_use_case(fake_ws: Path):
    """Test TestBuildUseCase."""
    use_case = TestBuildUseCase()
    cmd = TestBuildCommand(
        workspace_path=fake_ws,
        task_description="Build tests"
    )

    with patch("domain.workflow.test_builder.run_test_builder") as mock_run:
        mock_run.return_value = MagicMock(prompt="Test builder prompt")
        result = use_case.execute(cmd)
        assert result.prompt == "Test builder prompt"


def test_design_planner_use_case(fake_ws: Path):
    """Test DesignPlannerUseCase."""
    use_case = DesignPlannerUseCase()
    cmd = DesignPlannerCommand(
        workspace_path=fake_ws,
        task_description="Design database model"
    )

    with patch("domain.workflow.design_planner.run_design_planner") as mock_run:
        mock_run.return_value = MagicMock(prompt="Design planner prompt")
        result = use_case.execute(cmd)
        assert result.prompt == "Design planner prompt"
