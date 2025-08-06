@echo off
echo Starting Admin Panel Server...

REM 激活您指定的 Conda 环境
echo Activating Conda environment: newyolo
call conda activate newyolo

REM 切换到项目根目录
cd /d %~dp0..

echo Starting Waitress server for the admin panel...
waitress-serve --host 0.0.0.0 --port 8081 admin.app:app
