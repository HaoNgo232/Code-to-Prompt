import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from application.services.workspace_rules import (
    load_workspace_rules,
    save_workspace_rules,
    add_rule_file,
    remove_rule_file,
    is_rule_file,
    get_rule_file_contents,
    _get_rules_path
)

class TestWorkspaceRulesExtra:
    def test_get_rules_path_permission_error(self):
        # Trigger OSError in _get_rules_path (lines 24-25)
        # We mock Path.mkdir to raise PermissionError
        with patch.object(Path, "mkdir", side_effect=PermissionError("Mock Denied")):
            res = _get_rules_path(Path("/fake/workspace"))
            assert res == Path("/fake/workspace/.synapse/project_rules.json")

    def test_load_workspace_rules_errors(self, tmp_path):
        rules_file = tmp_path / ".synapse" / "project_rules.json"
        rules_file.parent.mkdir(parents=True, exist_ok=True)

        # 1. JSONDecodeError (lines 44-46)
        rules_file.write_text("invalid json {", encoding="utf-8")
        res1 = load_workspace_rules(tmp_path)
        assert res1 == set()

        # 2. OSError (lines 44-46)
        # Mock Path.read_text to raise OSError
        with patch.object(Path, "read_text", side_effect=OSError("Mock Disk Error")):
            res2 = load_workspace_rules(tmp_path)
            assert res2 == set()

    def test_save_workspace_rules_error(self, tmp_path):
        # Trigger OSError in save_workspace_rules (lines 55-56)
        with patch.object(Path, "write_text", side_effect=OSError("Mock Write Error")):
            save_workspace_rules(tmp_path, {"test.md"})
            # Should log error and not raise exception

    def test_add_rule_file_not_in_workspace(self, tmp_path):
        # File outside workspace triggers ValueError -> logs warning and returns (lines 69-71)
        outside_file = "/outside/path/rules.md"
        add_rule_file(tmp_path, outside_file)
        
        # Verify it wasn't added
        rules = load_workspace_rules(tmp_path)
        assert len(rules) == 0

    def test_remove_rule_file_not_in_workspace(self, tmp_path):
        # File outside workspace triggers ValueError -> returns (lines 89-90)
        outside_file = "/outside/path/rules.md"
        remove_rule_file(tmp_path, outside_file) # Should not raise exception

    def test_is_rule_file_not_in_workspace(self, tmp_path):
        # File outside workspace triggers ValueError -> returns False (lines 111-112)
        outside_file = "/outside/path/rules.md"
        res = is_rule_file(tmp_path, outside_file)
        assert res is False

    def test_get_rule_file_contents_edge_cases(self, tmp_path):
        # Setup workspace_rules first
        rules = {"rule1.md", "rule2.md", "rule3.md", "rule4.md"}
        save_workspace_rules(tmp_path, rules)

        # 1. rule1.md: exists and fits normally
        rule1 = tmp_path / "rule1.md"
        rule1.write_text("content 1", encoding="utf-8")

        # 2. rule2.md: non-existent file (lines 133-134)

        # 3. rule3.md: file too large (lines 138-139)
        rule3 = tmp_path / "rule3.md"
        rule3.write_text("a" * 15, encoding="utf-8") # size 15

        # 4. rule4.md: permission error reading file (lines 143-144)
        rule4 = tmp_path / "rule4.md"
        rule4.write_text("content 4", encoding="utf-8")

        # Helper mocks
        orig_stat = Path.stat
        orig_read = Path.read_text

        def mock_stat(self_obj, *args, **kwargs):
            if "rule3.md" in str(self_obj):
                # Fake a large size
                mock_stat_val = MagicMock()
                mock_stat_val.st_size = 11 * 1024 * 1024 # 11MB
                return mock_stat_val
            return orig_stat(self_obj, *args, **kwargs)

        def mock_read(self_obj, *args, **kwargs):
            if "rule4.md" in str(self_obj):
                raise PermissionError("Mock Read Denied")
            return orig_read(self_obj, *args, **kwargs)

        with patch.object(Path, "stat", mock_stat), \
             patch.object(Path, "read_text", mock_read):
            
            result = get_rule_file_contents(tmp_path)
            
            # verify rule1.md is present
            assert "--- Rule File: rule1.md ---" in result
            assert "content 1" in result
            
            # verify rule2.md (missing) is skipped
            # verify rule3.md (too large) is skipped
            assert "rule3.md" not in result
            
            # verify rule4.md (permission denied) is skipped
            assert "rule4.md" not in result

    def test_workspace_rules_success_paths(self, tmp_path):
        # 1. get_rule_file_contents empty (line 127)
        assert get_rule_file_contents(tmp_path) == ""

        rule_file_abs = str(tmp_path / "my_rules.md")
        # Ensure file exists
        Path(rule_file_abs).write_text("my custom instructions", encoding="utf-8")

        # 2. Add rule file success (lines 73-76)
        add_rule_file(tmp_path, rule_file_abs)
        assert is_rule_file(tmp_path, rule_file_abs) is True  # lines 114-115

        # Check content loader success
        contents = get_rule_file_contents(tmp_path)
        assert "my_rules.md" in contents
        assert "my custom instructions" in contents

        # 3. Remove rule file success (lines 92-95)
        remove_rule_file(tmp_path, rule_file_abs)
        assert is_rule_file(tmp_path, rule_file_abs) is False
