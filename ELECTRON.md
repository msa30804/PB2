# PPOS Desktop Application

This document explains how to use the Electron-based desktop application for the PPOS (Point of Sale System).

## What is Electron?

Electron is a framework that allows you to create desktop applications with web technologies like JavaScript, HTML, and CSS. It combines Chromium (for rendering) and Node.js (for system access), enabling web applications to run as desktop applications with native capabilities.

## Why Desktop Version?

The desktop version of PPOS offers several advantages:

1. **Offline Capabilities** - The application works even without an internet connection
2. **Native System Integration** - Access to printers, barcode scanners, and other hardware
3. **Improved Security** - Runs in a contained environment
4. **Better Performance** - Optimized for desktop usage
5. **Simplified Deployment** - Single executable file for end users

## Getting Started

### For Users

If you've received a packaged application:

1. Install the application by running the installer
2. Launch the application from your start menu or desktop shortcut
3. Log in with your credentials
4. The application will automatically set up the database on first run

### For Developers

To set up the development environment:

1. Navigate to the `electron_app` directory
2. Run the setup script:
   - Windows: `setup.bat`
   - macOS/Linux: `bash setup.sh`
3. Start the application in development mode:
   - `npm run dev`

For detailed instructions, see the [Getting Started Guide](electron_app/GETTING_STARTED.md).

## Features

The desktop application includes all features of the web version, plus:

- **Database Management** - Backup and restore database
- **Automatic Updates** - Checks for and installs updates
- **Offline Mode** - Works without internet connectivity
- **Hardware Integration** - Support for receipt printers and barcode scanners
- **Cross-Platform** - Works on Windows, macOS, and Linux

## Packaging

To create distributable packages:

### Windows
```bash
cd electron_app
npm run package-win
```

### macOS
```bash
cd electron_app
npm run package-mac
```

### Linux
```bash
cd electron_app
npm run package-linux
```

The packaged applications will be available in the `electron_app/dist` directory.

## Customization

The application can be customized in several ways:

- **Branding** - Update the icons in `electron_app/assets/`
- **Application Name** - Edit the `productName` in `electron_app/package.json`
- **Database Settings** - Configure connection details in `posproject/settings.py`

## Troubleshooting

If you encounter issues:

1. **Database Connection** - Verify MySQL is running and credentials are correct
2. **Application Crashes** - Check the logs in:
   - Windows: `%APPDATA%\PPOS\logs`
   - macOS: `~/Library/Logs/PPOS`
   - Linux: `~/.config/PPOS/logs`
3. **Updates Failing** - Ensure you have an internet connection and adequate disk space

## Contributing

Contributions to the desktop application are welcome! See the main project README for contribution guidelines. 