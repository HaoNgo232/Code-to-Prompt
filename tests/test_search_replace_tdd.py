"""
Các ca kiểm thử TDD cho các tính năng mở rộng của bộ phân tích Search/Replace (Aider-style),
bao gồm các thao tác DELETE và RENAME.
"""

from domain.prompt.opx_parser import (
    parse_search_replace_response,
    parse_any_response,
)


class TestSearchReplaceTdd:
    """Các trường hợp kiểm thử cho tính năng DELETE và RENAME mở rộng trong Search/Replace parser"""

    def test_parse_delete_simple(self):
        """Kiểm tra việc parse cú pháp DELETE đơn giản không có dấu '='"""
        text = """
<<<<<<< DELETE tests/legacy/old_file.py
>>>>>>> DELETE
        """
        result = parse_search_replace_response(text)
        assert len(result.errors) == 0
        assert len(result.file_actions) == 1

        action = result.file_actions[0]
        assert action.path == "tests/legacy/old_file.py"
        assert action.action == "delete"
        assert len(action.changes) == 0

    def test_parse_delete_with_equals(self):
        """Kiểm tra việc parse cú pháp DELETE có chứa dấu '=' phân tách"""
        text = """
<<<<<<< DELETE tests/legacy/old_file.py
=======
>>>>>>> DELETE
        """
        result = parse_search_replace_response(text)
        assert len(result.errors) == 0
        assert len(result.file_actions) == 1

        action = result.file_actions[0]
        assert action.path == "tests/legacy/old_file.py"
        assert action.action == "delete"

    def test_parse_rename(self):
        """Kiểm tra việc parse cú pháp RENAME (đổi tên/di chuyển tệp)"""
        text = """
<<<<<<< RENAME src/lib/old_name.ts
=======
src/lib/new_name.ts
>>>>>>> RENAME
        """
        result = parse_search_replace_response(text)
        assert len(result.errors) == 0
        assert len(result.file_actions) == 1

        action = result.file_actions[0]
        assert action.path == "src/lib/old_name.ts"
        assert action.action == "rename"
        assert action.new_path == "src/lib/new_name.ts"

    def test_parse_mixed_operations(self):
        """Kiểm tra việc parse đồng thời nhiều thao tác khác nhau (modify, delete, rename, create)"""
        text = """
<<<<<<< SEARCH src/hello.py
def old(): pass
=======
def new(): pass
>>>>>>> REPLACE

<<<<<<< DELETE tests/to_remove.txt
>>>>>>> DELETE

<<<<<<< RENAME old_dir/file.py
=======
new_dir/file.py
>>>>>>> RENAME

<<<<<<< SEARCH new_file.txt
=======
Hello World
>>>>>>> REPLACE
        """
        result = parse_search_replace_response(text)
        assert len(result.errors) == 0
        assert len(result.file_actions) == 4

        actions = {a.path: a for a in result.file_actions}

        assert "src/hello.py" in actions
        assert actions["src/hello.py"].action == "modify"

        assert "tests/to_remove.txt" in actions
        assert actions["tests/to_remove.txt"].action == "delete"

        assert "old_dir/file.py" in actions
        assert actions["old_dir/file.py"].action == "rename"
        assert actions["old_dir/file.py"].new_path == "new_dir/file.py"

        assert "new_file.txt" in actions
        assert actions["new_file.txt"].action == "create"

    def test_parse_any_response_detection(self):
        """Kiểm tra hàm parse_any_response tự động nhận diện định dạng Search/Replace khi có DELETE/RENAME"""
        text_delete = """
<<<<<<< DELETE tests/legacy/old_file.py
>>>>>>> DELETE
        """
        result = parse_any_response(text_delete)
        assert len(result.errors) == 0
        assert len(result.file_actions) == 1
        assert result.file_actions[0].action == "delete"

    def test_parse_search_replace_memory(self):
        """Kiểm tra trích xuất synapse_memory từ phản hồi Search/Replace"""
        text = """
<<<<<<< DELETE tests/legacy/old_file.py
>>>>>>> DELETE

<synapse_memory>
Đây là bộ nhớ liên tục quan trọng.
</synapse_memory>
        """
        result = parse_search_replace_response(text)
        assert len(result.errors) == 0
        assert result.memory_block == "Đây là bộ nhớ liên tục quan trọng."

    def test_parse_multiple_patches_same_file_wrapped_in_xml_block(self):
        """Kiểm tra parse nhiều patch của cùng một file được bọc trong markdown xml code block"""
        text = """
Dưới đây là các thay đổi:

```xml
<<<<<<< SEARCH src/hello.py
def old_1():
    print("old 1")
=======
def new_1():
    print("new 1")
>>>>>>> REPLACE

<<<<<<< SEARCH src/hello.py
def old_2():
    print("old 2")
=======
def new_2():
    print("new 2")
>>>>>>> REPLACE
```
        """
        result = parse_any_response(text)
        assert len(result.errors) == 0
        assert len(result.file_actions) == 1
        action = result.file_actions[0]
        assert action.path == "src/hello.py"
        assert action.action == "modify"
        assert len(action.changes) == 2
        assert action.changes[0].search == 'def old_1():\n    print("old 1")'
        assert action.changes[0].content == 'def new_1():\n    print("new 1")'
        assert action.changes[1].search == 'def old_2():\n    print("old 2")'
        assert action.changes[1].content == 'def new_2():\n    print("new 2")'

    def test_parse_multiple_patches_different_files_wrapped_in_xml_block(self):
        """Kiểm tra parse nhiều patch của các file khác nhau được bọc trong markdown xml code block"""
        text = """
Các tệp cần cập nhật:

```xml
<<<<<<< SEARCH src/a.py
a = 1
=======
a = 2
>>>>>>> REPLACE

<<<<<<< SEARCH src/b.py
b = 3
=======
b = 4
>>>>>>> REPLACE
```
        """
        result = parse_any_response(text)
        assert len(result.errors) == 0
        assert len(result.file_actions) == 2
        actions = {a.path: a for a in result.file_actions}

        assert "src/a.py" in actions
        assert actions["src/a.py"].changes[0].search == "a = 1"
        assert actions["src/a.py"].changes[0].content == "a = 2"

        assert "src/b.py" in actions
        assert actions["src/b.py"].changes[0].search == "b = 3"
        assert actions["src/b.py"].changes[0].content == "b = 4"
