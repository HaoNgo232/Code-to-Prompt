"""
Unit tests for application/services/apply_service.py.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from application.services.apply_service import save_memory_block, convert_to_row_results
from domain.ports.action_result import ActionResult


def test_save_memory_block_empty(tmp_path: Path) -> None:
    """If memory block is empty or whitespace, it should return early."""
    save_memory_block(tmp_path, "   \n  ")
    synapse_dir = tmp_path / ".synapse"
    assert not synapse_dir.exists()


def test_save_memory_block_success(tmp_path: Path) -> None:
    """Test successful saving to both memory v2 and legacy memory.xml."""
    # Create the workspace
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Mock domain.memory.memory_service calls for v2
    mock_store = MagicMock()
    with (
        patch(
            "domain.memory.memory_service.load_memory_store", return_value=mock_store
        ) as mock_load,
        patch("domain.memory.memory_service.save_memory_store") as mock_save,
    ):
        save_memory_block(workspace, "New Memory Block Content", max_blocks=3)

        mock_load.assert_called_once_with(workspace)
        mock_store.add.assert_called_once()
        mock_save.assert_called_once_with(workspace, mock_store)

    # Check that memory.xml was created in .synapse/
    memory_file = workspace / ".synapse" / "memory.xml"
    assert memory_file.exists()
    content = memory_file.read_text(encoding="utf-8")
    assert "<synapse_memory>\nNew Memory Block Content\n</synapse_memory>" in content


def test_save_memory_block_v2_exception(tmp_path: Path) -> None:
    """Verify that an exception in memory v2 does not prevent legacy XML saving."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with (
        patch(
            "domain.memory.memory_service.load_memory_store",
            side_effect=Exception("v2 Error"),
        ),
        patch("application.services.apply_service.logger") as mock_logger,
    ):
        save_memory_block(workspace, "Memory Block v2 Failed Content")

        # Should warning log the failure
        mock_logger.warning.assert_called_once()

    # Verify memory.xml was still saved
    memory_file = workspace / ".synapse" / "memory.xml"
    assert memory_file.exists()
    content = memory_file.read_text(encoding="utf-8")
    assert "Memory Block v2 Failed Content" in content


def test_save_memory_block_legacy_existing_parsing(tmp_path: Path) -> None:
    """Test reading existing blocks and trimming to max_blocks."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    synapse_dir = workspace / ".synapse"
    synapse_dir.mkdir(parents=True)
    memory_file = synapse_dir / "memory.xml"

    # Pre-populate with XML blocks
    existing_content = (
        "<synapse_memory>\nBlock One Long Content\n</synapse_memory>\n\n"
        "<synapse_memory>\nBlock Two Long Content\n</synapse_memory>\n"
    )
    memory_file.write_text(existing_content, encoding="utf-8")

    save_memory_block(workspace, "Block Three Long Content", max_blocks=2)

    # Should only keep the last 2 blocks (Block Two and Block Three)
    content = memory_file.read_text(encoding="utf-8")
    assert "Block One Long Content" not in content
    assert "<synapse_memory>\nBlock Two Long Content\n</synapse_memory>" in content
    assert "<synapse_memory>\nBlock Three Long Content\n</synapse_memory>" in content


def test_save_memory_block_legacy_existing_invalid_xml_fallback(tmp_path: Path) -> None:
    """If existing memory.xml is invalid XML, preserve up to 2000 chars as single block."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    synapse_dir = workspace / ".synapse"
    synapse_dir.mkdir(parents=True)
    memory_file = synapse_dir / "memory.xml"

    # Write invalid content
    invalid_content = (
        "This is some unstructured text that has more than 10 chars but no tags."
    )
    memory_file.write_text(invalid_content, encoding="utf-8")

    save_memory_block(workspace, "Fresh Block")

    content = memory_file.read_text(encoding="utf-8")
    assert (
        "<synapse_memory>\nThis is some unstructured text that has more than 10 chars but no tags.\n</synapse_memory>"
        in content
    )
    assert "<synapse_memory>\nFresh Block\n</synapse_memory>" in content


def test_save_memory_block_legacy_read_exception(tmp_path: Path) -> None:
    """If reading memory.xml throws exception, handle it and start fresh list."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    synapse_dir = workspace / ".synapse"
    synapse_dir.mkdir(parents=True)
    memory_file = synapse_dir / "memory.xml"
    memory_file.touch()

    # Mock read_text to throw an error
    with (
        patch.object(Path, "read_text", side_effect=OSError("Read error")),
        patch("application.services.apply_service.logger") as mock_logger,
    ):
        save_memory_block(workspace, "Content After Read Error")

        # Verify logger.warning was called
        mock_logger.warning.assert_called_once()

    # The file should contain only the new block
    content = memory_file.read_text(encoding="utf-8")
    assert "<synapse_memory>\nContent After Read Error\n</synapse_memory>" in content


def test_save_memory_block_legacy_write_exception(tmp_path: Path) -> None:
    """If writing memory.xml fails, cleanup temp file and log error."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with (
        patch("os.replace", side_effect=OSError("Disk full")),
        patch("application.services.apply_service.logger") as mock_logger,
    ):
        save_memory_block(workspace, "Content That Fails Write")

        # Error should be caught and logged
        mock_logger.error.assert_called_once()

    # Temp file should not exist, memory.xml should not exist
    synapse_dir = workspace / ".synapse"
    tmp_file = synapse_dir / "memory.tmp"
    memory_file = synapse_dir / "memory.xml"
    assert not tmp_file.exists()
    assert not memory_file.exists()


def test_convert_to_row_results_success() -> None:
    """Test convert_to_row_results with all successful actions."""
    results = [
        ActionResult(success=True, action="create", path="a.py", message="OK"),
        ActionResult(success=True, action="modify", path="b.py", message="OK"),
    ]
    row_results = convert_to_row_results(results, [])
    assert len(row_results) == 2
    assert all(r.success for r in row_results)
    assert not any(r.is_cascade_failure for r in row_results)


def test_convert_to_row_results_cascade() -> None:
    """Test convert_to_row_results detecting cascade failures on the same file."""
    results = [
        ActionResult(success=True, action="modify", path="a.py", message="OK"),
        ActionResult(
            success=False, action="modify", path="a.py", message="Search fail"
        ),
    ]
    row_results = convert_to_row_results(results, [])
    assert len(row_results) == 2
    assert row_results[0].success is True
    assert row_results[1].success is False
    assert row_results[1].is_cascade_failure is True
