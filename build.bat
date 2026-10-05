@echo off
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 exit /b 1
.venv\Scripts\python -m pip install -r requirements-build.txt
if errorlevel 1 exit /b 1
.venv\Scripts\python -m PyInstaller --noconfirm --clean --onefile --windowed --name DiskLens app.py
