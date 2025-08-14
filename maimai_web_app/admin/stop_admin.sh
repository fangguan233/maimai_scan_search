#!/bin/bash
# Get the directory of the script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PID_FILE="$SCRIPT_DIR/admin.pid"
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p $PID > /dev/null; then
        echo "Stopping admin server with PID $PID..."
        kill $PID
        # Wait a moment for the process to terminate
        sleep 2
        if ps -p $PID > /dev/null; then
            echo "Process did not stop, forcing kill..."
            kill -9 $PID
        fi
        rm "$PID_FILE"
        echo "Admin server stopped."
    else
        echo "Admin server is not running, but PID file exists. Removing stale PID file."
        rm "$PID_FILE"
    fi
else
    echo "Admin server is not running (no PID file found)."
fi
