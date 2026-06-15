"""
Tests for copy_action_controller.py:
- PromptCache: get, put, invalidate, invalidate_all
- copy_as_file_to_clipboard
- CopyTaskWorker: run() success and error
- SecurityCheckWorker: run() success and error
- CopyActionController: _begin_copy_operation, _is_current_generation, _cleanup_stale_refs
- CopyActionController: on_copy_context_requested, _copy_tree_map_only, _copy_smart_context
"""

import pytest
from pathlib import Path
from typing import Optional, Set, Any
from unittest.mock import MagicMock, patch, call

from domain.ports.registry import DomainRegistry
from domain.config.app_settings import AppSettings
from domain.config.output_format import OutputStyle, DEFAULT_OUTPUT_STYLE
from presentation.views.context.copy_action_controller import (
    PromptCache,
    CopyTaskWorker,
    CopyTaskSignals,
    SecurityCheckWorker,
    SecurityCheckSignals,
    CopyActionController,
    copy_as_file_to_clipboard,
    _build_fingerprint,
)


# ===========================================================================
# Fixtures / Helpers
# ===========================================================================


class DummySettingsService:
    def __init__(self) -> None:
        self._settings = AppSettings(
            model_id="gpt-4o",
            include_git_changes=False,
            enable_security_check=False,
            include_full_tree=False,
        )

    def load_settings(self) -> AppSettings:
        return self._settings

    def update_setting(self, key: str, value: str) -> None:
        setattr(self._settings, key, value)

    def add_instruction_history(self, text: str) -> None:
        pass


@pytest.fixture(autouse=True)
def setup_registry():
    orig_service = None
    orig_provider = None
    try:
        orig_service = DomainRegistry.settings_service()
    except RuntimeError:
        pass
    try:
        orig_provider = DomainRegistry._settings_provider
    except AttributeError:
        pass

    service = DummySettingsService()
    DomainRegistry.register_settings_service(service)
    DomainRegistry.register_settings_provider(lambda: service.load_settings())

    yield service

    if orig_service is not None:
        DomainRegistry.register_settings_service(orig_service)
    DomainRegistry._settings_provider = orig_provider


def make_mock_view(
    workspace: Optional[Path] = None,
    selected_paths: Optional[Set[str]] = None,
    instructions: str = "",
    copy_as_file: bool = False,
) -> MagicMock:
    """Create a mock CopyActionViewProtocol."""
    view = MagicMock()
    view.get_workspace.return_value = workspace or Path("/workspace")
    view.get_workspace_path.return_value = workspace or Path("/workspace")
    view.get_selected_paths.return_value = selected_paths or set()
    view.get_instructions_text.return_value = instructions
    view.get_output_style.return_value = DEFAULT_OUTPUT_STYLE
    view.get_copy_as_file.return_value = copy_as_file
    view.get_full_tree.return_value = False
    view.is_smart_mode_active.return_value = False
    view.parent_widget.return_value = None

    copy_config = MagicMock()
    copy_config.tree_map_only = False
    copy_config.include_git_diff = False
    from domain.prompt.copy_mode import CopyMode
    copy_config.mode = CopyMode.FULL
    view.get_copy_config.return_value = copy_config

    clipboard_service = MagicMock()
    clipboard_service.copy_to_clipboard.return_value = (True, "")
    view.get_clipboard_service.return_value = clipboard_service

    prompt_builder = MagicMock()
    view.get_prompt_builder.return_value = prompt_builder

    view.get_tokenization_service.return_value = MagicMock()
    view.get_ignore_engine.return_value = MagicMock()
    return view


# ===========================================================================
# PromptCache Tests
# ===========================================================================


