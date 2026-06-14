# Thiết kế: Cấu trúc lại Template Registry và loại bỏ Tier Logic

Tài liệu thiết kế chi tiết cho việc tinh chỉnh template registry trong `domain/prompt/template_manager.py` chỉ để lộ ra 7 templates mặc định và loại bỏ logic phân biệt tier (lite/pro).

## Mục tiêu
- Rút gọn danh sách template mặc định từ 16 xuống còn 7 templates thiết yếu.
- Loại bỏ hoàn toàn hệ thống tier (lite/pro) trong core template loader.
- Đảm bảo tính tương thích ngược: nếu có caller truyền tham số `tier` vào `load_template()`, hệ thống sẽ bỏ qua (ignore) mà không crash.
- Đảm bảo tất cả custom templates của người dùng không bị ảnh hưởng.

## Thay đổi chi tiết

### 1. File [template_manager.py](file:///home/hao/Desktop/labs/Synapse-Desktop/domain/prompt/template_manager.py)
- **BuiltInTemplateProvider._registry**:
  Chỉ giữ lại 7 template sau:
  - `bug_hunter`
  - `security_auditor`
  - `architecture_reviewer`
  - `code_explainer`
  - `test_writer`
  - `performance_optimizer`
  - `doc_generator`
  Xóa tất cả các template khác.

- **Hàm `_get_template_tier()`**:
  Xóa hoàn toàn hàm này.

- **Biến `_LITE_OUTPUT_FORMAT_PATH`**:
  Xóa hoàn toàn biến này.

- **Hàm `_get_output_format_only()`**:
  Cấu trúc lại để luôn đọc từ `_OUTPUT_FORMAT_PATH`, bỏ logic phân biệt tier.

- **Hàm `BuiltInTemplateProvider.load_template(self, template_id: str, *args, **kwargs)`**:
  Sửa đổi signature nhận `*args, **kwargs` (hoặc tham số `tier: str = None` hiển thị rõ ràng và ignore nó) để tránh crash. Luôn đọc từ `pro_path` (`_TEMPLATES_DIR / f"{template_id}.md"`).

- **Hàm `load_template(template_id: str, opx_mode: bool = False, tier: str = None, *args, **kwargs)`**:
  Cập nhật hàm ở module level để nhận và bỏ qua tham số `tier`.

### 2. Các Callers cần cập nhật
Chúng ta sẽ dùng grep để tìm tất cả các nơi gọi:
- `load_template`
- `list_templates`
- `get_template_info`
- `template_tier`
Và cập nhật lại chúng để không truyền `tier` (hoặc loại bỏ cấu hình tier liên quan).

### 3. Kế hoạch Kiểm thử (TDD)
Tạo file test mới tại `tests/domain/prompt/test_template_registry.py` chứa các test case sau:
- `test_list_returns_exactly_7_builtin`: Kiểm tra xem danh sách built-in template trả về chính xác 7 cái.
- `test_load_template_no_longer_needs_tier`: Kiểm tra xem việc gọi `load_template` có truyền `tier` hay không truyền `tier` đều load cùng một nội dung pro.
- `test_custom_templates_unaffected`: Đảm bảo các custom template vẫn hoạt động bình thường.
- `test_removed_template_ids_raise_key_error`: Đảm bảo các template đã bị xóa sẽ gây ra lỗi `KeyError`.
- `test_lite_dir_not_loaded`: Kiểm tra thư mục `templates/lite/` không được load.
- `test_all_7_templates_have_content`: Đảm bảo cả 7 template đều có nội dung hợp lệ và có thể load thành công.

## Tự đánh giá (Self-Review)
- Không có placeholder.
- Thiết kế rõ ràng, nhất quán với yêu cầu của người dùng.
