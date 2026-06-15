# Design Spec: Onion Architecture Isolation & Presentation Layer Refactoring

**Date**: 2026-06-15  
**Topic**: Strict Onion Architecture Isolation & Refactoring  
**Goal**: Resolve the remaining 36 import violations, 16 Layer Cycles, and fully align the codebase with Onion/Clean Architecture: `domain <- application <- infrastructure <- presentation`.

---

## 1. Problem Description & Context

The codebase of Synapse-Desktop currently contains a few architectural issues that prevent it from being a strictly isolated Onion Architecture:
1. **Domain imports Infrastructure**: Several workflows (`context_builder`, `design_planner`, `test_builder`, `code_reviewer`, `scope_detector`, `hybrid_investigation_graph`, `canonical_structure`, `template_manager`, `file_collector`, `assembler`) directly import filesystem, git, or settings helpers from the `infrastructure` layer.
2. **Presentation imports Domain/Infrastructure**: The `presentation` layer directly imports from `infrastructure` (e.g., settings_manager, git_utils, qt_utils, etc.) and `domain` (e.g. `TreeItem`, `OutputStyle`, `CopyMode`).
3. **Application imports Presentation**: In `application/services/preview_analyzer.py`, a forbidden import of `presentation.config.theme` is present for a function `get_change_color` that is actually unused.
4. **Layer Cycles**: 16 bidirectional dependency loops exist between layers due to the incorrect cross-layer imports.

---

## 2. Proposed Changes

We propose **Strict Layer Isolation** based on standard Clean/Onion Architecture principles.

