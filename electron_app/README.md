# PPOS Desktop Application

This is the desktop application wrapper for the PPOS (Point of Sale System) built with Electron.js.

## Features

- Cross-platform desktop application (Windows, macOS, Linux)
- Integrated Django backend
- Native system integration
- Offline capability
- Built-in database management

## Development Setup

### Prerequisites

- Node.js (v14+)
- npm (v6+)
- Python (v3.8+)
- MySQL

### Installation

1. Install Electron dependencies:

```bash
cd electron_app
npm install
```

2. Start the application in development mode:

```bash
npm run dev
```

This will:
- Start the Django server in the background
- Launch the Electron application pointing to the Django server

## Building for Production

### Windows

```bash
npm run package-win
```

### macOS

```bash
npm run package-mac
```

### Linux

```bash
npm run package-linux
```

## Project Structure

- `main.js`: Main Electron application file
- `preload.js`: Secure bridge between Electron and web content
- `package.json`: Electron app configuration
- `assets/`: Application icons and resources

## Notes

- The Django application is bundled with the Electron app
- MySQL database connection is required
- For development, the app connects to a local Django server
- For production, the Django app is bundled with the executable 