#!/bin/bash
echo ""
echo "=================================================="
echo "     Maimai DX Score Analyzer - Dependency Installer"
echo "=================================================="
echo ""
echo "This script will install required Python libraries in the 'newyolo' Conda environment."
echo ""
echo "Activating Conda environment 'newyolo'..."
# Check if conda is available
if ! command -v conda &> /dev/null
then
    echo "ERROR: conda could not be found. Please make sure Conda is installed."
    exit 1
fi
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate newyolo
# Check if conda activation was successful
if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Failed to activate Conda environment 'newyolo'."
    echo "Please make sure the 'newyolo' environment exists."
    echo ""
    exit 1
fi
echo ""
echo "Conda environment activated successfully."
echo ""
echo "--- Installing PyTorch (Deep Learning Framework) ---"
echo ""
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
echo ""
echo "--- PyTorch installation complete ---"
echo ""
echo ""
echo "--- Installing PaddlePaddle (for OCR) ---"
echo ""
pip3 install paddlepaddle -i https://mirror.baidu.com/pypi/simple
echo ""
echo "--- PaddlePaddle installation complete ---"
echo ""
echo ""
echo "--- Installing other dependencies ---"
pip3 install -r requirements.txt
echo ""
echo "--- Dependency installation complete ---"
echo ""
echo "If there are no red error messages, all libraries were installed successfully."
echo "You can now run start_server.sh to launch the application."
echo ""
