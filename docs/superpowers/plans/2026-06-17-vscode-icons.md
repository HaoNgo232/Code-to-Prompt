# VS Code Material Icon Theme Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current font-based `qtawesome` file tree icons in Synapse Desktop with the full official VS Code Material Icon Theme by implementing a dev-time asset downloader and a dynamic SVG rendering tree delegate.

**Architecture:** A Python script `scripts/fetch_material_icons.py` downloads and extracts the VS Code Material Icon Theme resources (SVGs + mapping JSON) from the Marketplace at build/dev time. The `FileTreeDelegate` uses `MaterialIconMapper` to parse the mappings and render the SVGs on the fly using `QSvgRenderer` with caching. A fallback to `qtawesome` is kept if assets are missing.

**Tech Stack:** Python 3.12, PySide6 (QtGui, QtSvg), `requests`, `zipfile`

## Global Constraints

- Keep Git repository clean: Add `assets/material-icons/` to `.gitignore`.
- Safe fallback: If assets are not found, fallback to `qtawesome` icons. No crash allowed.
- Dynamic SVG Rendering: Load and render SVGs using `QSvgRenderer` onto a `QPixmap` of size 16x16, cached by path.

---

### Task 1: Asset Downloader Script

**Files:**
- Create: `scripts/fetch_material_icons.py`
- Create: `tests/test_fetch_material_icons.py`

**Interfaces:**
- Consumes: None
- Produces:
  - `scripts/fetch_material_icons.py` containing function `fetch_icons(output_dir: Path, force: bool = False) -> bool`

- [ ] **Step 1: Write the failing test**

Create `tests/test_fetch_material_icons.py`:
```python
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
import zipfile
import shutil

def test_fetch_icons_success():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        output_dir = tmp_path / "material-icons"
        
        # Create a mock ZIP file (VSIX)
        zip_file = tmp_path / "extension.vsix"
        with zipfile.ZipFile(zip_file, "w") as zf:
            zf.writestr("extension/dist/material-icons.json", '{"iconDefinitions": {}}')
            zf.writestr("extension/icons/python.svg", "<svg></svg>")
            
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = zip_file.read_bytes()
        
        with patch("requests.get", return_value=mock_response):
            from scripts.fetch_material_icons import fetch_icons
            result = fetch_icons(output_dir, force=True)
            
        assert result is True
        assert (output_dir / "material-icons.json").exists()
        assert (output_dir / "icons" / "python.svg").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/test_fetch_material_icons.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'scripts.fetch_material_icons')

- [ ] **Step 3: Write minimal implementation**

Create `scripts/fetch_material_icons.py`:
```python
import os
import sys
import zipfile
from pathlib import Path
import io
import requests

VSIX_URL = "https://marketplace.visualstudio.com/_apis/public/gallery/publishers/PKief/vsextensions/material-icon-theme/latest/vspackage"

def fetch_icons(output_dir: Path, force: bool = False) -> bool:
    if output_dir.exists() and (output_dir / "material-icons.json").exists() and not force:
        print("Material icons already exist. Skipping download.")
        return True

    print(f"Downloading VS Code Material Icon Theme from {VSIX_URL}...")
    try:
        response = requests.get(VSIX_URL, timeout=30)
        if response.status_code != 200:
            print(f"Failed to download: HTTP {response.status_code}")
            return False
        
        # VSIX is a ZIP file. Read it in memory.
        zip_data = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_data) as zf:
            # Create directories
            output_dir.mkdir(parents=True, exist_ok=True)
            icons_dir = output_dir / "icons"
            icons_dir.mkdir(parents=True, exist_ok=True)
            
            # Extract relevant files
            for file_info in zf.infolist():
                name = file_info.filename
                if name == "extension/dist/material-icons.json":
                    content = zf.read(file_info)
                    with open(output_dir / "material-icons.json", "wb") as f:
                        f.write(content)
                elif name.startswith("extension/icons/") and name.endswith(".svg"):
                    content = zf.read(file_info)
                    filename = Path(name).name
                    with open(icons_dir / filename, "wb") as f:
                        f.write(content)
                        
        print("Successfully extracted material icons.")
        return True
    except Exception as e:
        print(f"Error fetching icons: {e}")
        return False

