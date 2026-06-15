"""
GUI Tests cho HistoryViewQt và các panel thành phần: HistoryListPanel, HistoryDetailPanel, và widgets.
"""

import os
import pytest
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from typing import List, Optional, Dict, Any

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QFrame,
    QMessageBox,
)

from domain.ports.history_port import HistoryEntry, IHistoryService
from domain.ports.registry import DomainRegistry
from presentation.config.theme import ThemeColors
from presentation.views.history.widgets import (
    create_status_dot_icon,
    create_search_icon,
    format_date_group,
    group_entries_by_date,
    DateGroupHeader,
    OperationBadge,
    FileChangeRow,
    ErrorCard,
    make_ghost_btn,
    make_danger_btn,
    make_primary_btn,
)
from presentation.views.history.list_panel import HistoryListPanel
from presentation.views.history.detail_panel import HistoryDetailPanel
from presentation.views.history.view import HistoryViewQt


class MockHistoryService(IHistoryService):
    """Mock HistoryService để điều khiển dữ liệu trả về cho tests."""
    def __init__(self) -> None:
        self.entries: List[HistoryEntry] = []
        self.stats = {
            "total_entries": 0,
            "total_operations": 0,
            "success_rate": 0.0
        }
        self.delete_result = True
        self.clear_result = True
        self.deleted_ids = []

    def add_history_entry(
        self,
        workspace_path: str,
        opx_content: str,
        action_results: List[dict],
    ) -> Optional[HistoryEntry]:
        return None

    def get_history_entries(self, limit: int = 50) -> List[HistoryEntry]:
        return self.entries[:limit]

    def get_entry_by_id(self, entry_id: str) -> Optional[HistoryEntry]:
        for entry in self.entries:
            if entry.id == entry_id:
                return entry
        return None

    def delete_entry(self, entry_id: str) -> bool:
        self.deleted_ids.append(entry_id)
        if self.delete_result:
            self.entries = [e for e in self.entries if e.id != entry_id]
            return True
        return False

    def clear_history(self) -> bool:
        if self.clear_result:
            self.entries = []
            return True
        return False

    def get_history_stats(self) -> dict:
        return self.stats


@pytest.fixture
def mock_history_service():
    """Đăng ký MockHistoryService cho DomainRegistry."""
    old_service = None
    try:
        old_service = DomainRegistry.history_service()
    except RuntimeError:
        pass
        
    service = MockHistoryService()
    DomainRegistry.register_history_service(service)
    yield service
    
    if old_service is not None:
        DomainRegistry.register_history_service(old_service)


# Helper tạo HistoryEntry giả lập
def make_mock_entry(
    id_val: str,
    timestamp: str,
    file_count: int = 2,
    success_count: int = 2,
    fail_count: int = 0,
    action_summary: List[str] = None,
    error_messages: List[str] = None,
    opx_content: str = "Mock OPX content",
) -> HistoryEntry:
    if action_summary is None:
        action_summary = ["MODIFY file1.py", "CREATE file2.py"]
    if error_messages is None:
        error_messages = []
    return HistoryEntry(
        id=id_val,
        timestamp=timestamp,
        workspace_path="/mock/workspace",
        opx_content=opx_content,
        file_count=file_count,
        success_count=success_count,
        fail_count=fail_count,
        action_summary=action_summary,
        error_messages=error_messages,
    )


# ===========================================================================
# Widgets & Helper Tests
# ===========================================================================

def test_status_dot_icon_creation(qtbot):
    """Test sinh icon status dot không bị crash."""
    icon = create_status_dot_icon("#FF0000", 12)
    assert not icon.isNull()


def test_search_icon_creation(qtbot):
    """Test sinh icon search không bị crash."""
    icon = create_search_icon(16)
    assert not icon.isNull()



def test_format_date_group():
    """Test format date group (Today, Yesterday, MM/DD)."""
    now = datetime.now()
    assert "Today" in format_date_group(now)
    
    yesterday = now - timedelta(days=1)
    assert "Yesterday" in format_date_group(yesterday)
    
    other_date = datetime(2023, 5, 20, 10, 30)
    assert format_date_group(other_date) == "05/20"


