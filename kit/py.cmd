@echo off
rem Runs Python from the Studio's engine (ComfyUI's embedded Python), e.g.:  kit\py.cmd kit\studio\gen.py status
for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "(Get-Content -Raw '%~dp0..\my\settings.json' | ConvertFrom-Json).engine_dir"`) do set "STUDIO_ENGINE=%%i"
if not exist "%STUDIO_ENGINE%\python_embeded\python.exe" (
  echo The Studio is not set up yet: run kit\setup.ps1 first.
  exit /b 2
)
"%STUDIO_ENGINE%\python_embeded\python.exe" -s %*
