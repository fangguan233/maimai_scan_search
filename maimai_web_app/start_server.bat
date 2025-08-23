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
echo.
echo Loading environment variables from .env file...

REM Load environment variables from .env file
for /f "tokens=1,* delims==" %%a in ('findstr /R /V "^#" .env') do (
    set "%%a=%%b"
)
REM Set default port if not defined in .env
if not defined APP_PORT (
    set "APP_PORT=25564"
)

echo Launching server with Waitress on port %APP_PORT%...
echo.
echo  - Local access: http://localhost:%APP_PORT%
echo  - Network access is available on your local network.
echo.
echo Server is running. Do not close this window.
echo Press Ctrl+C to stop the server.
echo.

waitress-serve --host=0.0.0.0 --port=%APP_PORT% app:app

echo.
echo Server has been stopped. Press any key to exit...
pause > nul
