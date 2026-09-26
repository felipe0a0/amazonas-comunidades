@echo off
cd /d %~dp0
set AI_PROVIDER=mock
set TRANSCRIPTION_PROVIDER=mock
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe -m uvicorn api:app --reload --host 0.0.0.0 --port 8000
) else (
  python -m uvicorn api:app --reload --host 0.0.0.0 --port 8000
)
pause
