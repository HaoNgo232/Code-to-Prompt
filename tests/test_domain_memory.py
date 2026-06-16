"""
Tests cho module Memory ở domain layer (domain/memory/)
"""

from domain.memory.memory_types import MemoryEntry, MemoryStore
from domain.memory.memory_service import (
    load_memory_store,
    save_memory_store,
    add_memory,
)
from domain.memory.memory_prompt_adapter import load_memory_for_prompt


def test_memory_entry_dataclass():
    """Test MemoryEntry properties, to_dict và from_dict."""
    entry = MemoryEntry(
        layer="action",
        content="Fixed test runner bug",
        linked_files=["tests/test_bug.py"],
        linked_symbols=["test_bug"],
        workflow="rp_review",
        tags=["bugfix", "tests"],
    )
    assert entry.layer == "action"
    assert entry.content == "Fixed test runner bug"
    assert entry.timestamp != ""
    assert entry.linked_files == ["tests/test_bug.py"]
    assert entry.linked_symbols == ["test_bug"]
    assert entry.workflow == "rp_review"
    assert entry.tags == ["bugfix", "tests"]

    # Test roundtrip dict
    d = entry.to_dict()
    restored = MemoryEntry.from_dict(d)
    assert restored.layer == entry.layer
    assert restored.content == entry.content
    assert restored.timestamp == entry.timestamp
    assert restored.linked_files == entry.linked_files
    assert restored.linked_symbols == entry.linked_symbols
    assert restored.workflow == entry.workflow
    assert restored.tags == entry.tags


def test_memory_store_dataclass():
    """Test MemoryStore functionalities."""
    store = MemoryStore()
    assert store.version == 2
    assert len(store.entries) == 0

    e1 = MemoryEntry(
        layer="action",
        content="Action content",
        linked_files=["file1.py"],
        workflow="w1",
    )
    e2 = MemoryEntry(
        layer="decision",
        content="Decision content",
        linked_files=["file2.py"],
        workflow="w2",
    )
    e3 = MemoryEntry(
        layer="constraint",
        content="Constraint content",
        linked_files=["file1.py", "file2.py"],
        workflow="w1",
    )

    store.add(e1)
    store.add(e2)
    store.add(e3)

    assert len(store.entries) == 3

    # get_by_layer
    assert store.get_by_layer("action") == [e1]
    assert store.get_by_layer("decision") == [e2]
    assert store.get_by_layer("constraint") == [e3]

    # get_by_file
    assert store.get_by_file("file1.py") == [e1, e3]
    assert store.get_by_file("file2.py") == [e2, e3]
    assert store.get_by_file("nonexistent.py") == []

    # get_by_workflow
    assert store.get_by_workflow("w1") == [e1, e3]
    assert store.get_by_workflow("w2") == [e2]

    # to_dict/from_dict
    d = store.to_dict()
    assert d["version"] == 2
    assert len(d["entries"]) == 3

    restored = MemoryStore.from_dict(d)
    assert restored.version == 2
    assert len(restored.entries) == 3
    assert restored.entries[0].content == "Action content"


def test_memory_store_format_for_prompt():
    """Test định dạng MemoryStore thành chuỗi prompt."""
    store = MemoryStore()
    assert store.format_for_prompt() == ""

    e1 = MemoryEntry(layer="constraint", content="Constraint 1")
    e2 = MemoryEntry(layer="decision", content="Decision 1", linked_files=["file.py"])
    e3 = MemoryEntry(layer="action", content="Action 1")

    store.add(e1)
    store.add(e2)
    store.add(e3)

    formatted = store.format_for_prompt(max_entries=5)
    assert "<Project Constraints>" in formatted
    assert "- Constraint 1" in formatted
    assert "<Past Decisions>" in formatted
    assert "- Decision 1" in formatted
    assert "  Files: file.py" in formatted
    assert "<Recent Actions>" in formatted
    assert "- Action 1" in formatted


def test_load_memory_store_nonexistent(tmp_path):
    """Test load store từ file chưa tồn tại."""
    store = load_memory_store(tmp_path)
    assert isinstance(store, MemoryStore)
    assert len(store.entries) == 0


