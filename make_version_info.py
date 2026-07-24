"""version.py → PyInstaller Windows 버전 리소스(version_info.txt) 생성."""
from pathlib import Path
import version

_TEMPLATE = """VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({maj}, {min}, {pat}, 0),
    prodvers=({maj}, {min}, {pat}, 0),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', '{author}'),
      StringStruct('FileDescription', 'SnapStamp — Event Photobooth'),
      StringStruct('FileVersion', '{ver}'),
      StringStruct('InternalName', 'SnapStamp'),
      StringStruct('LegalCopyright', '(c) {year} {author}'),
      StringStruct('OriginalFilename', 'SnapStamp.exe'),
      StringStruct('ProductName', 'SnapStamp'),
      StringStruct('ProductVersion', '{ver}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def generate():
    maj, mn, pat = (version.VERSION.split(".") + ["0", "0", "0"])[:3]
    Path("version_info.txt").write_text(_TEMPLATE.format(
        maj=maj, min=mn, pat=pat, ver=version.VERSION,
        author=version.AUTHOR, year=version.YEAR), encoding="utf-8")


if __name__ == "__main__":
    generate()
    print("wrote version_info.txt")
