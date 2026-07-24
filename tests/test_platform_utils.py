import sys
from core import platform_utils as pu


def test_is_win_matches_sys_platform():
    assert pu.is_win() == sys.platform.startswith("win")


def test_platform_label_nonempty():
    assert isinstance(pu.platform_label(), str) and pu.platform_label()


def test_apply_dark_titlebar_noop_offwindows_returns_false():
    if not pu.is_win():
        assert pu.apply_dark_titlebar(12345) is False


def test_open_folder_missing_path_raises(tmp_path):
    import pytest
    with pytest.raises(FileNotFoundError):
        pu.open_folder(str(tmp_path / "nope"))
