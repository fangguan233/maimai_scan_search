@echo off
chcp 65001 > nul
echo.
echo ==================================================
echo      Maimai DX Score Analyzer - Server Launcher
echo ==================================================
echo.
echo Activating Conda environment 'newyolo'...
call conda activate newyolo

REM Check if conda activation was successful
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Failed to activate Conda environment 'newyolo'.
    echo Please make sure Conda is installed and the 'newyolo' environment exists.
    echo.
    pause
    exit /b
)

echo.
echo Conda environment activated successfully.
echo Launching server with Waitress...
echo.
echo  - Local access: http://localhost:5000
echo  - Network access: http://[Your-IP-Address]:5000
echo.
echo Server is running. Do not close this window.
echo Press Ctrl+C to stop the server.
echo.

waitress-serve --host=0.0.0.0 --port=5000 app:app

echo.
echo Server has been stopped. Press any key to exit...
pause > nul
