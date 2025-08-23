#!/bin/bash
echo "Starting Admin Panel Server..."
# Check if conda is available
if ! command -v conda &> /dev/null
then
    echo "ERROR: conda could not be found. Please make sure Conda is installed."
    exit 1
fi
echo "Activating Conda environment: newyolo"
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
# Get the directory of the script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# Change to the project root directory
cd "$SCRIPT_DIR/.."
echo "Loading environment variables from .env file..."
# Load environment variables from .env file
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi
# Set default port if not defined in .env
ADMIN_PORT=${ADMIN_PORT:-25565}
echo "Starting Waitress server for the admin panel in the background on port ${ADMIN_PORT}..."
# The log file will be in the same directory as the script
LOG_FILE="$SCRIPT_DIR/admin.log"
PID_FILE="$SCRIPT_DIR/admin.pid"
# Check if the process is already running
if [ -f "$PID_FILE" ] && ps -p $(cat "$PID_FILE") > /dev/null; then
    echo "Admin server is already running."
    exit 1
fi
# Start the server with nohup, redirect output, run in background, and save PID
nohup waitress-serve --host 0.0.0.0 --port=${ADMIN_PORT} admin.app:app > "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
echo "Admin server started. Log file: $LOG_FILE, PID file: $PID_FILE"
