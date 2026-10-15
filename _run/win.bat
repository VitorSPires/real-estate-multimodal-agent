@echo off
REM Windows one-click: double-click to start the API + frontend in dev mode.
REM The real logic lives in _run\lib\dev.ps1 (do not run that file directly).
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0lib\dev.ps1"
