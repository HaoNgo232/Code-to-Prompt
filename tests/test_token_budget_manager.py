"""
Unit tests for domain/workflow/shared/token_budget_manager.py.
"""

import pytest
from pathlib import Path
from typing import Optional, List, Dict
from unittest.mock import MagicMock, patch

from domain.ports.tokenization_port import ITokenizationService
from domain.workflow.shared.token_budget_manager import (
    TokenBudgetManager,
    BudgetResult,
)
from domain.workflow.shared.file_slicer import FileSlice


class MockTokenizationService(ITokenizationService):
    """Mock Tokenization Service specifically configured for budget manager tests."""

    def __init__(
        self, token_map: Optional[dict] = None, default_tokens: int = 10
    ) -> None:
        self.token_map = token_map or {}
        self.default_tokens = default_tokens

    def count_tokens(self, text: str) -> int:
        if text in self.token_map:
            return self.token_map[text]
        return len(text) // 4 + self.default_tokens

    def estimate_tokens(self, text: str) -> int:
        return self.count_tokens(text)

    def count_tokens_for_file(self, file_path: Path) -> int:
        return self.default_tokens

    def count_tokens_batch_parallel(
        self,
        file_paths: List[Path],
        max_workers: int = 2,
        update_cache: bool = True,
    ) -> Dict[str, int]:
        return {str(p): self.default_tokens for p in file_paths}

    def clear_cache(self) -> None:
        pass

    def clear_file_from_cache(self, path: str) -> None:
        pass

    def is_binary_file(self, file_path: Path) -> bool:
        return False

    def get_model_name(self) -> str:
        return "gpt-4"

    def set_model_config(self, tokenizer_repo: Optional[str] = None) -> None:
        pass

    def reset_encoder(self) -> None:
        pass


@pytest.fixture
def mock_tok() -> MockTokenizationService:
    return MockTokenizationService()


def test_estimate_budget_allocation(mock_tok: MockTokenizationService) -> None:
    """Test estimate_budget_allocation with different options."""
    manager = TokenBudgetManager(tokenization_service=mock_tok, max_tokens=10000)

    # 1. Without git budget
    mock_tok.token_map["instruction text"] = 100
    alloc = manager.estimate_budget_allocation(
        "instruction text", file_count=3, include_git=False
    )
    assert alloc.instruction_budget == 100
    assert alloc.git_budget == 0
    assert alloc.overhead_budget == 500
    assert alloc.file_budget == 10000 - 100 - 500

    # 2. With git budget
    alloc_git = manager.estimate_budget_allocation(
        "instruction text", file_count=3, include_git=True
    )
    assert alloc_git.git_budget == 5000
    assert alloc_git.file_budget == 10000 - 100 - 500 - 5000


def test_fit_files_quick_estimate(
    tmp_path: Path, mock_tok: MockTokenizationService
) -> None:
    """Test fit_files_to_budget when quick estimate is successful (fits in budget)."""
    manager = TokenBudgetManager(tokenization_service=mock_tok, max_tokens=1000)

    # Create dummy files
    p1 = tmp_path / "primary.py"
    p1.write_text("print('primary')", encoding="utf-8")
    d1 = tmp_path / "dep.py"
    d1.write_text("print('dep')", encoding="utf-8")

    # Tokens: instruction = 10, overhead = 500. Quick estimate: 510 + 200 = 710 <= 800.
    # Actual tokens: instruction (10) + overhead (500) + primary (10+3) + dep (10+2) = 535 <= 1000.
    result = manager.fit_files_to_budget(
        primary_files=[p1],
        dependency_files=[d1],
        instructions="hello",
        workspace_root=tmp_path,
    )

    assert result.total_tokens == 538
    assert "primary.py" in result.file_contents
    assert "dep.py" in result.file_contents
    assert result.optimizations_applied == []