def test_group_entries_by_date():
    """Test gom nhóm các entries lịch sử theo ngày."""
    now_str = datetime.now().isoformat()
    yesterday_str = (datetime.now() - timedelta(days=1)).isoformat()
    invalid_date_str = "invalid-date-format"
    
    e1 = make_mock_entry("1", now_str)
    e2 = make_mock_entry("2", yesterday_str)
    e3 = make_mock_entry("3", invalid_date_str)
    
    groups = group_entries_by_date([e1, e2, e3])
    
    assert any("Today" in k for k in groups.keys())
    assert any("Yesterday" in k for k in groups.keys())
    assert "Unknown" in groups
    assert groups["Unknown"][0].id == "3"


def test_custom_widgets_render(qtbot):
    """Test các widgets nhỏ custom được vẽ đúng."""
    # DateGroupHeader
    header = DateGroupHeader("Today")
    qtbot.addWidget(header)
    
    # OperationBadge
    badge_modify = OperationBadge("MODIFY")
    badge_unknown = OperationBadge("UNKNOWN")
    qtbot.addWidget(badge_modify)
    qtbot.addWidget(badge_unknown)
    
    # FileChangeRow
    row_success = FileChangeRow("MODIFY", "test.py", success=True)
    row_fail = FileChangeRow("DELETE", "test2.py", success=False)
    qtbot.addWidget(row_success)
    qtbot.addWidget(row_fail)
    
    # ErrorCard
    err_card_split = ErrorCard("main.py", "main.py: line 10 error")
    err_card_no_split = ErrorCard("Error", "General failure")
    qtbot.addWidget(err_card_split)
    qtbot.addWidget(err_card_no_split)
    
    # Nút style custom
    btn_ghost = make_ghost_btn("Ghost")
    btn_danger = make_danger_btn("Danger")
    btn_primary = make_primary_btn("Primary")
    qtbot.addWidget(btn_ghost)
    qtbot.addWidget(btn_danger)
    qtbot.addWidget(btn_primary)
    
    assert badge_modify.text() == "MODIFY"


# ===========================================================================
# History List Panel Tests
# ===========================================================================

def test_history_list_panel_empty(qtbot):
    """Test hiển thị khi danh sách lịch sử trống."""
    panel = HistoryListPanel()
    qtbot.addWidget(panel)
    panel.load_entries([])
    
    # Phải render nhãn "No operations yet"
    labels = panel.findChildren(QLabel)
    assert any(label.text() == "No operations yet" for label in labels)


def test_history_list_panel_with_entries(qtbot):
    """Test hiển thị danh sách entries và tương tác click, tìm kiếm."""
    panel = HistoryListPanel()
    qtbot.addWidget(panel)
    
    now_str = datetime.now().isoformat()
    e1 = make_mock_entry("uuid-1", now_str, file_count=3, success_count=2, fail_count=1)
    e2 = make_mock_entry("uuid-2", now_str, file_count=2, success_count=0, fail_count=2, action_summary=["CREATE helper.py"])
    
    # Load entries
    panel.load_entries([e1, e2])
    
    # Đếm số dòng
    # 1 dòng Date Header + 2 dòng entries
    assert panel._entry_list.count() == 3
    
    # Test Click chọn entry
    selected_ids = []
    panel._on_entry_selected = lambda x: selected_ids.append(x)
    
    # Lấy QListWidgetItem thứ 2 (đầu tiên là DateGroupHeader, thứ 2 là e1)
    item1 = panel._entry_list.item(1)
    assert item1.data(Qt.ItemDataRole.UserRole) == "uuid-1"
    
    # Click item
    panel._on_entry_clicked(item1)
    assert panel.get_selected_id() == "uuid-1"
    assert selected_ids == ["uuid-1"]
    
    # Click item khác
    item2 = panel._entry_list.item(2)
    panel._on_entry_clicked(item2)
    assert panel.get_selected_id() == "uuid-2"
    assert selected_ids == ["uuid-1", "uuid-2"]
    
    # Xóa selection
    panel.clear_selection()
    assert panel.get_selected_id() is None
    
    # Test Search Filter
    # Nhập search khớp uuid-1
    panel._search_input.setText("uuid-1")
    qtbot.wait(50)
    assert panel._entry_list.count() == 2 # 1 Date header + 1 entry
    
    # Nhập search khớp action_summary "helper"
    panel._search_input.setText("helper")
    qtbot.wait(50)
    assert panel._entry_list.count() == 2 # 1 Date header + e2
    
    # Nhập search không khớp gì cả
    panel._search_input.setText("non-existent-query")
    qtbot.wait(50)
    # Phải hiện "No operations yet"
    labels = panel.findChildren(QLabel)
    assert any(label.text() == "No operations yet" for label in labels)
    
    # Clear search
    panel._search_input.clear()
    qtbot.wait(50)
    assert panel._entry_list.count() == 3


