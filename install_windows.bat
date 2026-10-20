@echo off
rem SurfactantKit Studio installer for Windows. Needs Python 3.10 or newer (python.org or the Microsoft Store).
rem Creates a private environment in .venv next to this file; nothing is installed system-wide.
rem SurfactantKit comes from GitHub by default; set SURFACTANTKIT_SRC to a local copy to use that instead.
setlocal
cd /d "%~dp0"

where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>nul
if errorlevel 1 (
  echo Python 3.10 or newer was not found. Install it from https://www.python.org/downloads/ and run this again.
  pause & exit /b 1
)

if not exist .venv (
  echo Creating the environment in .venv ...
  %PY% -m venv .venv || (echo Could not create the environment. & pause & exit /b 1)
)
set "VPY=.venv\Scripts\python.exe"
%VPY% -m pip install --upgrade pip >nul

if defined SURFACTANTKIT_SRC (
  echo Installing SurfactantKit from %SURFACTANTKIT_SRC% ...
  %VPY% -m pip install -e "%SURFACTANTKIT_SRC%[calc]" || goto :fail
) else (
  echo Installing SurfactantKit from GitHub ...
  %VPY% -m pip install "surfactantkit[calc] @ git+https://github.com/prashant-kotian/Surfactant-Toolkit.git" || goto :fail
)
echo Installing SurfactantKit Studio ...
%VPY% -m pip install -e . || goto :fail

echo.
echo Installed. Start it with run_studio.bat (it opens http://127.0.0.1:8770 in your browser).
echo Optional local AI chat: install Ollama from https://ollama.com and run:  ollama pull qwen3:1.7b
pause
exit /b 0

:fail
echo Installation failed; see the messages above.
pause
exit /b 1
