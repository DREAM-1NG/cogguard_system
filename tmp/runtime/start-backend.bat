@echo off
cd /d G:\CISCN\cogguard_system\new-system\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
