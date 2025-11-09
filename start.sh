#!/bin/bash

echo "Starting Market Making Simulator..."
echo "====================================="
echo ""

# Navigate to backend directory
cd backend

# Check if dependencies are installed
if ! python3 -c "import flask" 2>/dev/null; then
    echo "Installing dependencies..."
    pip3 install -r requirements.txt
fi

# Start the server
echo "Starting Flask server..."
echo "Open your browser to: http://localhost:5000"
echo ""
python3 app.py
