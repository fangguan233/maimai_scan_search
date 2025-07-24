@echo off
echo Starting the Maimai Song-Scanner server...

REM --- Conda 环境激活 ---
echo Activating Conda environment 'yolov8'...
CALL conda activate yolov8

REM 检查 Conda 环境是否激活成功
IF %CONDA_DEFAULT_ENV% NEQ yolov8 (
    echo Failed to activate Conda environment 'yolov8'.
    echo Please make sure Conda is installed and the 'yolov8' environment exists.
    pause
    exit /b
)

echo Conda environment activated successfully.

REM --- 启动 Flask 服务器 ---
echo Starting Flask server...
REM 使用 python  来禁用输出缓冲，这样可以实时看到日志
python -u app.py

echo Server has been shut down.
pause
