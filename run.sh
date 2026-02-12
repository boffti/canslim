#!/bin/bash
cd "$(dirname "$0")"

# Load environment variables from .env if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Check required environment variables
if [ -z "$GOOGLE_SHEET_ID" ]; then
    echo "ERROR: GOOGLE_SHEET_ID not set in .env file"
    echo "Please copy .env.example to .env and configure it"
    exit 1
fi

if [ -z "$GOG_ACCOUNT" ]; then
    echo "ERROR: GOG_ACCOUNT not set in .env file"
    echo "Please copy .env.example to .env and configure it"
    exit 1
fi

# Create data directory if it doesn't exist
mkdir -p data/history data/routines

# Run the app using uv
PORT=${PORT:-5561}
echo "Starting CANSLIM Scanner Dashboard on http://localhost:$PORT"
uv run run.py