if __name__ == "__main__":
    script_dir = Path(__file__).parent.parent
    dest = script_dir / "assets" / "material-icons"
    fetch_icons(dest, force="--force" in sys.argv)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/test_fetch_material_icons.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/fetch_material_icons.py tests/test_fetch_material_icons.py
git commit -m "feat: add fetch_material_icons script and tests"
```

---

### Task 2: Build and Git Integration

**Files:**
- Modify: `.gitignore`
- Modify: `build-windows.ps1:115-120`
- Modify: `build-appimage.sh:70-75`

**Interfaces:**
- Consumes: `scripts/fetch_material_icons.py`

- [ ] **Step 1: Update .gitignore**

Add to the end of `.gitignore`:
```text
# Material icons assets
assets/material-icons/
```

- [ ] **Step 2: Update build-windows.ps1**

Insert the fetch command execution inside [build-windows.ps1](file:///d:/share_vm/Synapse-Desktop/build-windows.ps1) right before collecting assets:
```powershell
# ── Step 3b: Fetch Material Icons if missing ───────────────────
$MATERIAL_ICONS_DIR = Join-Path $ASSETS_DIR "material-icons"
if (-not (Test-Path $MATERIAL_ICONS_DIR)) {
    Write-Host "  Material icons missing. Fetching..." -ForegroundColor Green
    & $VENV_PYTHON scripts/fetch_material_icons.py
}
```

- [ ] **Step 3: Update build-appimage.sh**

Insert the fetch command execution inside [build-appimage.sh](file:///d:/share_vm/Synapse-Desktop/build-appimage.sh) right before PyInstaller execution:
```bash
echo "Fetching material icons if missing..."
python3 scripts/fetch_material_icons.py
```

- [ ] **Step 4: Manual verification of build integration**

Remove `assets/material-icons` if it exists. Then run:
```powershell
python scripts/fetch_material_icons.py
```
Verify the directory `assets/material-icons` is created with a `material-icons.json` and `icons/` folder filled with SVGs.

- [ ] **Step 5: Commit**

```bash
git add .gitignore build-windows.ps1 build-appimage.sh
git commit -m "build: integrate fetch_material_icons into build process and gitignore"
```

---

### Task 3: `MaterialIconMapper` Implementation

**Files:**
- Create: `tests/presentation/test_file_tree_delegate.py`
- Modify: `presentation/components/file_tree/file_tree_delegate.py`

**Interfaces:**
- Consumes: `assets/material-icons/material-icons.json` structure
- Produces: `MaterialIconMapper` class with:
  - `__init__(assets_dir: Path)`
  - `get_icon_path(name: str, is_dir: bool, is_expanded: bool) -> Optional[str]`

- [ ] **Step 1: Write the failing test**

Create `tests/presentation/test_file_tree_delegate.py`:
```python
import pytest
from pathlib import Path
import json
import tempfile
import shutil

def test_material_icon_mapper():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        
        # Mock configuration JSON
        config = {
            "iconDefinitions": {
                "_file": {"iconPath": "icons/default_file.svg"},
                "_folder": {"iconPath": "icons/default_folder.svg"},
                "_folder_open": {"iconPath": "icons/default_folder_open.svg"},
                "python": {"iconPath": "icons/python.svg"},
                "folder_src": {"iconPath": "icons/folder_src.svg"},
                "folder_src_open": {"iconPath": "icons/folder_src_open.svg"}
            },
            "file": "_file",
            "folder": "_folder",
            "folderExpanded": "_folder_open",
            "fileExtensions": {
                "py": "python"
            },
            "fileNames": {
                "package.json": "nodejs"
            },
            "folderNames": {
                "src": "folder_src"
            },
            "folderNamesExpanded": {
                "src": "folder_src_open"
            }
        }
        
        # Write JSON config
        mat_dir = assets_dir / "material-icons"
        mat_dir.mkdir()
        with open(mat_dir / "material-icons.json", "w") as f:
            json.dump(config, f)
            
        # Create empty dummy icons
        icons_dir = mat_dir / "icons"
        icons_dir.mkdir()
        for key in ["default_file", "default_folder", "default_folder_open", "python", "folder_src", "folder_src_open"]:
            (icons_dir / f"{key}.svg").touch()
            
        # Test Mapper
        from presentation.components.file_tree.file_tree_delegate import MaterialIconMapper
        mapper = MaterialIconMapper(assets_dir)
        assert mapper.enabled is True
        
        # Test extensions
        p = mapper.get_icon_path("main.py", is_dir=False, is_expanded=False)
        assert p is not None
        assert Path(p).name == "python.svg"
        
        # Test folder closed
        p = mapper.get_icon_path("src", is_dir=True, is_expanded=False)
        assert p is not None
        assert Path(p).name == "folder_src.svg"
        
        # Test folder open
        p = mapper.get_icon_path("src", is_dir=True, is_expanded=True)
        assert p is not None
        assert Path(p).name == "folder_src_open.svg"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/presentation/test_file_tree_delegate.py -v`
Expected: FAIL (ImportError: cannot import name 'MaterialIconMapper' from 'presentation.components.file_tree.file_tree_delegate')

- [ ] **Step 3: Implement MaterialIconMapper class**

Modify [file_tree_delegate.py](file:///d:/share_vm/Synapse-Desktop/presentation/components/file_tree/file_tree_delegate.py) (Add `MaterialIconMapper` class at the top, after imports):
```python
import json
import logging

