from shared.utils.file_utils import is_binary_file


def test_is_binary_file(tmp_path):
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("Hello World", encoding="utf-8")
    assert not is_binary_file(txt_file)

    bin_file = tmp_path / "test.bin"
    bin_file.write_bytes(b"\x00\x01\x02\x03")
    assert is_binary_file(bin_file)
