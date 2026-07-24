from PyQt5.QtWidgets import QWidget, QDialog
from ui import theme
import version


def test_make_header_is_widget(qapp):
    parent = QWidget()
    h = theme.make_header(parent)
    assert isinstance(h, QWidget)
    assert h.height() == 64


def test_about_contains_brand_and_version(qapp):
    dlg = theme.show_about(None)
    assert isinstance(dlg, QDialog)
    texts = _all_text(dlg)
    assert "Unknown" in texts
    assert "2026" in texts
    assert version.RELEASE_LABEL in texts
    assert "@unknown8563" in texts


def _all_text(w):
    from PyQt5.QtWidgets import QLabel
    return "\n".join(lbl.text() for lbl in w.findChildren(QLabel))