logger = logging.getLogger(__name__)

class MaterialIconMapper:
    """Parses material-icons.json and maps files/folders to their SVG icons."""
    def __init__(self, assets_dir: Path):
        self.assets_dir = assets_dir
        self.json_path = assets_dir / "material-icons" / "material-icons.json"
        self.icons_dir = assets_dir / "material-icons"
        self.enabled = False
        self.data: dict = {}
        self.load_config()

    def load_config(self):
        if not self.json_path.exists():
            logger.info(f"Material-icons config not found at {self.json_path}. Falling back to default icons.")
            return
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
            self.enabled = True
        except Exception as e:
            logger.error(f"Failed to load material-icons config: {e}")

    def get_icon_path(self, name: str, is_dir: bool, is_expanded: bool = False) -> str | None:
        if not self.enabled:
            return None

        name_lower = name.lower()

        if is_dir:
            icon_def = None
            if is_expanded:
                icon_def = self.data.get("folderNamesExpanded", {}).get(name_lower)
            if not icon_def:
                icon_def = self.data.get("folderNames", {}).get(name_lower)
            if not icon_def:
                icon_def = self.data.get("folderExpanded" if is_expanded else "folder")
            return self._resolve_definition(icon_def)

        # 1. Exact filename match
        icon_def = self.data.get("fileNames", {}).get(name_lower)

        # 2. Extension match
        if not icon_def:
            parts = name_lower.split(".")
            if len(parts) > 1:
                # Check multi-part extensions (e.g. test.spec.js)
                for i in range(1, len(parts)):
                    ext = ".".join(parts[i:])
                    icon_def = self.data.get("fileExtensions", {}).get(ext)
                    if icon_def:
                        break

        # 3. Default file fallback
        if not icon_def:
            icon_def = self.data.get("file")

        return self._resolve_definition(icon_def)

    def _resolve_definition(self, icon_def: str | None) -> str | None:
        if not icon_def:
            return None
        definition = self.data.get("iconDefinitions", {}).get(icon_def)
        if not definition:
            return None
        rel_path = definition.get("iconPath")
        if not rel_path:
            return None
        if rel_path.startswith("./"):
            rel_path = rel_path[2:]
        elif rel_path.startswith("/"):
            rel_path = rel_path[1:]

        full_path = self.icons_dir / rel_path
        if full_path.exists():
            return str(full_path)
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/presentation/test_file_tree_delegate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add presentation/components/file_tree/file_tree_delegate.py tests/presentation/test_file_tree_delegate.py
git commit -m "feat: implement MaterialIconMapper with tests"
```

---

### Task 4: Integrate `MaterialIconMapper` into `FileTreeDelegate`

**Files:**
- Modify: `presentation/components/file_tree/file_tree_delegate.py:157-178` (Modify `_draw_file_icon` and `paint` method)
- Modify: `tests/presentation/test_file_tree_delegate.py` (Add integration test for FileTreeDelegate)

**Interfaces:**
- Consumes: `MaterialIconMapper`
- Produces: Updated `FileTreeDelegate` class rendering custom SVG icons

- [ ] **Step 1: Write integration tests**

Add to `tests/presentation/test_file_tree_delegate.py`:
```python
from unittest.mock import patch, MagicMock
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QStyleOptionViewItem

