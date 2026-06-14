# Copy Mode Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidated 5 copy modes into 3 core modes (FULL, SMART, APPLY) and 2 sub-options (include_git_diff, tree_map_only) with complete backward compatibility.

**Architecture:** Define `CopyMode` (Enum) and `CopyConfig` (dataclass) in `domain/prompt/copy_mode.py`. Integrate it into `PromptBuildService` and `CopyActionController`, converting legacy settings automatically.

**Tech Stack:** Python, Pytest, PySide6

---

### Task 1: Create TDD Tests for CopyConfig

**Files:**
- Create: `tests/domain/prompt/test_copy_mode.py`

- [ ] **Step 1: Write empty/stub tests**
  Write tests with bodies containing `pass` or basic checks for all required cases.
  ```python
  import pytest
  import warnings
  from domain.prompt.copy_mode import CopyMode, CopyConfig
  from presentation.config.output_format import OutputStyle

  def test_copy_config_serializes_to_dict():
      config = CopyConfig(mode=CopyMode.FULL, include_git_diff=True, tree_map_only=False)
      assert config.to_dict() == {
          "mode": "full",
          "include_git_diff": True,
          "tree_map_only": False,
          "output_style": "xml"
      }

  def test_legacy_compress_string_loads_as_smart():
      with pytest.deprecated_call():
          config = CopyConfig.from_dict({"mode": "compress"})
      assert config.mode == CopyMode.SMART

  def test_legacy_strings_all_map_correctly():
      c1 = CopyConfig.from_dict({"mode": "copy_context"})
      assert c1.mode == CopyMode.FULL
      c2 = CopyConfig.from_dict({"mode": "search_replace"})
      assert c2.mode == CopyMode.APPLY

  def test_tree_map_only_overrides_mode():
      # When tree_map_only is True, map it correctly
      config = CopyConfig.from_dict({"mode": "full", "tree_map_only": True})
      assert config.tree_map_only is True

  def test_all_modes_have_display_name():
      for m in CopyMode:
          assert len(m.display_name) > 0
          assert len(m.description) > 0

  def test_invalid_mode_string_raises_value_error():
      with pytest.raises(ValueError):
          CopyConfig.from_dict({"mode": "invalid_mode"})
  ```

- [ ] **Step 2: Run pytest to verify it fails**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/domain/prompt/test_copy_mode.py -v`
  Expected: FAIL with ModuleNotFoundError (domain.prompt.copy_mode does not exist).

- [ ] **Step 3: Commit TDD stubs**
  Run:
  ```bash
  git add tests/domain/prompt/test_copy_mode.py
  git commit -m "test: add stub tests for CopyConfig TDD"
  ```

---

### Task 2: Implement CopyMode and CopyConfig Data Model

**Files:**
- Create: `domain/prompt/copy_mode.py`

- [ ] **Step 1: Write model implementation**
  Create `domain/prompt/copy_mode.py` containing:
  ```python
  from dataclasses import dataclass
  from enum import Enum
  import warnings
  from typing import Dict, Any
  from presentation.config.output_format import OutputStyle

  class CopyMode(Enum):
      FULL = "full"
      SMART = "smart"
      APPLY = "apply"

      @property
      def display_name(self) -> str:
          if self == CopyMode.FULL:
              return "Full Context"
          elif self == CopyMode.SMART:
              return "Smart Context"
          elif self == CopyMode.APPLY:
              return "Apply (Search/Replace)"
          raise ValueError(f"Unknown mode: {self}")

      @property
      def description(self) -> str:
          if self == CopyMode.FULL:
              return "Sao chép toàn bộ nội dung file đã chọn"
          elif self == CopyMode.SMART:
              return "Chỉ sao chép cấu trúc code (AST signatures & docstrings)"
          elif self == CopyMode.APPLY:
              return "Sao chép kèm theo chỉ dẫn Search/Replace (Aider-style)"
          raise ValueError(f"Unknown mode: {self}")

  @dataclass
  class CopyConfig:
      mode: CopyMode
      include_git_diff: bool = False
      tree_map_only: bool = False
      output_style: OutputStyle = OutputStyle.XML

      def to_dict(self) -> Dict[str, Any]:
          return {
              "mode": self.mode.value,
              "include_git_diff": self.include_git_diff,
              "tree_map_only": self.tree_map_only,
              "output_style": self.output_style.value
          }

      @classmethod
      def from_dict(cls, data: Dict[str, Any]) -> "CopyConfig":
          raw_mode = data.get("mode", "full")
          style_val = data.get("output_style", "xml")
          try:
              output_style = OutputStyle(style_val)
          except ValueError:
              output_style = OutputStyle.XML

          if raw_mode == "compress":
              warnings.warn(
                  "Legacy mode 'compress' is deprecated. Use 'smart' instead.",
                  DeprecationWarning,
                  stacklevel=2
              )
              mode = CopyMode.SMART
          elif raw_mode == "copy_context":
              mode = CopyMode.FULL
          elif raw_mode == "search_replace":
              mode = CopyMode.APPLY
          else:
              try:
                  mode = CopyMode(raw_mode)
              except ValueError:
                  raise ValueError(f"Invalid mode string: {raw_mode}")

          return cls(
              mode=mode,
              include_git_diff=data.get("include_git_diff", False),
              tree_map_only=data.get("tree_map_only", False),
              output_style=output_style
          )
  ```

- [ ] **Step 2: Run pytest to verify all tests pass**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/domain/prompt/test_copy_mode.py -v`
  Expected: PASS

