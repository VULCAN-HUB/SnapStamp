from pathlib import Path


def test_build_spec_has_platform_branch():
    spec = Path("build.spec").read_text(encoding="utf-8")
    assert "darwin" in spec
    assert "snapstamp.ico" in spec
    assert "version_info.txt" in spec
    assert "assets" in spec


def test_entitlements_has_camera():
    ent = Path("entitlements.mac.plist").read_text(encoding="utf-8")
    assert "com.apple.security.device.camera" in ent
    assert "disable-library-validation" in ent


def test_mac_build_doc_exists():
    doc = Path("docs/MAC_BUILD.md").read_text(encoding="utf-8")
    assert "notarytool" in doc or "공증" in doc
    assert "NSCameraUsageDescription" in doc
