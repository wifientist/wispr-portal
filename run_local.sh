#!/bin/bash

# Copy .env from example if it doesn't exist
if [ ! -f .env ]; then
    echo "No .env file found — copying from .env.example..."
    cp .env.example .env
    echo "Edit .env to configure your environment, then re-run this script."
fi

# Create and activate virtual environment
echo "Creating Python virtual environment..."
python3 -m venv .venv

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Run the application
echo "Starting WISPr Portal application..."
echo "Application will be available at http://localhost:8080"
echo "Press Ctrl+C to stop the server"
python server.py