def test_load_memory_store_corrupted(tmp_path):
    """Test load store từ file bị hỏng hoặc lỗi JSON."""
    synapse_dir = tmp_path / ".synapse"
    synapse_dir.mkdir()
    memory_file = synapse_dir / "memory_v2.json"
    memory_file.write_text("invalid json format {{{", encoding="utf-8")

    store = load_memory_store(tmp_path)
    assert isinstance(store, MemoryStore)
    assert len(store.entries) == 0


def test_load_save_memory_store_roundtrip(tmp_path):
    """Test luồng ghi rồi đọc bộ nhớ."""
    store = MemoryStore()
    e = MemoryEntry(layer="action", content="Hello test")
    store.add(e)

    save_memory_store(tmp_path, store)

    # Đọc lại
    loaded = load_memory_store(tmp_path)
    assert len(loaded.entries) == 1
    assert loaded.entries[0].content == "Hello test"


def test_add_memory_logic(tmp_path):
    """Test add_memory thêm entry mới và kiểm soát giới hạn max_entries."""
    # Thêm memory lần đầu
    add_memory(tmp_path, "action", "Content 1", max_entries=2)

    loaded = load_memory_store(tmp_path)
    assert len(loaded.entries) == 1
    assert loaded.entries[0].content == "Content 1"

    # Thêm memory lần hai
    add_memory(tmp_path, "action", "Content 2", max_entries=2)
    loaded = load_memory_store(tmp_path)
    assert len(loaded.entries) == 2

    # Thêm memory lần ba, vượt quá max_entries=2, entry cũ nhất ("Content 1") phải bị xóa
    add_memory(tmp_path, "action", "Content 3", max_entries=2)
    loaded = load_memory_store(tmp_path)
    assert len(loaded.entries) == 2
    contents = [e.content for e in loaded.entries]
    assert "Content 1" not in contents
    assert "Content 2" in contents
    assert "Content 3" in contents


def test_add_memory_corrupted_file_handles(tmp_path):
    """Test add_memory khi file bị corrupt, nó tự tạo store mới không crash."""
    synapse_dir = tmp_path / ".synapse"
    synapse_dir.mkdir(parents=True)
    memory_file = synapse_dir / "memory_v2.json"
    memory_file.write_text("corrupted json", encoding="utf-8")

    # Không bị crash, tự overwrite
    add_memory(tmp_path, "decision", "New Decision", max_entries=2)

    loaded = load_memory_store(tmp_path)
    assert len(loaded.entries) == 1
    assert loaded.entries[0].content == "New Decision"


def test_load_memory_for_prompt_v2(tmp_path):
    """Test load_memory_for_prompt trả về nội dung v2 nếu tồn tại."""
    store = MemoryStore()
    store.add(MemoryEntry(layer="constraint", content="Memory V2 Constraint"))
    save_memory_store(tmp_path, store)

    formatted = load_memory_for_prompt(tmp_path)
    assert formatted is not None
    assert "Memory V2 Constraint" in formatted


def test_load_memory_for_prompt_legacy_fallback(tmp_path):
    """Test load_memory_for_prompt fallback sang legacy memory.xml khi v2 rỗng."""
    synapse_dir = tmp_path / ".synapse"
    synapse_dir.mkdir(parents=True)

    # Không tạo v2, chỉ tạo legacy xml
    xml_file = synapse_dir / "memory.xml"
    xml_file.write_text("<memory>Legacy Content</memory>", encoding="utf-8")

    formatted = load_memory_for_prompt(tmp_path)
    assert formatted == "<memory>Legacy Content</memory>"


def test_load_memory_for_prompt_empty(tmp_path):
    """Test load_memory_for_prompt trả về None khi không có file nào."""
    formatted = load_memory_for_prompt(tmp_path)
    assert formatted is None


def test_load_memory_for_prompt_legacy_exception(tmp_path):
    """Test load_memory_for_prompt trả về None khi đọc legacy file bị lỗi."""
    synapse_dir = tmp_path / ".synapse"
    synapse_dir.mkdir(parents=True)

    # Tạo folder thay vì file để tạo exception khi đọc text
    xml_file = synapse_dir / "memory.xml"
    xml_file.mkdir()

    formatted = load_memory_for_prompt(tmp_path)
    assert formatted is None
