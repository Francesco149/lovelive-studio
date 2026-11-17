@echo off
rem Double-click to start the Love Live Studio (the desktop shortcut runs this).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0kit\start.ps1" %*
if errorlevel 1 pause