def test_fit_files_strategy_1_full_content(
    tmp_path: Path, mock_tok: MockTokenizationService
) -> None:
    """Test fit_files_to_budget when quick estimate fails but full content still fits."""
    manager = TokenBudgetManager(tokenization_service=mock_tok, max_tokens=1000)

    # Create dummy files
    p1 = tmp_path / "primary.py"
    p1.write_text("print('primary')", encoding="utf-8")
    d1 = tmp_path / "dep.py"
    d1.write_text("print('dep')", encoding="utf-8")

    # Quick estimate: base (instruction tokens (305) + 500) + 200 = 1005 > 800. Quick estimate fails.
    # Actual tokens: instruction (305) + overhead (500) + files (25) = 830 <= 1000. Fits in Strategy 1.
    long_instruction = "a" * 1180  # 1180 // 4 + 10 = 305 tokens
    result = manager.fit_files_to_budget(
        primary_files=[p1],
        dependency_files=[d1],
        instructions=long_instruction,
        workspace_root=tmp_path,
    )

    assert result.total_tokens == 832
    assert "primary.py" in result.file_contents
    assert result.optimizations_applied == []


def test_fit_files_strategy_2_smartify_dependencies(
    tmp_path: Path, mock_tok: MockTokenizationService
) -> None:
    """Test fit_files_to_budget when full content exceeds budget but smartifying dependencies works."""
    manager = TokenBudgetManager(tokenization_service=mock_tok, max_tokens=1000)

    p1 = tmp_path / "primary.py"
    p1.write_text("primary content", encoding="utf-8")
    d1 = tmp_path / "dep.py"
    d1.write_text("large dependency content", encoding="utf-8")

    # Tokens map:
    # Instruction: 300
    # Overhead: 500
    # Primary: 100
    # Dep (full): 200
    # Dep (smart): 20
    # Full total: 300 + 500 + 100 + 200 = 1100 > 1000 (exceeds)
    # Smartified total: 300 + 500 + 100 + 20 = 920 <= 1000 (fits!)
    mock_tok.token_map["long instruction"] = 300
    mock_tok.token_map["primary content"] = 100
    mock_tok.token_map["large dependency content"] = 200
    mock_tok.token_map["def dep_sig(): pass"] = 20

    with patch(
        "domain.workflow.shared.token_budget_manager.smart_parse",
        return_value="def dep_sig(): pass",
    ) as mock_parse:
        result = manager.fit_files_to_budget(
            primary_files=[p1],
            dependency_files=[d1],
            instructions="long instruction",
            workspace_root=tmp_path,
        )

        mock_parse.assert_called_once_with(str(d1), "large dependency content")
        assert result.total_tokens == 920
        assert "primary.py" in result.file_contents
        assert result.file_contents["dep.py"] == "def dep_sig(): pass"
        assert "smartified_dependencies" in result.optimizations_applied
        assert "dep.py" in result.files_smartified


def test_fit_files_strategy_2_smart_parse_failures(
    tmp_path: Path, mock_tok: MockTokenizationService
) -> None:
    """Test fit_files_to_budget when smart_parse returns None or raises exception."""
    manager = TokenBudgetManager(tokenization_service=mock_tok, max_tokens=1000)

    p1 = tmp_path / "primary.py"
    p1.write_text("primary content", encoding="utf-8")
    d1 = tmp_path / "dep_fail.py"
    d1.write_text("dep content", encoding="utf-8")

    # Setup tokens:
    # Instruction: 300
    # Overhead: 500
    # Primary: 100
    # Dep content: 500 (full total = 1400 > 1000, fails Strategy 1)
    mock_tok.token_map["long instruction"] = 300
    mock_tok.token_map["primary content"] = 100
    mock_tok.token_map["dep content"] = 500

    # 1. smart_parse returns None
    with (
        patch(
            "domain.workflow.shared.token_budget_manager.smart_parse", return_value=None
        ),
        patch("domain.workflow.shared.token_budget_manager.logger") as mock_logger,
    ):
        result = manager.fit_files_to_budget(
            primary_files=[p1],
            dependency_files=[d1],
            instructions="long instruction",
            workspace_root=tmp_path,
        )
        assert result.total_tokens == 900
        # If smart_parse returns None, it does not add to files_smartified
        assert "dep_fail.py" not in result.files_smartified
        # Verify logger.warning was called because failed_deps count exceeds 30%
        mock_logger.warning.assert_called_once()

    # 2. smart_parse raises exception
    with (
        patch(
            "domain.workflow.shared.token_budget_manager.smart_parse",
            side_effect=ValueError("Syntax Error"),
        ),
        patch("domain.workflow.shared.token_budget_manager.logger") as mock_logger,
    ):
        result = manager.fit_files_to_budget(
            primary_files=[p1],
            dependency_files=[d1],
            instructions="long instruction",
            workspace_root=tmp_path,
        )
        assert result.total_tokens == 900
        assert "dep_fail.py" not in result.files_smartified
        # Verify logger.warning was called for exception and for failed count
        assert mock_logger.warning.call_count >= 1