# ===========================================================================
# History Detail Panel Tests
# ===========================================================================

def test_history_detail_panel_empty(qtbot):
    """Test Detail Panel ở trạng thái trống."""
    panel = HistoryDetailPanel()
    qtbot.addWidget(panel)
    panel.show_empty()
    
    labels = panel.findChildren(QLabel)
    assert any("Select an operation" in l.text() for l in labels)


def test_history_detail_panel_show_entry_success(qtbot, mock_history_service):
    """Test hiển thị entry thành công hoàn toàn."""
    panel = HistoryDetailPanel()
    qtbot.addWidget(panel)
    
    e = make_mock_entry(
        "uuid-success",
        datetime.now().isoformat(),
        file_count=2,
        success_count=2,
        fail_count=0,
    )
    panel.show_entry(e)
    
    labels = panel.findChildren(QLabel)
    # Tìm text done
    assert any("all successful" in l.text() for l in labels)
    
    # Test Copy OPX
    footer_messages = []
    panel._on_footer_message = lambda msg, is_err: footer_messages.append((msg, is_err))
    
    # Click nút Copy OPX
    btn_copy = None
    for btn in panel.findChildren(QPushButton):
        if btn.text() == "Copy OPX":
            btn_copy = btn
            break
            
    assert btn_copy is not None
    
    with patch("presentation.views.history.detail_panel.copy_to_clipboard", return_value=(True, "")) as mock_copy:
        qtbot.mouseClick(btn_copy, Qt.MouseButton.LeftButton)
        mock_copy.assert_called_once_with("Mock OPX content")
        assert ("OPX copied to clipboard!", False) in footer_messages

    # Test copy fail
    with patch("presentation.views.history.detail_panel.copy_to_clipboard", return_value=(False, "error")) as mock_copy:
        qtbot.mouseClick(btn_copy, Qt.MouseButton.LeftButton)
        assert ("Failed to copy OPX", True) in footer_messages


def test_history_detail_panel_reapply(qtbot):
    """Test click Re-apply kích hoạt callback."""
    reapplied_content = []
    panel = HistoryDetailPanel(
        on_reapply=lambda content: reapplied_content.append(content),
        on_footer_message=lambda msg, is_err: None
    )
    qtbot.addWidget(panel)
    
    e = make_mock_entry("uuid-1", datetime.now().isoformat())
    panel.show_entry(e)
    
    # Click Re-apply
    btn_reapply = None
    for btn in panel.findChildren(QPushButton):
        if btn.text() == "Re-apply":
            btn_reapply = btn
            break
    assert btn_reapply is not None
    
    qtbot.mouseClick(btn_reapply, Qt.MouseButton.LeftButton)
    assert reapplied_content == ["Mock OPX content"]


def test_history_detail_panel_delete_entry(qtbot, mock_history_service):
    """Test click Delete mở dialog confirm và gọi xóa."""
    deleted_callbacks = 0
    
    def on_deleted():
        nonlocal deleted_callbacks
        deleted_callbacks += 1

    panel = HistoryDetailPanel(
        on_entry_deleted=on_deleted,
        on_footer_message=lambda msg, is_err: None
    )
    qtbot.addWidget(panel)
    
    e = make_mock_entry("uuid-delete-test", datetime.now().isoformat())
    mock_history_service.entries = [e]
    panel.show_entry(e)
    
    btn_delete = None
    for btn in panel.findChildren(QPushButton):
        if btn.text() == "Delete":
            btn_delete = btn
            break
    assert btn_delete is not None
    
    # Mock QMessageBox để chọn Yes
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes) as mock_quest:
        qtbot.mouseClick(btn_delete, Qt.MouseButton.LeftButton)
        mock_quest.assert_called_once()
        assert mock_history_service.deleted_ids == ["uuid-delete-test"]
        assert deleted_callbacks == 1

    # Mock QMessageBox để chọn No -> không xóa
    mock_history_service.deleted_ids.clear()
    deleted_callbacks = 0
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No) as mock_quest:
        qtbot.mouseClick(btn_delete, Qt.MouseButton.LeftButton)
        assert mock_history_service.deleted_ids == []
        assert deleted_callbacks == 0

    # Test delete fail từ service
    mock_history_service.delete_result = False
    footer_messages = []
    panel._on_footer_message = lambda msg, is_err: footer_messages.append((msg, is_err))
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        qtbot.mouseClick(btn_delete, Qt.MouseButton.LeftButton)
        assert ("Failed to delete entry", True) in footer_messages