### Component 1: Architecture Governance Configuration
* **Modify**: [check_architecture.py](file:///home/hao/Desktop/labs/Synapse-Desktop/tools/architecture/check_architecture.py)
* **Action**: Change the forbidden imports configuration to allow the `presentation` layer to depend on the `domain` layer. 
  * In Onion Architecture, the presentation layer (outermost) is allowed to import from the domain layer (innermost) as it is an outer-to-inner dependency flow.
  * We will keep the restriction that forbids `presentation` from importing `infrastructure` directly.
* **Detail**: Update `FORBIDDEN_IMPORTS["presentation"]` from `{"domain", "infrastructure"}` to `{"infrastructure"}`.
  * This resolves all 7 presentation-to-domain violations instantly without requiring code duplication or moving domain concepts to the `shared` layer.

---

### Component 2: Domain Ports & Registry Enhancements
To decouple the `domain` layer from concrete filesystem, git, AST parsing, and settings implementations:

1. **[NEW] Port: IDirectoryScanner**:
   * Create [directory_scanner.py](file:///home/hao/Desktop/labs/Synapse-Desktop/domain/ports/directory_scanner.py)
   * Define the `IDirectoryScanner` port to scan a directory and return a `TreeItem` domain object.
   ```python
   import abc
   from pathlib import Path
   from domain.smart_context.tree_item import TreeItem

   class IDirectoryScanner(abc.ABC):
       @abc.abstractmethod
       def scan_directory(self, root_path: Path) -> TreeItem:
           """Scan a directory recursively and build its TreeItem structure, respecting ignore rules."""
           pass
   ```

2. **Enhance DomainRegistry**:
   * Update [registry.py](file:///home/hao/Desktop/labs/Synapse-Desktop/domain/ports/registry.py)
   * Add support for registering and resolving:
     * `IDirectoryScanner`
     * `IGitService` (port already defined in `domain/workflow/interfaces/git_port.py`)
     * `IAstParser` (port already defined in `domain/workflow/interfaces/ast_parser_port.py`)
     * `AppSettings` provider (callback returning `AppSettings` from the domain config).

3. **Wire concrete implementations in ServiceContainer**:
   * Update [service_container.py](file:///home/hao/Desktop/labs/Synapse-Desktop/presentation/service_container.py)
   * Instantiate and register `ConcreteDirectoryScanner` (implementing `IDirectoryScanner`), `GitService`, `AstParser`, and the settings loader (`load_app_settings`) into `DomainRegistry`.

---

### Component 3: Resolve Domain-to-Infrastructure Violations
* **Workflows** (`context_builder.py`, `design_planner.py`, `test_builder.py`, `code_reviewer.py`, `scope_detector.py`, `hybrid_investigation_graph.py`):
  * Replace direct imports of `scan_directory` and `IgnoreEngine` with calls to `DomainRegistry.directory_scanner().scan_directory(...)`.
  * Replace direct imports of `get_git_diffs` / `get_git_logs` with calls to `DomainRegistry.git_service().get_diffs(...)` / `get_logs(...)`.
* **Canonical Structure** ([canonical_structure.py](file:///home/hao/Desktop/labs/Synapse-Desktop/domain/codemap/canonical_structure.py)):
  * Resolve AST parser dependency by falling back to `DomainRegistry.ast_parser()` when no parser is passed to the function.
* **File Collector** ([file_collector.py](file:///home/hao/Desktop/labs/Synapse-Desktop/domain/prompt/file_collector.py)):
  * Import `is_binary_file` from [shared/utils/file_utils.py](file:///home/hao/Desktop/labs/Synapse-Desktop/shared/utils/file_utils.py) instead of `infrastructure`.
* **Template Manager** ([template_manager.py](file:///home/hao/Desktop/labs/Synapse-Desktop/domain/prompt/template_manager.py)):
  * Import settings from `DomainRegistry.settings()` instead of importing `load_app_settings` from `infrastructure.persistence.settings_manager`.
* **Assembler** ([assembler.py](file:///home/hao/Desktop/labs/Synapse-Desktop/domain/prompt/assembler.py)):
  * Import `GitDiffResult` and `GitLogResult` from [shared/types/git_types.py](file:///home/hao/Desktop/labs/Synapse-Desktop/shared/types/git_types.py) instead of `infrastructure.git.git_utils`.

---

### Component 4: Clean up Unused Functions and Imports in Application
* **Preview Analyzer** ([preview_analyzer.py](file:///home/hao/Desktop/labs/Synapse-Desktop/application/services/preview_analyzer.py)):
  * Delete the unused `get_change_color` function and remove `from presentation.config.theme import ThemeColors` import.
* **Error Context** ([__init__.py](file:///home/hao/Desktop/labs/Synapse-Desktop/application/services/error_context/__init__.py)):
  * Delete the unused `copy_error_to_clipboard` function and remove `from infrastructure.adapters.clipboard_utils import copy_to_clipboard` import.

---

### Component 5: Relocate Presentation-only Qt Threading Utilities
* **Action**: Move `qt_utils.py` from `infrastructure/adapters/qt_utils.py` to `presentation/utils/qt_utils.py`.
* **Rationale**: `qt_utils.py` is a UI-specific utility containing PySide6 code for thread-safe UI updates and background scheduling. It does not perform any system I/O or talk to external APIs. Moving it to `presentation/utils/` eliminates the UI's direct dependency on infrastructure without creating cycles, since neither `domain` nor `application` imports `qt_utils.py`.
* Update all references/imports in presentation files and tests to reflect this change.

---

### Component 6: Decouple UI from Remaining Infrastructure
For all other presentation files importing from `infrastructure`:
1. Use `shared.utils.file_utils` for filesystem checks (e.g. `is_binary_file`).
2. Wrap settings activities (`load_app_settings`, `update_app_setting`) or resolve them using the UI's own state or `ServiceContainer`.
3. Wrap Clipboard interactions using `container.clipboard`.
4. Wrap `HistoryService` and git repository activities (`RepoManager`) with application services.

---

## 3. Verification Plan

### Automated Tests
* Run unit tests:
  ```bash
  env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v
  ```
* Run type checker:
  ```bash
  env -u PYTHONHOME -u PYTHONPATH .venv/bin/pyrefly check
  ```
* Run linter:
  ```bash
  env -u PYTHONHOME -u PYTHONPATH .venv/bin/ruff check --fix .
  env -u PYTHONHOME -u PYTHONPATH .venv/bin/ruff format .
  ```
* Verify architecture checker in strict mode:
  ```bash
  .venv/bin/python tools/architecture/check_architecture.py --strict
  ```