def test_fit_files_strategy_3_slice_primary_no_codemap(
    tmp_path: Path, mock_tok: MockTokenizationService
) -> None:
    """Test fit_files_to_budget slicing primary files using auto_slice_file when codemap_builder is None."""
    manager = TokenBudgetManager(
        tokenization_service=mock_tok, max_tokens=1000, codemap_builder=None
    )

    p1 = tmp_path / "primary.py"
    p1.write_text("large primary content", encoding="utf-8")
    d1 = tmp_path / "dep.py"
    d1.write_text("large dependency content", encoding="utf-8")

    # Tokens:
    # Instruction: 300, Overhead: 500
    # Primary (full): 300, Dep (full): 200, Dep (smart): 50
    # Total with smart dep: 300 + 500 + 300 + 50 = 1150 > 1000 (exceeds)
    # Primary (sliced): 100
    # Total with sliced primary + smart dep: 300 + 500 + 100 + 50 = 950 <= 1000 (fits!)
    mock_tok.token_map["long instruction"] = 300
    mock_tok.token_map["large primary content"] = 300
    mock_tok.token_map["large dependency content"] = 200
    mock_tok.token_map["def dep_sig(): pass"] = 50
    mock_tok.token_map["sliced primary"] = 100

    mock_slice = FileSlice(
        file_path="primary.py",
        content="sliced primary",
        start_line=5,
        end_line=15,
        total_lines=50,
        symbols_included=["foo"],
        is_full_file=False,
    )

    with (
        patch(
            "domain.workflow.shared.token_budget_manager.smart_parse",
            return_value="def dep_sig(): pass",
        ),
        patch(
            "domain.workflow.shared.token_budget_manager.auto_slice_file",
            return_value=mock_slice,
        ) as mock_slice_fn,
    ):
        result = manager.fit_files_to_budget(
            primary_files=[p1],
            dependency_files=[d1],
            instructions="long instruction",
            workspace_root=tmp_path,
            relevant_symbols={"primary.py": {"foo"}},
        )

        mock_slice_fn.assert_called_once_with(p1, {"foo"}, workspace_root=tmp_path)
        assert result.total_tokens == 950
        assert result.file_contents["primary.py"] == "sliced primary"
        assert "sliced_primary_files" in result.optimizations_applied
        assert "primary.py" in result.files_sliced


