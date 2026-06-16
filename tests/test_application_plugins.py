"""
Tests cho Workflow Plugins system trong application/plugins/
"""

import time
import threading
from pathlib import Path
import pytest
from application.errors import UseCaseValidationError, WorkflowExecutionError
from application.plugins.contracts import (
    WorkflowPluginMetadata,
    WorkflowPluginRequest,
    WorkflowPluginResult,
)
from application.plugins.registry import (
    WorkflowPluginRegistry,
    workflow_plugin_registry,
)


# Mock plugin thuc thi interface IWorkflowPlugin
class DummyPlugin:
    """Mock plugin class de testing."""

    def __init__(self, plugin_id: str = "dummy-plugin") -> None:
        self.metadata = WorkflowPluginMetadata(
            plugin_id=plugin_id,
            display_name="Dummy Plugin",
            version="1.0.0",
            description="Testing mock plugin",
        )
        self.initialized = False
        self.shutdown_called = False
        self.execute_delay = 0.0
        self.should_fail_execute = False
        self.should_validation_fail = False

    def initialize(self) -> None:
        self.initialized = True

    def execute(self, request: WorkflowPluginRequest) -> WorkflowPluginResult:
        if self.should_validation_fail:
            raise UseCaseValidationError("Mock validation error")
        if self.should_fail_execute:
            raise RuntimeError("Mock runtime crash")
        if self.execute_delay > 0.0:
            time.sleep(self.execute_delay)
        return WorkflowPluginResult(
            success=True,
            message="Executed successfully",
            data={"input_action": request.action, "payload_data": request.payload},
        )

    def shutdown(self) -> None:
        self.shutdown_called = True


def test_contracts_dataclass():
    """Test structures trong contracts.py."""
    metadata = WorkflowPluginMetadata("p-1", "Plugin 1", "0.1.0", "Desc")
    assert metadata.plugin_id == "p-1"

    req = WorkflowPluginRequest(workspace_path=Path("/tmp"))
    assert req.action == "run"
    assert req.payload == {}

    res = WorkflowPluginResult(success=True, message="done")
    assert res.success is True
    assert res.data == {}


def test_registry_register_and_get():
    """Test register plugin vao registry va lay ra."""
    registry = WorkflowPluginRegistry()
    plugin = DummyPlugin("test-plugin")

    # Register
    registry.register(plugin)
    assert registry.get("test-plugin") is plugin

    # Register trung -> validation error
    with pytest.raises(UseCaseValidationError, match="already registered"):
        registry.register(plugin)

    # Register trung nhung cho phep override
    new_plugin = DummyPlugin("test-plugin")
    registry.register(new_plugin, allow_override=True)
    assert registry.get("test-plugin") is new_plugin


def test_registry_register_invalid_id():
    """Test register plugin co ID rong."""
    registry = WorkflowPluginRegistry()
    plugin = DummyPlugin("   ")
    with pytest.raises(UseCaseValidationError, match="plugin_id must not be empty"):
        registry.register(plugin)


def test_registry_list_metadata():
    """Test list metadata trong registry."""
    registry = WorkflowPluginRegistry()
    p1 = DummyPlugin("p1")
    p2 = DummyPlugin("p2")

    registry.register(p1)
    registry.register(p2)

    metadata_list = registry.list_metadata()
    assert len(metadata_list) == 2
    ids = {m.plugin_id for m in metadata_list}
    assert ids == {"p1", "p2"}


def test_registry_execute_success():
    """Test execution cua plugin thông qua registry."""
    registry = WorkflowPluginRegistry()
    plugin = DummyPlugin("p1")
    registry.register(plugin)

    req = WorkflowPluginRequest(
        workspace_path=Path("/tmp"), action="analyze", payload={"deep": True}
    )
    res = registry.execute("p1", req)

    assert res.success is True
    assert res.data["input_action"] == "analyze"
    assert res.data["payload_data"] == {"deep": True}


def test_registry_execute_validation_error():
    """Test handle UseCaseValidationError nem ra tu execute."""
    registry = WorkflowPluginRegistry()
    plugin = DummyPlugin("p1")
    plugin.should_validation_fail = True
    registry.register(plugin)

    req = WorkflowPluginRequest(workspace_path=Path("/tmp"))
    with pytest.raises(UseCaseValidationError, match="Mock validation error"):
        registry.execute("p1", req)


def test_registry_execute_workflow_error():
    """Test map error thuong thanh WorkflowExecutionError."""
    registry = WorkflowPluginRegistry()
    plugin = DummyPlugin("p1")
    plugin.should_fail_execute = True
    registry.register(plugin)

    req = WorkflowPluginRequest(workspace_path=Path("/tmp"))
    with pytest.raises(WorkflowExecutionError, match="execution failed"):
        registry.execute("p1", req)


def test_registry_execute_nonexistent():
    """Test execute plugin khong ton tai."""
    registry = WorkflowPluginRegistry()
    req = WorkflowPluginRequest(workspace_path=Path("/tmp"))
    with pytest.raises(UseCaseValidationError, match="Unknown plugin_id"):
        registry.execute("unknown-id", req)


def test_registry_unregister():
    """Test unregister plugin thành công."""
    registry = WorkflowPluginRegistry()
    plugin = DummyPlugin("p1")
    registry.register(plugin)

    assert registry.unregister("p1") is True
    assert registry.get("p1") is None
    assert plugin.shutdown_called is True

    # Unregister tiep khi khong co -> False
    assert registry.unregister("p1") is False


def test_registry_unregister_waiting_execution():
    """Test unregister phai cho cho execution dang chay hoan thanh."""
    registry = WorkflowPluginRegistry()
    plugin = DummyPlugin("p1")
    plugin.execute_delay = 0.2
    registry.register(plugin)

    def run_execution():
        req = WorkflowPluginRequest(workspace_path=Path("/tmp"))
        registry.execute("p1", req)

    # Chay thread execute plugin
    t = threading.Thread(target=run_execution)
    t.start()
    time.sleep(0.05)  # Dam bao execution da bat dau

    # Unregister o main thread - phai cho plugin.execute song
    start_time = time.time()
    assert registry.unregister("p1") is True
    elapsed = time.time() - start_time
    assert elapsed >= 0.1  # Dam bao co blocked wait

    t.join()
    assert plugin.shutdown_called is True


def test_registry_execute_during_shutdown():
    """Test execute khong cho phep khi plugin dang shutdown."""
    registry = WorkflowPluginRegistry()
    plugin = DummyPlugin("p1")
    registry.register(plugin)

    # Set shutting down manually (gia lap)
    registry._shutting_down.add("p1")

    req = WorkflowPluginRequest(workspace_path=Path("/tmp"))
    with pytest.raises(UseCaseValidationError, match="is shutting down"):
        registry.execute("p1", req)


def test_global_registry_instance():
    """Dam bao instance global cua registry duoc khoi tao."""
    assert isinstance(workflow_plugin_registry, WorkflowPluginRegistry)
