@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto usepython
py -3 epicor_discover.py --config operis-scan-config.json
set "SCAN_EXIT=%ERRORLEVEL%"
goto done
:usepython
where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.10 or newer is required. Install Python from python.org, then try again.
  pause
  exit /b 1
)
python epicor_discover.py --config operis-scan-config.json
set "SCAN_EXIT=%ERRORLEVEL%"
:done
if not "%SCAN_EXIT%"=="0" echo Scan failed. No new successful package is available from this attempt.
pause
exit /b %SCAN_EXIT%
