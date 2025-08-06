@echo off
chcp 65001 > nul
echo.
echo ==================================================
echo      Maimai DX Score Analyzer - Dependency Installer
echo ==================================================
echo.
echo This script will install required Python libraries in the 'newyolo' Conda environment.
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
echo --- Installing PyTorch (Deep Learning Framework) ---
echo.
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
echo.
echo --- PyTorch installation complete ---
echo.

echo.
echo --- Installing PaddlePaddle (for OCR) ---
echo.
pip install paddlepaddle -i https://mirror.baidu.com/pypi/simple
echo.
echo --- PaddlePaddle installation complete ---
echo.

echo.
echo --- Installing other dependencies ---
pip install -r requirements.txt

echo.
echo --- Dependency installation complete ---
echo.
echo If there are no red error messages, all libraries were installed successfully.
echo You can now run start_server.bat to launch the application.
echo.
echo Press any key to exit...
pause > nul