class TestPromptCache:
    def test_get_miss(self):
        cache = PromptCache()
        result = cache.get("copy", "fp123")
        assert result is None

    def test_put_and_get_hit(self):
        cache = PromptCache()
        breakdown = {"content_tokens": 100}
        cache.put("copy", "fp123", "hello prompt", 500, breakdown)
        result = cache.get("copy", "fp123")
        assert result is not None
        prompt, count, bd = result
        assert prompt == "hello prompt"
        assert count == 500
        assert bd == breakdown

    def test_get_wrong_fingerprint(self):
        cache = PromptCache()
        cache.put("copy", "fp123", "prompt", 100, {})
        result = cache.get("copy", "fp_different")
        assert result is None

    def test_get_wrong_mode(self):
        cache = PromptCache()
        cache.put("copy", "fp123", "prompt", 100, {})
        result = cache.get("smart", "fp123")
        assert result is None

    def test_invalidate_mode(self):
        cache = PromptCache()
        cache.put("copy", "fp1", "prompt1", 100, {})
        cache.put("smart", "fp2", "prompt2", 200, {})
        cache.invalidate("copy")
        assert cache.get("copy", "fp1") is None
        assert cache.get("smart", "fp2") is not None

    def test_invalidate_all_modes(self):
        cache = PromptCache()
        cache.put("copy", "fp1", "prompt1", 100, {})
        cache.put("smart", "fp2", "prompt2", 200, {})
        cache.invalidate()  # No mode = invalidate all
        assert cache.get("copy", "fp1") is None
        assert cache.get("smart", "fp2") is None

    def test_invalidate_all_explicit(self):
        cache = PromptCache()
        cache.put("copy", "fp1", "prompt1", 100, {})
        cache.invalidate_all()
        assert cache.get("copy", "fp1") is None

    def test_invalidate_nonexistent_mode(self):
        cache = PromptCache()
        # Should not raise even if mode doesn't exist
        cache.invalidate("nonexistent")

    def test_overwrite_same_mode(self):
        cache = PromptCache()
        cache.put("copy", "fp1", "old prompt", 100, {})
        cache.put("copy", "fp2", "new prompt", 200, {})
        # Only newest fingerprint should be stored
        assert cache.get("copy", "fp1") is None
        result = cache.get("copy", "fp2")
        assert result is not None
        assert result[0] == "new prompt"


# ===========================================================================
# copy_as_file_to_clipboard Tests
# ===========================================================================


def test_copy_as_file_to_clipboard_success(qtbot):
    success, path_or_err = copy_as_file_to_clipboard("hello world", "test.txt")
    assert success is True
    assert "test.txt" in path_or_err


def test_copy_as_file_to_clipboard_default_filename(qtbot):
    success, path_or_err = copy_as_file_to_clipboard("content")
    assert success is True
    assert "paste.txt" in path_or_err


def test_copy_as_file_to_clipboard_error(qtbot):
    with patch("tempfile.gettempdir", side_effect=OSError("disk full")):
        success, err = copy_as_file_to_clipboard("content")
        assert success is False
        assert "disk full" in err


# ===========================================================================
# _build_fingerprint Tests
# ===========================================================================


def test_build_fingerprint_deterministic():
    paths = {"/a/b.py", "/c/d.py"}
    fp1 = _build_fingerprint(paths, "instr", "xml", "copy", True, False)
    fp2 = _build_fingerprint(paths, "instr", "xml", "copy", True, False)
    assert fp1 == fp2


def test_build_fingerprint_differs_by_mode():
    paths = {"/a/b.py"}
    fp_copy = _build_fingerprint(paths, "instr", "xml", "copy", True, False)
    fp_smart = _build_fingerprint(paths, "instr", "xml", "smart", True, False)
    assert fp_copy != fp_smart


def test_build_fingerprint_differs_by_instructions():
    paths = {"/a/b.py"}
    fp1 = _build_fingerprint(paths, "instruction A", "xml", "copy", True, False)
    fp2 = _build_fingerprint(paths, "instruction B", "xml", "copy", True, False)
    assert fp1 != fp2


def test_build_fingerprint_differs_by_paths():
    fp1 = _build_fingerprint({"/a/b.py"}, "instr", "xml", "copy", True, False)
    fp2 = _build_fingerprint({"/c/d.py"}, "instr", "xml", "copy", True, False)
    assert fp1 != fp2


# ===========================================================================
# CopyTaskWorker Tests
# ===========================================================================


