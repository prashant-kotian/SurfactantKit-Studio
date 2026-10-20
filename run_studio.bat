@echo off
rem Start SurfactantKit Studio (local only, http://127.0.0.1:8770). Close this window to stop it.
cd /d "%~dp0"
if not exist .venv\Scripts\surfkit-studio.exe (
  echo SurfactantKit Studio is not installed yet. Run install_windows.bat first.
  pause & exit /b 1
)
.venv\Scripts\surfkit-studio.exe %*
