@echo off
echo Starting AuditLens Backend API...
if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Please create it first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" unified_backend.py