def test_fit_files_strategy_3_slice_primary_with_codemap(
    tmp_path: Path, mock_tok: MockTokenizationService
) -> None:
    """Test fit_files_to_budget slicing primary files using smart_truncate when codemap_builder is provided."""
    mock_builder = MagicMock()
    manager = TokenBudgetManager(
        tokenization_service=mock_tok, max_tokens=1000, codemap_builder=mock_builder
    )

    p1 = tmp_path / "primary.py"
    p1.write_text("large primary content", encoding="utf-8")
    d1 = tmp_path / "dep.py"
    d1.write_text("large dependency content", encoding="utf-8")

    mock_tok.token_map["long instruction"] = 300
    mock_tok.token_map["large primary content"] = 300
    mock_tok.token_map["large dependency content"] = 200
    mock_tok.token_map["def dep_sig(): pass"] = 50
    mock_tok.token_map["sliced primary"] = 100

    mock_slice = FileSlice(
        file_path="primary.py",
        content="sliced primary",
        start_line=5,
        end_line=15,
        total_lines=50,
        symbols_included=["foo"],
        is_full_file=False,
    )

    with (
        patch(
            "domain.workflow.shared.token_budget_manager.smart_parse",
            return_value="def dep_sig(): pass",
        ),
        patch(
            "domain.workflow.shared.token_budget_manager.smart_truncate",
            return_value=mock_slice,
        ) as mock_truncate_fn,
    ):
        result = manager.fit_files_to_budget(
            primary_files=[p1],
            dependency_files=[d1],
            instructions="long instruction",
            workspace_root=tmp_path,
            relevant_symbols={"primary.py": {"foo"}},
        )

        # Remaining budget for smart_truncate = 1000 - (300 + 500) = 200
        mock_truncate_fn.assert_called_once_with(
            p1,
            target_tokens=200,
            codemap_builder=mock_builder,
            relevance_hints={"foo"},
            workspace_root=tmp_path,
        )
        assert result.total_tokens == 950
        assert "primary.py" in result.files_sliced


def test_fit_files_strategy_3_hard_limit_enforced(
    tmp_path: Path, mock_tok: MockTokenizationService
) -> None:
    """Test that primary files are skipped if they exceed the remaining budget during slicing/smartifying."""
    manager = TokenBudgetManager(tokenization_service=mock_tok, max_tokens=1000)

    p1 = tmp_path / "primary.py"
    p1.write_text("large primary content", encoding="utf-8")
    d1 = tmp_path / "dep.py"
    d1.write_text("large dependency content", encoding="utf-8")

    # Tokens:
    # Instruction: 300, Overhead: 500
    # Remaining: 200
    # Primary slice: 250 tokens -> exceeds remaining 200, so skipped.
    # Dep smartified: 50 tokens -> fits in remaining 200, so kept.
    mock_tok.token_map["long instruction"] = 300
    mock_tok.token_map["large primary content"] = 300
    mock_tok.token_map["large dependency content"] = 200
    mock_tok.token_map["def dep_sig(): pass"] = 50
    mock_tok.token_map["sliced primary"] = 250  # huge slice

    mock_slice = FileSlice(
        file_path="primary.py",
        content="sliced primary",
        start_line=1,
        end_line=10,
        total_lines=10,
        symbols_included=[],
        is_full_file=False,
    )

    with (
        patch(
            "domain.workflow.shared.token_budget_manager.smart_parse",
            return_value="def dep_sig(): pass",
        ),
        patch(
            "domain.workflow.shared.token_budget_manager.auto_slice_file",
            return_value=mock_slice,
        ),
    ):
        result = manager.fit_files_to_budget(
            primary_files=[p1],
            dependency_files=[d1],
            instructions="long instruction",
            workspace_root=tmp_path,
        )

        # primary.py should be skipped because it exceeded budget
        assert "primary.py" not in result.file_contents
        assert "dep.py" in result.file_contents
        assert result.total_tokens == 300 + 500 + 50 == 850


