@echo off
echo Running AuditLens Backend Tests...
".venv\Scripts\python.exe" -m unittest backend.tests.unit_tests

