#!/bin/bash

echo "PPOS Desktop Application Setup"
echo "=============================="

echo "Installing Node.js dependencies..."
npm install

echo ""
echo "Setting up environment..."
mkdir -p assets

echo ""
echo "Setup complete!"
echo ""
echo "To start the application in development mode, run:"
echo "npm run dev"
echo ""
echo "To build the application for your platform, run one of:"
echo "npm run package-linux  # For Linux"
echo "npm run package-mac    # For macOS"
echo "npm run package-win    # For Windows"
echo "" 