def test_fit_files_strategy_4_smart_truncate_largest(
    tmp_path: Path, mock_tok: MockTokenizationService
) -> None:
    """Test fit_files_to_budget falling back to Strategy 4 (smart truncate largest files)."""
    manager = TokenBudgetManager(tokenization_service=mock_tok, max_tokens=1000)

    # Create two files with different sizes
    p1 = tmp_path / "small_primary.py"
    p1.write_text("small", encoding="utf-8")  # size = 5 bytes

    d1 = tmp_path / "large_dep.py"
    d1.write_text("large " * 100, encoding="utf-8")  # size = 600 bytes

    # Tokens map:
    # Instruction: 300, Overhead: 500
    # Remaining: 200
    # Setup mock returns for smart_truncate
    mock_slice_small = FileSlice(
        file_path="small_primary.py",
        content="small content",
        start_line=1,
        end_line=1,
        total_lines=1,
        symbols_included=[],
        is_full_file=True,
    )
    mock_slice_large = FileSlice(
        file_path="large_dep.py",
        content="truncated large",
        start_line=1,
        end_line=10,
        total_lines=50,
        symbols_included=[],
        is_full_file=False,
    )

    mock_tok.token_map["long instruction"] = 300
    mock_tok.token_map["small content"] = 30
    mock_tok.token_map["truncated large"] = 100

    def mock_smart_truncate(file_path: Path, target_tokens: int, **kwargs) -> FileSlice:
        if file_path.name == "small_primary.py":
            return mock_slice_small
        else:
            return mock_slice_large

    # Setup all previous strategies to exceed budget
    mock_tok.token_map["large " * 100] = 500
    with (
        patch(
            "domain.workflow.shared.token_budget_manager.smart_parse",
            return_value="def too_long_sig(): pass",
        ),
        # Make the smartified signature tokens huge so Strategy 2 & 3 exceed budget
        patch.object(
            mock_tok,
            "count_tokens",
            side_effect=lambda text: (
                900
                if text == "def too_long_sig(): pass"
                else mock_tok.token_map.get(text, 10)
            ),
        ),
        patch.object(
            TokenBudgetManager,
            "_try_slice_primary",
            return_value=BudgetResult(total_tokens=1500),
        ),
        patch(
            "domain.workflow.shared.token_budget_manager.smart_truncate",
            side_effect=mock_smart_truncate,
        ) as mock_truncate_fn,
    ):
        result = manager.fit_files_to_budget(
            primary_files=[p1],
            dependency_files=[d1],
            instructions="long instruction",
            workspace_root=tmp_path,
        )

        assert "small_primary.py" in result.file_contents
        assert "large_dep.py" in result.file_contents
        assert "smart_truncated" in result.optimizations_applied

        # Verify smart_truncate was called with allocated budget
        # Small file size = 5, Large file size = 600. Total size = 605.
        # Remaining budget = 1000 - 800 = 200.
        # Small allocation = max(200, 200 * 5 // 605) = 200 tokens
        # Large allocation = max(200, 200 * 600 // 605) = 200 tokens
        mock_truncate_fn.assert_any_call(
            p1, target_tokens=200, codemap_builder=None, workspace_root=tmp_path
        )
        mock_truncate_fn.assert_any_call(
            d1, target_tokens=200, codemap_builder=None, workspace_root=tmp_path
        )


def test_fit_files_strategy_4_smart_truncate_exception_handling(
    tmp_path: Path, mock_tok: MockTokenizationService
) -> None:
    """Test exception handling in Strategy 4 does not crash the entire fit execution."""
    manager = TokenBudgetManager(tokenization_service=mock_tok, max_tokens=1000)

    p1 = tmp_path / "primary.py"
    p1.write_text("content", encoding="utf-8")
    d1 = tmp_path / "dep.py"
    d1.write_text("dep content", encoding="utf-8")

    mock_tok.token_map["long instruction"] = 300
    mock_tok.token_map["content"] = 500

    with (
        patch(
            "domain.workflow.shared.token_budget_manager.smart_parse",
            return_value="sig",
        ),
        patch.object(
            mock_tok,
            "count_tokens",
            side_effect=lambda text: (
                900 if text == "sig" else mock_tok.token_map.get(text, 10)
            ),
        ),
        patch.object(
            TokenBudgetManager,
            "_try_slice_primary",
            return_value=BudgetResult(total_tokens=1500),
        ),
        patch(
            "domain.workflow.shared.token_budget_manager.smart_truncate",
            side_effect=RuntimeError("ast error"),
        ),
    ):
        result = manager.fit_files_to_budget(
            primary_files=[p1],
            dependency_files=[d1],
            instructions="long instruction",
            workspace_root=tmp_path,
        )

        # Slicing failed, so file_contents should be empty, but it returned a valid result
        assert result.file_contents == {}
        assert result.total_tokens == 300 + 500