- [ ] **Step 3: Commit implementation**
  Run:
  ```bash
  git add domain/prompt/copy_mode.py
  git commit -m "feat: implement CopyMode and CopyConfig with backward compatibility"
  ```

---

### Task 3: Update PromptBuildService to use CopyConfig

**Files:**
- Modify: `application/services/prompt_build_service.py`

- [ ] **Step 1: Modify PromptBuildService parameter resolution**
  Update `build_prompt` and `build_prompt_full` in `application/services/prompt_build_service.py` to handle `CopyConfig`.
  Ensure that if a string is passed as `output_format` (backward compatibility for existing tests), it wraps it using `CopyConfig.from_dict({"mode": output_format})`.
  
  Specifically, parse `output_format`:
  ```python
  from domain.prompt.copy_mode import CopyConfig, CopyMode
  # inside build_prompt_full:
  if isinstance(output_format, str):
      # Legacy mapping
      if output_format in ("compress", "compress_plain"):
          mode = CopyMode.SMART
      elif output_format == "search_replace":
          mode = CopyMode.APPLY
      else:
          mode = CopyMode.FULL
      
      style_val = "plain" if "plain" in output_format else "xml"
      from presentation.config.output_format import OutputStyle
      config = CopyConfig(
          mode=mode,
          include_git_diff=include_git_changes,
          tree_map_only=False,
          output_style=OutputStyle(style_val)
      )
  elif isinstance(output_format, dict):
      config = CopyConfig.from_dict(output_format)
  else:
      config = output_format
  ```

  Use `config` fields to decide generation flow:
  - If `config.tree_map_only` is True: generate file map only, instructions, diff if enabled.
  - If `config.mode == CopyMode.SMART`: generate smart context contents.
  - Format generators selection is decided by `config.output_style`.

- [ ] **Step 2: Run pytest to ensure no regressions in prompt building**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/test_prompt_generator.py -v`
  Expected: PASS

- [ ] **Step 3: Commit service updates**
  Run:
  ```bash
  git commit -am "refactor: update PromptBuildService to support CopyConfig"
  ```

---

### Task 4: Update CopyActionController and ContextViewQt

**Files:**
- Modify: `presentation/views/context/copy_action_controller.py`

- [ ] **Step 1: Update CopyActionController references**
  Update cache fingerprints, background task setups to construct and pass `CopyConfig` instead of formatting strings.
  
- [ ] **Step 2: Run whole test suite to verify no regressions**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v`
  Expected: PASS

- [ ] **Step 3: Commit final updates**
  Run:
  ```bash
  git commit -am "refactor: update CopyActionController references to use CopyConfig"
  ```
