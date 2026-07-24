# -*- mode: python ; coding: utf-8 -*-
import os
import sys
is_mac = sys.platform == "darwin"
# 배포 형태 스위치. 기본 = onedir(폴더 배포).
# ⚠️ onefile은 실행할 때마다 128MB를 임시폴더에 자가추출한다. 이 동작 자체가 백신
#    휴리스틱의 대표 트리거이고, 기동도 느리다(실측 3.95s vs onedir 1.36s, 2.9배).
#    따라서 배포 기본형은 onedir이고, onefile은 SNAPSTAMP_ONEFILE=1 일 때만 만든다.
ONEDIR = os.environ.get("SNAPSTAMP_ONEFILE", "0") != "1"

from PyInstaller.utils.hooks import collect_data_files
datas = [("assets", "assets"), ("config.default.json", ".")]
# imageio-ffmpeg가 번들한 ffmpeg 실행파일을 exe에 포함(고해상도 카메라 캡처)
datas += collect_data_files("imageio_ffmpeg")
hiddenimports = ["cv2", "PyQt5.sip", "PyQt5.QtSvg", "imageio_ffmpeg"]
# v2: EDSDK 바이너리는 아래 binaries=[('assets/EDSDK.dll','.')] 형태로 추가
binaries = []

a = Analysis(["main.py"], pathex=[], binaries=binaries, datas=datas,
             hiddenimports=hiddenimports, hookspath=[], runtime_hooks=[],
             excludes=[], noarchive=False)
pyz = PYZ(a.pure)

if is_mac:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="SnapStamp",
              console=False, icon="assets/snapstamp.icns")
    coll = COLLECT(exe, a.binaries, a.datas, name="SnapStamp")
    app = BUNDLE(coll, name="SnapStamp.app", icon="assets/snapstamp.icns",
                 bundle_identifier="com.unknown8563.snapstamp",
                 info_plist={
                     "NSCameraUsageDescription": "이벤트 포토부스 촬영을 위해 카메라를 사용합니다.",
                     "NSHighResolutionCapable": True})
else:
    # ⚠️ UPX 압축은 백신 오탐(False Positive)의 대표 원인이므로 명시적으로 끈다.
    #    (현재 빌드 PC엔 upx가 없어 미적용이지만, 다른 PC에서 자동 적용되는 것을 차단)
    if ONEDIR:
        # 폴더 배포: 자가추출이 없어 오탐이 크게 줄고 실행이 빠르다(대신 폴더 통째 배포)
        exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="SnapStamp",
                  console=False, upx=False, icon="assets/snapstamp.ico",
                  version="version_info.txt")
        coll = COLLECT(exe, a.binaries, a.datas, upx=False, name="SnapStamp")
    else:
        # onefile: a.binaries+a.datas를 EXE에 직접 포함(COLLECT 없음)하면 단일 파일 산출
        exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="SnapStamp",
                  console=False, upx=False, icon="assets/snapstamp.ico",
                  version="version_info.txt")