def test_token_budget_manager_edge_cases(
    tmp_path: Path, mock_tok: MockTokenizationService
) -> None:
    """Test various edge cases and exception handling blocks in TokenBudgetManager."""
    p1 = tmp_path / "primary.py"
    p1.write_text("primary", encoding="utf-8")
    d1 = tmp_path / "dep.py"
    d1.write_text("dep", encoding="utf-8")

    manager = TokenBudgetManager(tokenization_service=mock_tok, max_tokens=1000)

    # 1. Exception in _read_full_content (line 225-226)
    with patch.object(Path, "read_text", side_effect=Exception("Read error")):
        result = manager.fit_files_to_budget([p1], [], "hello", tmp_path)
        assert "primary.py" not in result.file_contents

    # 2. Exception in _try_smartify_dependencies primary loop (line 261-262)
    mock_tok.token_map["long inst"] = 600
    mock_tok.token_map["primary"] = 600
    with patch.object(Path, "read_text", side_effect=Exception("Read error")):
        result = manager.fit_files_to_budget([p1], [], "long inst", tmp_path)
        assert "primary.py" not in result.file_contents

    # 3. UnicodeDecodeError in _try_smartify_dependencies deps loop (line 279)
    mock_tok.token_map["dep"] = 300
    original_read_text = Path.read_text

    def mock_read_text(self, *args, **kwargs):
        if self.name == "dep.py":
            raise UnicodeDecodeError("utf-8", b"", 0, 1, "invalid start byte")
        return original_read_text(self, *args, **kwargs)

    with patch.object(Path, "read_text", mock_read_text):
        result = manager.fit_files_to_budget([p1], [d1], "long inst", tmp_path)
        assert "dep.py" not in result.file_contents

    # 4. Exception in _try_slice_primary primary loop (line 349-350)
    mock_tok.token_map["sig"] = 900
    with (
        patch(
            "domain.workflow.shared.token_budget_manager.smart_parse",
            return_value="sig",
        ),
        patch(
            "domain.workflow.shared.token_budget_manager.auto_slice_file",
            side_effect=Exception("slice error"),
        ),
    ):
        result = manager.fit_files_to_budget([p1], [d1], "long inst", tmp_path)
        assert "primary.py" not in result.file_contents

    # 5. Enforce hard limit skip in _try_slice_primary deps loop (line 362)
    mock_slice = FileSlice("primary.py", "slice", 1, 1, 1, [], False)
    with (
        patch(
            "domain.workflow.shared.token_budget_manager.smart_parse",
            return_value="sig",
        ),
        patch.object(
            mock_tok,
            "count_tokens",
            side_effect=lambda text: (
                900 if text == "sig" else mock_tok.token_map.get(text, 10)
            ),
        ),
        patch(
            "domain.workflow.shared.token_budget_manager.auto_slice_file",
            return_value=mock_slice,
        ),
    ):
        result = manager.fit_files_to_budget([p1], [d1], "long inst", tmp_path)
        assert "dep.py" not in result.file_contents

    # 6. Exception in _try_slice_primary deps loop (line 368-369)
    with (
        patch(
            "domain.workflow.shared.token_budget_manager.smart_parse",
            side_effect=Exception("parse error"),
        ),
        patch(
            "domain.workflow.shared.token_budget_manager.auto_slice_file",
            return_value=mock_slice,
        ),
    ):
        result = manager.fit_files_to_budget([p1], [d1], "long inst", tmp_path)
        assert "dep.py" not in result.file_contents

    # 7. Enforce hard limit skip in _try_truncate_largest (line 422)
    mock_slice_huge = FileSlice("primary.py", "huge", 1, 1, 1, [], False)
    mock_tok.token_map["huge"] = 1200
    with (
        patch.object(
            TokenBudgetManager,
            "_try_slice_primary",
            return_value=BudgetResult(total_tokens=1500),
        ),
        patch(
            "domain.workflow.shared.token_budget_manager.smart_truncate",
            return_value=mock_slice_huge,
        ),
    ):
        result = manager.fit_files_to_budget([p1], [], "long inst", tmp_path)
        assert "primary.py" not in result.file_contents
