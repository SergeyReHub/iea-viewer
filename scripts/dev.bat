@echo off
setlocal
cd /d "%~dp0.."

if not exist ".env" (
  echo Copy .env.example to .env and set IEA_DB_URL
  copy /Y .env.example .env >nul
)

echo Starting backend on http://localhost:8010 ...
start "iea-viewer-v2-backend" cmd /k "cd /d %CD%\backend && set SOURCES_CONFIG=..\config\sources.yaml && python -m uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload"

timeout /t 3 /nobreak >nul

echo Starting frontend on http://localhost:5180 ...
cd frontend
if not exist node_modules (
  call npm install
)
call npm run dev