def test_copy_task_worker_success():
    signals = CopyTaskSignals()
    task_fn = MagicMock(return_value=("prompt text", 100, {"key": "val"}))

    finished_calls = []
    signals.finished.connect(lambda p, t, b: finished_calls.append((p, t, b)))

    worker = CopyTaskWorker(task_fn, signals, generation=1)
    worker.run()

    assert len(finished_calls) == 1
    assert finished_calls[0][0] == "prompt text"
    assert finished_calls[0][1] == 100


def test_copy_task_worker_error():
    signals = CopyTaskSignals()
    task_fn = MagicMock(side_effect=Exception("Task failed!"))

    error_calls = []
    signals.error.connect(lambda msg: error_calls.append(msg))

    worker = CopyTaskWorker(task_fn, signals, generation=1)
    worker.run()

    assert len(error_calls) == 1
    assert "Task failed!" in error_calls[0]


def test_copy_task_worker_no_auto_delete():
    signals = CopyTaskSignals()
    task_fn = MagicMock(return_value=("p", 0, {}))
    worker = CopyTaskWorker(task_fn, signals, generation=1)
    assert worker.autoDelete() is False


# ===========================================================================
# SecurityCheckWorker Tests
# ===========================================================================


def test_security_check_worker_success():
    signals = SecurityCheckSignals()
    scanner = MagicMock()
    scanner.scan_secrets_in_files_cached.return_value = []

    finished_calls = []
    signals.finished.connect(lambda matches: finished_calls.append(matches))

    with patch.object(DomainRegistry, "security_scanner", return_value=scanner):
        worker = SecurityCheckWorker(paths={"/a/b.py"}, signals=signals, generation=1)
        worker.run()

    assert len(finished_calls) == 1
    assert finished_calls[0] == []


def test_security_check_worker_error():
    signals = SecurityCheckSignals()

    error_calls = []
    signals.error.connect(lambda msg: error_calls.append(msg))

    with patch.object(DomainRegistry, "security_scanner", side_effect=Exception("scan error")):
        worker = SecurityCheckWorker(paths={"/a/b.py"}, signals=signals, generation=1)
        worker.run()

    assert len(error_calls) == 1
    assert "scan error" in error_calls[0]


# ===========================================================================
# CopyActionController Tests
# ===========================================================================


def test_controller_begin_copy_operation(qtbot):
    view = make_mock_view()
    ctrl = CopyActionController(view)

    gen = ctrl._begin_copy_operation()
    assert gen == 1
    assert ctrl._copy_generation == 1
    view.set_copy_buttons_enabled.assert_called_with(False)


def test_controller_begin_copy_operation_increments(qtbot):
    view = make_mock_view()
    ctrl = CopyActionController(view)

    ctrl._begin_copy_operation()
    ctrl._begin_copy_operation()
    gen3 = ctrl._begin_copy_operation()
    assert gen3 == 3


def test_controller_is_current_generation(qtbot):
    view = make_mock_view()
    ctrl = CopyActionController(view)
    ctrl._begin_copy_operation()

    assert ctrl._is_current_generation(1) is True
    assert ctrl._is_current_generation(0) is False
    assert ctrl._is_current_generation(2) is False


def test_controller_cleanup_stale_refs(qtbot):
    view = make_mock_view()
    ctrl = CopyActionController(view)

    stale_obj = MagicMock()
    ctrl._stale_workers = [stale_obj]
    ctrl._cleanup_stale_refs(gen=0)

    # stale_obj is not a QObject so deleteLater won't be called
    # but _stale_workers should be cleared
    assert ctrl._stale_workers == []


def test_controller_no_workspace_shows_error(qtbot):
    view = make_mock_view(workspace=None)
    view.get_workspace.return_value = None
    view.get_workspace_path.return_value = None
    ctrl = CopyActionController(view)

    ctrl._copy_context()
    view.show_status.assert_called()
    call_args = view.show_status.call_args
    assert call_args[1].get("is_error", True) or "workspace" in call_args[0][0].lower()


def test_controller_no_files_shows_error(qtbot, tmp_path):
    view = make_mock_view(workspace=tmp_path, selected_paths=set())
    ctrl = CopyActionController(view)

    ctrl._copy_context()
    view.show_status.assert_called()