def test_history_detail_panel_show_more_files(qtbot):
    """Test phần Files Changed hiển thị nút Show More khi > 15 files."""
    panel = HistoryDetailPanel()
    qtbot.addWidget(panel)
    panel.show()
    
    # Tạo entry có 20 files
    actions = [f"MODIFY file{i}.py" for i in range(20)]
    e = make_mock_entry(
        "uuid-20",
        datetime.now().isoformat(),
        file_count=20,
        success_count=18,
        fail_count=2,
        action_summary=actions,
    )
    panel.show_entry(e)
    
    # Tìm nút Show 5 more files
    btn_more = None
    for btn in panel.findChildren(QPushButton):
        if "Show" in btn.text() and "more files" in btn.text():
            btn_more = btn
            break
            
    assert btn_more is not None
    assert btn_more.text() == "Show 5 more files"
    
    # Click show more -> text chuyển thành Collapse
    qtbot.mouseClick(btn_more, Qt.MouseButton.LeftButton)
    assert btn_more.text() == "Collapse"
    
    # Click collapse -> text trở lại Show 5 more files
    qtbot.mouseClick(btn_more, Qt.MouseButton.LeftButton)
    assert btn_more.text() == "Show 5 more files"


def test_history_detail_panel_show_more_errors(qtbot):
    """Test phần Errors hiển thị nút Show More khi > 3 errors."""
    panel = HistoryDetailPanel()
    qtbot.addWidget(panel)
    panel.show()
    
    errors = [f"file{i}.py: Error line {i}" for i in range(5)]
    e = make_mock_entry(
        "uuid-5-errors",
        datetime.now().isoformat(),
        file_count=5,
        success_count=0,
        fail_count=5,
        error_messages=errors,
    )
    panel.show_entry(e)
    
    # Tìm nút Show 2 more errors
    btn_more = None
    for btn in panel.findChildren(QPushButton):
        if "Show" in btn.text() and "more errors" in btn.text():
            btn_more = btn
            break
            
    assert btn_more is not None
    assert btn_more.text() == "Show 2 more errors..."
    
    # Click show more
    qtbot.mouseClick(btn_more, Qt.MouseButton.LeftButton)
    assert btn_more.text() == "Collapse errors"
    
    # Click collapse
    qtbot.mouseClick(btn_more, Qt.MouseButton.LeftButton)
    assert btn_more.text() == "Show 2 more errors..."


# ===========================================================================
# History View Qt (Composition Root) Tests
# ===========================================================================

