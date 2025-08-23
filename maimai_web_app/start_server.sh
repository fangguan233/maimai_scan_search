#!/bin/bash
echo ""
echo "=================================================="
echo "     Maimai DX Score Analyzer - Server Launcher"
echo "=================================================="
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
echo "Loading environment variables from .env file..."
# Load environment variables from .env file
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi
# Set default port if not defined in .env
APP_PORT=${APP_PORT:-25564}
echo "Launching server with Waitress on port ${APP_PORT}..."
echo ""
echo " - Local access: http://localhost:${APP_PORT}"
echo " - Network access: http://$(hostname -I | awk '{print $1}'):${APP_PORT}"
echo ""
echo "Server is running. Do not close this window."
echo "Press Ctrl+C to stop the server."
echo ""
waitress-serve --host=0.0.0.0 --port=${APP_PORT} app:app
echo ""
echo "Server has been stopped."
