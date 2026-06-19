# Close Workspace Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a Close Workspace feature that resets the application state to "no project open" without restarting, clearing all views and stopping file watcher and token processes.

**Architecture:** Extend `SynapseMainWindow` to support `self.workspace_path = None`, and propagate this state change into `ContextViewQt`, `PresetController`, `FileTreeWidget`, `FileTreeModel`, and `ApplyViewQt`. Add a Close Workspace `[x]` QToolButton dynamically visible in the Top Bar.

**Tech Stack:** Python, PySide6

## Global Constraints
- Python 3.10+
- PySide6 UI elements must only be updated from the main thread.
- Avoid automatic commits (user global rule).

---

### Task 1: Update FileTree Model & Widget

**Files:**
- Modify: `presentation/components/file_tree/file_tree_model.py`
- Modify: `presentation/components/file_tree/file_tree_widget.py`
- Test: Run existing tests to verify no regression.

**Interfaces:**
- Consumes: None
- Produces: `FileTreeModel.load_tree(workspace_path: Optional[Path])` and `FileTreeWidget.load_tree(workspace_path: Optional[Path])`.

- [ ] **Step 1: Modify FileTreeModel.load_tree to support Optional[Path]**
  Update the method signature and wrap directory scanning:
  ```python
      def load_tree(self, workspace_path: Optional[Path]) -> None:
          """
          Load file tree cho workspace mới.
          """
          self._workspace_path = workspace_path

          with self._generation_lock:
              self._generation += 1

          self.beginResetModel()

          self._selection_mgr.reset()
          self._token_cache.clear()
          self._line_cache.clear()
          self._path_to_node.clear()
          self._folder_state_cache.clear()
          self._search_index.clear()
          self._search_index_ready = False

          if workspace_path is not None:
              try:
                  from application.services.workspace_config import get_excluded_patterns
                  excluded = get_excluded_patterns()

                  from domain.ports.registry import DomainRegistry

                  tree_item = DomainRegistry.directory_scanner().scan_directory_shallow(
                      workspace_path,
                      ignore_engine=self._ignore_engine,
                      depth=1,
                      excluded_patterns=excluded if excluded else None,
                  )
                  if tree_item:
                      self._root_tree_item = tree_item
                      self._root_node = TreeNode.from_tree_item(
                          tree_item,
                          parent=self._invisible_root,
                          row=0,
                          depth=0,
                          max_depth=1,
                          path_index=self._path_to_node,
                      )
                      self._invisible_root.children = [self._root_node]
                  else:
                      self._root_node = None
                      self._invisible_root.children = []
              except Exception as e:
                  logger.error(f"Error loading tree: {e}")
                  self._root_node = None
                  self._invisible_root.children = []
          else:
              self._root_tree_item = None
              self._root_node = None
              self._invisible_root.children = []

          self.endResetModel()

          if workspace_path is not None and workspace_path.exists():
              self._build_search_index_async(workspace_path)
  ```

- [ ] **Step 2: Modify FileTreeWidget.load_tree to support Optional[Path]**
  Modify signature and stop/start the selection polling timer:
  ```python
      def load_tree(self, workspace_path: Optional[Path]) -> None:
          """Load file tree cho workspace."""
          if self._current_token_worker:
              self._current_token_worker.cancel()
              self._current_token_worker = None

          self._token_debounce.stop()
          self._search_debounce.stop()

          self._search_field.clear()
          self._match_count_label.setText("")
          self._delegate.set_search_query("")
          self._filter_proxy.set_search_state("", None)
          self._last_search_results = []
          self._select_results_btn.hide()

          if workspace_path is not None:
              self._selection_poll_timer.start()
          else:
              self._selection_poll_timer.stop()

          self._model.load_tree(workspace_path)

          if workspace_path is not None:
              root_idx = self._filter_proxy.index(0, 0)
              if root_idx.isValid():
                  self._tree_view.expand(root_idx)
  ```

