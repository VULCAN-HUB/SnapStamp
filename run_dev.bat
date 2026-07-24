@echo off
REM SnapStamp 개발 실행(오너 수동 QA). venv 있으면 사용.
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe main.py
) else (
  python main.py
)
