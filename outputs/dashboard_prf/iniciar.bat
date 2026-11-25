@echo off
cd /d "%~dp0"
set "PYTHON_PROJETO=..\..\.venv\Scripts\python.exe"
if not exist "%PYTHON_PROJETO%" py -3.12 -m venv ..\..\.venv
if errorlevel 1 exit /b
"%PYTHON_PROJETO%" -c "import streamlit, pandas, plotly" >nul 2>&1
if errorlevel 1 "%PYTHON_PROJETO%" -m pip install -r requirements.txt
if errorlevel 1 exit /b
if not defined PROEX_DASHBOARD_PORT set "PROEX_DASHBOARD_PORT=8501"
"%PYTHON_PROJETO%" -m streamlit run app.py --server.address 127.0.0.1 --server.port %PROEX_DASHBOARD_PORT% --server.headless true