def test_controller_on_copy_context_requested_smart_xml_blocked(qtbot, tmp_path):
    """Smart mode + OPX should show a warning and not proceed."""
    view = make_mock_view(workspace=tmp_path)
    view.is_smart_mode_active.return_value = True
    ctrl = CopyActionController(view)

    with patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warning:
        ctrl.on_copy_context_requested(include_xml=True)
        mock_warning.assert_called_once()


def test_controller_on_copy_context_requested_calls_copy(qtbot, tmp_path):
    """Normal copy context request should call _copy_context."""
    view = make_mock_view(workspace=tmp_path)
    view.is_smart_mode_active.return_value = False
    ctrl = CopyActionController(view)

    with patch.object(ctrl, "_copy_context") as mock_copy:
        ctrl.on_copy_context_requested(include_xml=False)
        mock_copy.assert_called_once()


def test_controller_on_copy_tree_map_requested(qtbot, tmp_path):
    view = make_mock_view(workspace=tmp_path)
    ctrl = CopyActionController(view)

    with patch.object(ctrl, "_copy_tree_map_only") as mock_copy:
        ctrl.on_copy_tree_map_requested()
        mock_copy.assert_called_once()


def test_controller_on_copy_smart_requested(qtbot, tmp_path):
    view = make_mock_view(workspace=tmp_path)
    ctrl = CopyActionController(view)

    with patch.object(ctrl, "_copy_smart_context") as mock_copy:
        ctrl.on_copy_smart_requested()
        mock_copy.assert_called_once()


def test_controller_stale_workers_moved_on_begin(qtbot):
    """begin_copy_operation should move current worker to stale list."""
    view = make_mock_view()
    ctrl = CopyActionController(view)

    mock_worker = MagicMock()
    mock_signals = MagicMock()
    ctrl._current_copy_worker = mock_worker
    ctrl._current_copy_signals = mock_signals

    ctrl._begin_copy_operation()

    assert ctrl._current_copy_worker is None
    assert ctrl._current_copy_signals is None
    assert mock_worker in ctrl._stale_workers
    assert mock_signals in ctrl._stale_workers


def test_controller_on_copy_requested_tree_map(qtbot, tmp_path):
    view = make_mock_view(workspace=tmp_path)
    copy_config = MagicMock()
    copy_config.tree_map_only = True
    view.get_copy_config.return_value = copy_config
    ctrl = CopyActionController(view)

    with patch.object(ctrl, "_copy_tree_map_only") as mock_copy:
        ctrl.on_copy_requested()
        mock_copy.assert_called_once()


def test_controller_on_copy_requested_full(qtbot, tmp_path):
    from domain.prompt.copy_mode import CopyMode
    view = make_mock_view(workspace=tmp_path)
    copy_config = MagicMock()
    copy_config.tree_map_only = False
    copy_config.mode = CopyMode.FULL
    view.get_copy_config.return_value = copy_config
    ctrl = CopyActionController(view)

    with patch.object(ctrl, "_copy_context") as mock_copy:
        ctrl.on_copy_requested()
        mock_copy.assert_called_once_with(include_xml=False, copy_destination="text")


def test_controller_on_copy_requested_smart(qtbot, tmp_path):
    from domain.prompt.copy_mode import CopyMode
    view = make_mock_view(workspace=tmp_path)
    copy_config = MagicMock()
    copy_config.tree_map_only = False
    copy_config.mode = CopyMode.SMART
    view.get_copy_config.return_value = copy_config
    ctrl = CopyActionController(view)

    with patch.object(ctrl, "_copy_smart_context") as mock_copy:
        ctrl.on_copy_requested()
        mock_copy.assert_called_once()


def test_controller_on_copy_requested_apply(qtbot, tmp_path):
    from domain.prompt.copy_mode import CopyMode
    view = make_mock_view(workspace=tmp_path)
    copy_config = MagicMock()
    copy_config.tree_map_only = False
    copy_config.mode = CopyMode.APPLY
    view.get_copy_config.return_value = copy_config
    ctrl = CopyActionController(view)

    with patch.object(ctrl, "_copy_context") as mock_copy:
        ctrl.on_copy_requested()
        mock_copy.assert_called_once_with(include_xml=True, copy_destination="text")
