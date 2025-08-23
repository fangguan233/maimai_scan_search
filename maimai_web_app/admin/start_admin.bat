@echo off
echo Starting Admin Panel Server...

REM 激活您指定的 Conda 环境
echo Activating Conda environment: newyolo
call conda activate newyolo

REM 切换到项目根目录
cd /d %~dp0..

echo Loading environment variables from .env file...

REM Load environment variables from .env file
for /f "tokens=1,* delims==" %%a in ('findstr /R /V "^#" .env') do (
    set "%%a=%%b"
)
REM Set default port if not defined in .env
if not defined ADMIN_PORT (
    set "ADMIN_PORT=25565"
)

echo Starting Waitress server for the admin panel on port %ADMIN_PORT%...
waitress-serve --host 0.0.0.0 --port=%ADMIN_PORT% admin.app:app
