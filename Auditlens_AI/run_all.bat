@echo off
echo ========================================================
echo Starting AuditLens Enterprise System (Backend + Frontend)
echo ========================================================

start "AuditLens Backend API" cmd /k "run_backend.bat"
start "AuditLens Frontend UI" cmd /k "run_frontend.bat"

echo.
echo Both servers are launching in separate windows:
echo - Backend: http://127.0.0.1:5000
echo - Frontend: http://localhost:5173
echo.

