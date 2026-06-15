# Thiết kế PatchDetectionService

Tài liệu này mô tả chi tiết thiết kế kỹ thuật cho `PatchDetectionService` trong codebase Synapse Desktop. Service này chịu trách nhiệm nhận diện xem một phản hồi thô từ AI (raw AI response text) có chứa các patch thay đổi file hay không, và danh sách các file nào sẽ bị ảnh hưởng.

---

## 1. Mục tiêu (Goals)
- Nhận diện chính xác sự hiện diện của các patch thay đổi file từ AI response text (hỗ trợ cả hai định dạng OPX và Search/Replace).
- Trích xuất danh sách các `FileAction` và lọc danh sách các file bị ảnh hưởng (`affected_files`) dưới dạng đường dẫn tương đối (relative path), độc nhất (unique) và giữ nguyên thứ tự xuất hiện gốc.
- Đảm bảo hiệu năng xử lý văn bản lớn (100KB) dưới 500ms.
- Hoạt động ổn định, không crash khi gặp đầu vào đặc biệt như chuỗi rỗng (`""`), `None`, hoặc các giá trị `None-like` (`"None"`, `"null"`).
- Tuân thủ quy tắc type hints nghiêm ngặt (Pyright strict mode) và viết comment giải thích bằng tiếng Việt có dấu.

---

## 2. Kiến trúc & Vị trí File
Service sẽ được đặt tại lớp Domain thuộc cấu trúc DDD của dự án:
- **Service**: `domain/prompt/patch_detection_service.py`
- **Unit Tests**: `tests/domain/prompt/test_patch_detection_service.py`

---

## 3. Thiết kế Chi tiết (Detailed Design)

### 3.1. Các Lớp Dữ liệu (Data Classes)

```python
from dataclasses import dataclass, field
from typing import List, Optional
from domain.prompt.opx_parser import FileAction

@dataclass
class PatchDetectionResult:
    """
    Kết quả phân tích nhận diện patch từ AI response.

    Attributes:
        has_patches (bool): True nếu có ít nhất một file action hợp lệ được phân tích thành công.
        file_actions (List[FileAction]): Danh sách các file action được phân tích từ opx_parser.
        parse_errors (List[str]): Danh sách các lỗi cú pháp xảy ra khi cố gắng parse patch.
        affected_files (List[str]): Danh sách các đường dẫn tương đối, độc nhất của các file bị ảnh hưởng.
    """
    has_patches: bool
    file_actions: List[FileAction] = field(default_factory=list)
    parse_errors: List[str] = field(default_factory=list)
    affected_files: List[str] = field(default_factory=list)
```

### 3.2. Lớp PatchDetectionService

```python
import os
from typing import Optional, Set
from domain.prompt.opx_parser import parse_any_response, _looks_like_opx, _looks_like_search_replace

class PatchDetectionService:
    """
    Service phát hiện và trích xuất thông tin patch từ AI response text.
    """

    def __init__(self, workspace_root: Optional[str] = None) -> None:
        """
        Khởi tạo service với thư mục gốc workspace tùy chọn.

        Args:
            workspace_root (Optional[str]): Thư mục gốc của workspace dùng để tính toán relative path.
        """
        self.workspace_root = workspace_root

    def detect(self, raw_text: str) -> PatchDetectionResult:
        """
        Phát hiện và parse các patch từ text thô của AI response.

        Hàm này sử dụng trực tiếp logic của opx_parser để nhận dạng và phân tích
        cú pháp định dạng OPX hoặc Search/Replace.

        Args:
            raw_text (str): Phản hồi thô từ AI.

        Returns:
            PatchDetectionResult: Kết quả phân tích chứa thông tin patch và lỗi cú pháp nếu có.
        """
        # 1. Guard clauses cho đầu vào trống hoặc None-like
        if raw_text is None:
            return PatchDetectionResult(has_patches=False)

        if not isinstance(raw_text, str):
            return PatchDetectionResult(has_patches=False)

        cleaned = raw_text.strip()
        if not cleaned or cleaned.lower() in ("none", "null"):
            return PatchDetectionResult(has_patches=False)

        # 2. Kiểm tra xem text có chứa cấu trúc patch hay không (tránh coi chat thường là lỗi parse)
        is_opx = _looks_like_opx(cleaned)
        is_sr = _looks_like_search_replace(cleaned)

        if not is_opx and not is_sr:
            # Hội thoại thông thường, không có ý định patch -> trả về kết quả trống, không có lỗi
            return PatchDetectionResult(has_patches=False)

        # 3. Tiến hành phân tích cú pháp bằng opx_parser
        parse_result = parse_any_response(cleaned)
        
        file_actions = parse_result.file_actions
        has_patches = len(file_actions) > 0
        parse_errors = parse_result.errors

        # 4. Trích xuất affected_files (relative path, unique, giữ nguyên thứ tự)
        affected_files: List[str] = []
        seen_paths: Set[str] = set()

        for action in file_actions:
            path = action.path
            
            # Chuẩn hóa path thành relative path nếu là absolute path
            if os.path.isabs(path):
                root = self.workspace_root or os.getcwd()
                try:
                    rel_path = os.path.relpath(path, root)
                except Exception:
                    rel_path = path
            else:
                rel_path = path

            # Lọc trùng lặp nhưng giữ nguyên thứ tự xuất hiện
            if rel_path not in seen_paths:
                seen_paths.add(rel_path)
                affected_files.append(rel_path)

        return PatchDetectionResult(
            has_patches=has_patches,
            file_actions=file_actions,
            parse_errors=parse_errors,
            affected_files=affected_files
        )
```

---

## 4. Kế hoạch Kiểm thử (Verification Plan)

Chúng ta sẽ sử dụng pytest để chạy các test case sau nhằm đảm bảo tính đúng đắn và hiệu năng:

1.  **`test_detects_search_replace_blocks`**: Gửi một Search/Replace block hợp lệ và kiểm tra xem `has_patches` có phải là `True`, `file_actions` được map đúng, và `affected_files` được trích xuất chính xác.
2.  **`test_detects_opx_blocks`**: Gửi một OPX block hợp lệ và kiểm tra kết quả tương tự.
3.  **`test_no_patches_returns_false`**: Gửi một văn bản hội thoại thông thường (ví dụ: *"Chào bạn, hôm nay tôi có thể giúp gì cho bạn?"*) và kiểm tra xem `has_patches` có là `False` và `parse_errors` có rỗng hay không.
4.  **`test_affected_files_populated_correctly`**: Gửi patch chứa đường dẫn tuyệt đối (hoặc nhiều hành động trùng lặp cho cùng một file) để đảm bảo `affected_files` là đường dẫn tương đối, độc nhất và giữ nguyên thứ tự.
5.  **`test_parse_errors_captured`**: Gửi patch bị lỗi cú pháp (ví dụ: `<edit>` thiếu thẻ đóng `</edit>`) và kiểm tra xem `parse_errors` có ghi nhận lỗi đó.
6.  **`test_performance_100kb_under_500ms`**: Tạo dữ liệu giả lập có kích thước 100KB chứa patch và đo thời gian xử lý của `detect()`, yêu cầu thời gian thực thi `< 500ms`.
7.  **`test_empty_string_input_no_crash`**: Gửi chuỗi rỗng `""` và kiểm tra không có crash.
8.  **`test_none_like_input_handled`**: Gửi `None` (hoặc `"None"`, `"null"`) và kiểm tra không có crash.