def test_history_view_qt_flow(qtbot, mock_history_service):
    """Test luồng hoạt động tổng thể của HistoryViewQt."""
    # Thiết lập mock service dữ liệu ban đầu
    now_str = datetime.now().isoformat()
    e1 = make_mock_entry("uuid-1", now_str, file_count=2, success_count=2, fail_count=0)
    e2 = make_mock_entry("uuid-2", now_str, file_count=3, success_count=1, fail_count=2)
    mock_history_service.entries = [e1, e2]
    mock_history_service.stats = {
        "total_entries": 2,
        "total_operations": 5,
        "success_rate": 60.0
    }
    
    view = HistoryViewQt()
    qtbot.addWidget(view)
    
    # Kích hoạt view
    view.on_view_activated()
    qtbot.wait(50)
    
    # Thống kê header phải cập nhật
    assert "2 entries · 5 ops · 60% success" in view._stats_label.text()
    
    # List panel phải có 2 entries (+ 1 date header = 3 items)
    assert view._list_panel._entry_list.count() == 3
    
    # Chọn entry 1 ở list panel -> Detail panel phải cập nhật hiển thị e1
    item1 = view._list_panel._entry_list.item(1)
    view._list_panel._on_entry_clicked(item1)
    
    # Tìm nhãn "Entry #uuid-1" ở detail panel
    detail_labels = view._detail_panel.findChildren(QLabel)
    assert any("uuid-1" in l.text() for l in detail_labels)
    
    # Thử nút Refresh
    mock_history_service.stats = {
        "total_entries": 2,
        "total_operations": 5,
        "success_rate": 80.0 # đổi thông số để verify
    }
    btn_refresh = None
    for btn in view.findChildren(QPushButton):
        if btn.text() == "Refresh":
            btn_refresh = btn
            break
    assert btn_refresh is not None
    qtbot.mouseClick(btn_refresh, Qt.MouseButton.LeftButton)
    assert "80% success" in view._stats_label.text()
    
    # Xóa một entry từ detail panel
    btn_delete = None
    for btn in view._detail_panel.findChildren(QPushButton):
        if btn.text() == "Delete":
            btn_delete = btn
            break
    assert btn_delete is not None
    
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        qtbot.mouseClick(btn_delete, Qt.MouseButton.LeftButton)
        qtbot.wait(100)
        
    # e1 đã bị xóa, còn lại e2. Detail panel quay về empty state.
    assert len(mock_history_service.entries) == 1
    assert mock_history_service.entries[0].id == "uuid-2"
    
    empty_labels = view._detail_panel.findChildren(QLabel)
    assert any("Select an operation" in l.text() for l in empty_labels)
    
    # Thử click nút "Clear All"
    btn_clear = None
    for btn in view.findChildren(QPushButton):
        if btn.text() == "Clear All":
            btn_clear = btn
            break
    assert btn_clear is not None
    
    # Click "Clear All" nhưng chọn No -> không xóa
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No) as mock_quest:
        qtbot.mouseClick(btn_clear, Qt.MouseButton.LeftButton)
        mock_quest.assert_called_once()
        assert len(mock_history_service.entries) == 1
        
    # Click "Clear All" chọn Yes -> xóa sạch
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        qtbot.mouseClick(btn_clear, Qt.MouseButton.LeftButton)
        qtbot.wait(100)
    assert len(mock_history_service.entries) == 0
    assert view._list_panel._entry_list.count() == 1 # Chỉ còn dòng "No operations yet"


def test_history_view_qt_clear_all_failures(qtbot, mock_history_service):
    """Test khi Clear All thất bại từ phía service."""
    view = HistoryViewQt()
    qtbot.addWidget(view)
    
    mock_history_service.clear_result = False
    
    btn_clear = None
    for btn in view.findChildren(QPushButton):
        if btn.text() == "Clear All":
            btn_clear = btn
            break
            
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        qtbot.mouseClick(btn_clear, Qt.MouseButton.LeftButton)
        qtbot.wait(50)
        
    # Phải có thông báo lỗi ở footer
    assert view._footer_label.text() == "Failed to clear history"


def test_history_view_legacy_delegation(qtbot, mock_history_service):
    """Test các phương thức legacy delegation (dùng cho backward compatibility / tests cũ)."""
    reapplied = []
    view = HistoryViewQt(on_reapply=lambda x: reapplied.append(x))
    qtbot.addWidget(view)
    
    e = make_mock_entry("uuid-1", datetime.now().isoformat())
    mock_history_service.entries = [e]
    view._refresh()
    
    # Chọn entry
    view._on_entry_selected("uuid-1")
    
    # 1. Gọi _confirm_delete_entry trực tiếp trên view
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        view._confirm_delete_entry("uuid-1")
        assert mock_history_service.deleted_ids == ["uuid-1"]
        
    # 2. Gọi _copy_opx trực tiếp trên view
    with patch("presentation.views.history.detail_panel.copy_to_clipboard", return_value=(True, "")) as mock_copy:
        view._copy_opx(e)
        mock_copy.assert_called_once_with(e.opx_content)
        
    # 3. Gọi _reapply_opx trực tiếp trên view
    view._reapply_opx(e)
    assert reapplied == [e.opx_content]