- [ ] **Step 3: Run existing unit tests to check for no regressions**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/presentation/test_context_controllers.py -v`
  Expected: PASS

---

### Task 2: Update PresetController & ContextViewQt

**Files:**
- Modify: `presentation/views/context/preset_controller.py`
- Modify: `presentation/views/context/context_view_qt.py`

**Interfaces:**
- Consumes: `FileTreeWidget.load_tree(workspace_path: Optional[Path])`
- Produces: `ContextViewQt.on_workspace_changed(workspace_path: Optional[Path])` and `PresetController.on_workspace_changed(workspace_path: Optional[Path])`.

- [ ] **Step 1: Modify PresetController.on_workspace_changed**
  Support `Optional[Path]` and set store to `None` if workspace path is `None`:
  ```python
      def on_workspace_changed(self, workspace_path: Optional[Path]) -> None:
          """Khởi tạo/reset PresetStore khi workspace thay đổi."""
          if workspace_path is None:
              self._store = None
          else:
              self._store = DomainRegistry.preset_store_factory().create_preset_store(
                  workspace_path
              )
          self._active_preset_id = None
          self.presets_changed.emit()
  ```

- [ ] **Step 2: Modify ContextViewQt.on_workspace_changed**
  Support `Optional[Path]` and guard `workspace_path` checks:
  ```python
      def on_workspace_changed(self, workspace_path: Optional[Path]) -> None:
          """Handle workspace change."""
          if (
              not self._copy_controller
              or not self._related_controller
              or not self._tree_controller
          ):
              return

          from shared.logging_config import log_info

          log_info(f"[ContextView] Workspace changing to: {workspace_path}")

          self._copy_controller._begin_copy_operation()
          self.set_copy_buttons_enabled(True)

          self._ai_suggest_generation += 1
          self._cancel_ai_suggest_worker()
          if hasattr(self, "_ai_suggest_btn"):
              self._ai_suggest_btn.setEnabled(True)
              self._ai_suggest_btn.setText("AI Suggest Select")

          if self._file_watcher:
              self._file_watcher.stop()

          self._related_controller.set_mode(False, 0, silent=True)

          DomainRegistry.cache_registry().invalidate_for_workspace()
          self._copy_controller._prompt_cache.invalidate_all()

          if self._preset_controller:
              self._preset_controller.on_workspace_changed(workspace_path)

          self.file_tree_widget.load_tree(workspace_path)
          self.tree = self.file_tree_widget.get_model()._root_node  # type: ignore

          if hasattr(self, "_token_usage_bar"):
              self._token_usage_bar.update_stats(tokens=0, limit=200000, files=0)

          if hasattr(self, "_context_info_label"):
              self._context_info_label.setText("")
          if hasattr(self, "_limit_warning"):
              self._limit_warning.hide()

          if self._file_watcher and workspace_path is not None and workspace_path.exists():
              self._file_watcher.start(
                  path=workspace_path,
                  callbacks=WatcherCallbacks(
                      on_file_modified=self._tree_controller.on_file_modified,
                      on_file_created=self._tree_controller.on_file_created,
                      on_file_deleted=self._tree_controller.on_file_deleted,
                      on_batch_change=self._tree_controller.on_file_system_changed,
                  ),
                  debounce_seconds=0.5,
              )

          if hasattr(self, "_template_btn"):
              self._template_btn.setText("Templates")
  ```

---

### Task 3: Update ApplyViewQt

**Files:**
- Modify: `presentation/views/apply/apply_view_qt.py`

**Interfaces:**
- Consumes: None
- Produces: `ApplyViewQt.on_workspace_changed(workspace_path: Optional[Path])`

- [ ] **Step 1: Add on_workspace_changed to ApplyViewQt**
  Add method:
  ```python
      def on_workspace_changed(self, workspace_path: Optional[Path]) -> None:
          """Update workspace label and clear inputs when workspace changes."""
          if workspace_path:
              self._workspace_label.setText(workspace_path.name)
              self._workspace_label.setToolTip(str(workspace_path))
          else:
              self._workspace_label.setText("No workspace")
              self._workspace_label.setToolTip("")
          self._clear_input()
  ```

---

### Task 4: Add Close Workspace Button and Slot in SynapseMainWindow

**Files:**
- Modify: `presentation/main_window.py`

**Interfaces:**
- Consumes: `ContextViewQt.on_workspace_changed(workspace_path: Optional[Path])`, `ApplyViewQt.on_workspace_changed(workspace_path: Optional[Path])`
- Produces: `SynapseMainWindow._close_workspace(self)` slot and close workspace button `self._close_workspace_btn`.

- [ ] **Step 1: Instantiate Close Button in _build_top_bar**
  Insert the close button after the workspace path label:
  ```python
          # In presentation/main_window.py (around line 276)
          self._folder_path_label.setToolTip("Current workspace folder")
          layout.addWidget(self._folder_path_label, stretch=1)

          # ── Close workspace button ──
          self._close_workspace_btn = QToolButton()
          self._close_workspace_btn.setIcon(
              create_colored_icon(
                  str(self.assets_dir / "x.svg"), ThemeColors.TEXT_SECONDARY
              )
          )
          self._close_workspace_btn.setIconSize(QSize(14, 14))
          self._close_workspace_btn.setToolTip("Close Workspace")
          self._close_workspace_btn.setStyleSheet(
              f"QToolButton {{ padding: 4px 6px; border-radius: 4px; }}"
              f"QToolButton:hover {{ background-color: {ThemeColors.BG_ELEVATED}; }}"
          )
          self._close_workspace_btn.setCursor(Qt.CursorShape.PointingHandCursor)
          self._close_workspace_btn.clicked.connect(self._close_workspace)
          self._close_workspace_btn.setVisible(False)
          layout.addWidget(self._close_workspace_btn)
  ```

- [ ] **Step 2: Add _close_workspace Slot**
  Add slot method in `SynapseMainWindow`:
  ```python
      @Slot()
      def _close_workspace(self) -> None:
          """Close current workspace and reset app to no project open state."""
          self.workspace_path = None
          self._cached_git_branch = None
          self._git_branch_pending = False

          # Hide close button
          self._close_workspace_btn.setVisible(False)

          # Reset folder path label
          self._folder_path_label.setText("No folder selected")
          self._folder_path_label.setStyleSheet(
              f"color: {ThemeColors.TEXT_SECONDARY}; "
              f"font-family: {ThemeFonts.FAMILY_MONO}; "
              f"font-size: {ThemeFonts.SIZE_CAPTION}px;"
          )

          # Update window title
          self._update_window_title()

          # Update status bar
          self._update_status_bar()

          # Notify context view
          self.context_view.on_workspace_changed(None)

          # Notify apply view
          if hasattr(self, "apply_view") and hasattr(self.apply_view, "on_workspace_changed"):
              self.apply_view.on_workspace_changed(None)
  ```

- [ ] **Step 3: Update _set_workspace and _restore_session to show Close Button**
  In `_set_workspace`:
  ```python
      def _set_workspace(self, path: Path) -> None:
          """Set workspace path and notify all views."""
          self.workspace_path = path
          self._cached_git_branch = None  # Clear stale branch
          self._git_branch_pending = False  # Allow immediate re-detection

          self._close_workspace_btn.setVisible(True)
          # ...
  ```
  In `_restore_session`:
  ```python
          recent_folders = DomainRegistry.recent_folders().load_recent_folders()
          if recent_folders:
              workspace = Path(recent_folders[0])
              if workspace.exists() and workspace.is_dir():
                  self.workspace_path = workspace
                  self._close_workspace_btn.setVisible(True)
                  # ...
  ```

---

### Task 5: E2E and Unit Verification

**Files:**
- Modify: `tests/test_e2e_critical_flows.py`

**Interfaces:**
- None

- [ ] **Step 1: Add automated tests to test close workspace functionality**
  Add a new test in `tests/test_e2e_critical_flows.py`:
  ```python
  def test_flow_f_close_workspace(app_e2e, qtbot, workspace_dir):
      """
      Test that closing the workspace correctly resets state, title, and labels.
      """
      window = app_e2e
      window._set_workspace(workspace_dir)

      # Wait for workspace load
      qtbot.waitUntil(
          lambda: window.context_view.file_tree_widget.get_model()._root_node is not None,
          timeout=3000,
      )
      assert window.workspace_path == workspace_dir
      assert window._close_workspace_btn.isVisible()

      # Click Close Workspace button
      qtbot.mouseClick(window._close_workspace_btn, Qt.MouseButton.LeftButton)

      # Verify reset
      assert window.workspace_path is None
      assert not window._close_workspace_btn.isVisible()
      assert "No project open" in window.windowTitle()
      assert window._folder_path_label.text() == "No folder selected"
      assert window.context_view.file_tree_widget.get_model()._root_node is None
  ```

- [ ] **Step 2: Run all tests**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v`
  Expected: All tests pass.
