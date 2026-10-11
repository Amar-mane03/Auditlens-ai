@echo off
echo Running AuditLens Backend Tests...
cd /d "%~dp0Auditlens_AI"
".venv\Scripts\python.exe" -m unittest backend.tests.unit_tests

