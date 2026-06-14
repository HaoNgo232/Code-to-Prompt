# Design Spec: Copy Mode Consolidation

Hợp nhất 5 copy modes hiện tại thành 3 core modes + 2 sub-options.

## 1. Goal Description

Hiện tại, Synapse Desktop có nhiều cách khác nhau để sao chép context (Copy Context, Compress/Smart Context, Copy + Search/Replace, Git Diff, Tree Map). Để đơn giản hóa kiến trúc và nâng cao tính mở rộng, tài liệu này thiết kế một data model mới `CopyConfig` chứa:
- `CopyMode` (FULL, SMART, APPLY)
- `include_git_diff` (Git Diff cũ thành sub-option)
- `tree_map_only` (Tree Map cũ thành sub-option)

## 2. Proposed Changes

### 2.1 [NEW] [copy_mode.py](file:///home/hao/Desktop/labs/Synapse-Desktop/domain/prompt/copy_mode.py)

Tạo file mới định nghĩa `CopyMode` (Enum) và `CopyConfig` (dataclass).

### 2.2 [MODIFY] [prompt_build_service.py](file:///home/hao/Desktop/labs/Synapse-Desktop/application/services/prompt_build_service.py)

Cập nhật `PromptBuildService` để hỗ trợ `CopyConfig`.
- Map `CopyMode` sang định dạng output thích hợp (XML/Plain).
- Xử lý `tree_map_only` để chỉ kết xuất Tree Map.
- Xử lý `include_git_diff` để tích hợp Git changes.

### 2.3 [MODIFY] [copy_action_controller.py](file:///home/hao/Desktop/labs/Synapse-Desktop/presentation/views/context/copy_action_controller.py)

Cập nhật `CopyActionController` để sử dụng `CopyConfig` khi gọi prompt builder, tạo cache fingerprint, và xử lý kết quả copy.

## 3. Verification & TDD Plan

### 3.1 TDD Tests
Tạo file `tests/domain/prompt/test_copy_mode.py` với các test cases:
- `test_copy_config_serializes_to_dict`
- `test_legacy_compress_string_loads_as_smart`
- `test_legacy_strings_all_map_correctly`
- `test_tree_map_only_overrides_mode`
- `test_all_modes_have_display_name`
- `test_invalid_mode_string_raises_value_error`

### 3.2 Automated Tests Command
```bash
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/domain/prompt/test_copy_mode.py -v
env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v
```
