# SnapStamp macOS 빌드 런북

## 사전
- macOS 실기(PyInstaller 크로스컴파일 불가). Python 3.12, Xcode CLT.
- `.icns` 생성: `assets/snapstamp.png`(1024)에서 `iconutil`(iconset) 또는 Pillow로 `assets/snapstamp.icns` 생성.

## 빌드
```bash
bash build_mac.sh   # dist/SnapStamp.app 산출
```

## 카메라 권한(필수)
- `Info.plist`에 `NSCameraUsageDescription` 포함(build.spec에서 주입).
- Hardened Runtime + codesign 경로에서는 `entitlements.mac.plist`(`com.apple.security.device.camera` + `com.apple.security.cs.disable-library-validation`) 필요.

## 서명/공증(정식 배포)
- Apple Developer($99/년). ⚠️ 실명·Apple ID는 코드/리포에 하드코딩 금지 — 빌드 시점 로컬 입력.
```bash
codesign --deep --force --options runtime \
  --entitlements entitlements.mac.plist \
  --sign "Developer ID Application: <NAME>" dist/SnapStamp.app
xcrun notarytool submit dist/SnapStamp.app --apple-id <ID> --team-id <TEAM> --wait
xcrun stapler staple dist/SnapStamp.app
```
- 미서명 .app은 Gatekeeper 경고 → 내부 테스트는 우클릭→열기.
