@echo off
REM SnapStamp Windows 빌드 → _빌드파일 배치 (실제 작업은 build_win.ps1)
REM   기본     : onedir ZIP (배포용, 백신 오탐 트리거인 자가추출 없음)
REM   -OneFile : 단일 exe만
REM   -Both    : 둘 다
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_win.ps1" %*
