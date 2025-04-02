@echo off
echo PPOS Desktop Application Setup
echo ==============================

echo Installing Node.js dependencies...
call npm install

echo.
echo Setting up environment...
mkdir assets 2>NUL

echo.
echo Setup complete!
echo.
echo To start the application in development mode, run:
echo npm run dev
echo.
echo To build the application for Windows, run:
echo npm run package-win
echo. 