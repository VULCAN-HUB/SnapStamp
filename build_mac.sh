#!/usr/bin/env bash
set -e
# SnapStamp macOS 빌드(실기 필요). 서명/공증은 MAC_BUILD.md 참조.
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python make_version_info.py || true
python build_icon.py
# .icns는 assets/snapstamp.png(1024)에서 iconutil 또는 Pillow로 생성(MAC_BUILD.md 참조)
pyinstaller --noconfirm build.spec
echo "빌드 산출: dist/SnapStamp.app — codesign/notarize는 MAC_BUILD.md 참조"
