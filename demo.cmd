@echo off
cd /d "%~dp0"
python demo.py %*
if errorlevel 1 echo. & echo Demo failed. Confirm that Python 3.12 or later is installed.
echo.
pause