def test_file_tree_delegate_fallback():
    # Test that delegate falls back to qtawesome when assets are missing
    from presentation.components.file_tree.file_tree_delegate import FileTreeDelegate
    delegate = FileTreeDelegate()
    assert delegate._icon_mapper.enabled is False
```

- [ ] **Step 2: Run test to verify it passes**

Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/presentation/test_file_tree_delegate.py -v`
Expected: PASS

- [ ] **Step 3: Implement dynamic rendering and caching in delegate**

Modify [file_tree_delegate.py](file:///d:/share_vm/Synapse-Desktop/presentation/components/file_tree/file_tree_delegate.py):
1. Resolve dynamic `ASSETS_DIR` at the top:
```python
import sys
from pathlib import Path

if hasattr(sys, "_MEIPASS"):
    ASSETS_DIR = Path(sys._MEIPASS) / "assets"
else:
    ASSETS_DIR = Path(__file__).parent.parent.parent.parent / "assets"
```

2. Inside `FileTreeDelegate.__init__`, initialize `self._icon_mapper`:
```python
    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_query: str = ""
        self._icon_mapper = MaterialIconMapper(ASSETS_DIR)
```

3. Update the global SVG icon cache and rendering helper at module-level:
```python
_svg_icon_cache: dict[str, QPixmap] = {}

def _get_svg_pixmap(svg_path: str, size: int = ICON_SIZE) -> QPixmap:
    cache_key = f"{svg_path}_{size}"
    if cache_key not in _svg_icon_cache:
        try:
            from PySide6.QtSvg import QSvgRenderer
            renderer = QSvgRenderer(svg_path)
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
            
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            
            _svg_icon_cache[cache_key] = pixmap
        except Exception as e:
            logger.error(f"Failed to render SVG {svg_path}: {e}")
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
            _svg_icon_cache[cache_key] = pixmap
    return _svg_icon_cache[cache_key]
```

4. Modify `_draw_file_icon` function to accept `mapper` and `is_expanded`:
```python
def _draw_file_icon(
    painter: QPainter, x: int, y: int, label: str, is_dir: bool, height: int, mapper: MaterialIconMapper, is_expanded: bool = False
):
    """Vẽ icon bằng Material SVG hoặc dự phòng qtawesome pixmap."""
    svg_path = mapper.get_icon_path(label, is_dir, is_expanded)
    if svg_path:
        pixmap = _get_svg_pixmap(svg_path)
    else:
        # Fallback to original qtawesome logic
        if is_dir:
            pixmap = _get_qta_pixmap("mdi6.folder", COLOR_FOLDER)
        else:
            icon_name = "mdi6.file-outline"
            icon_color = COLOR_FILE

            for ext, (name, color) in _EXT_ICONS.items():
                if label.endswith(ext):
                    icon_name = name
                    icon_color = QColor(color)
                    break

            pixmap = _get_qta_pixmap(icon_name, icon_color)

    icon_y = y + (height - ICON_SIZE) // 2
    painter.drawPixmap(x, icon_y, pixmap)
```

5. Modify `paint` method where `_draw_file_icon` is called:
```python
        # Check if expanded
        is_expanded = bool(state & QStyle.StateFlag.State_Open)

        # 2. Draw icon (Material Design)
        _draw_file_icon(painter, x, y, label, is_dir or False, height, self._icon_mapper, is_expanded)
        x += ICON_SIZE + SPACING
```

6. Modify `get_hit_zone` to also use `self._icon_mapper`:
We need to verify if `is_expanded` is needed or if folder matches are sufficient. We can default it to `False` inside `get_hit_zone`.

- [ ] **Step 4: Run tests to verify all tests pass**

Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/presentation/test_file_tree_delegate.py -v`
Expected: PASS

Run all presentation tests:
`env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/presentation/ -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add presentation/components/file_tree/file_tree_delegate.py tests/presentation/test_file_tree_delegate.py
git commit -m "feat: integrate MaterialIconMapper rendering into FileTreeDelegate"
```
