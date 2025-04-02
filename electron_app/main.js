const { app, BrowserWindow, Menu, dialog, shell, ipcMain } = require('electron');
const path = require('path');
const url = require('url');
const { PythonShell } = require('python-shell');
const isDev = require('electron-is-dev');
const fs = require('fs');
const child_process = require('child_process');
const dbManager = require('./database');
const updater = require('./updater');

// Keep a global reference of the window object to avoid garbage collection
let mainWindow;
let djangoProcess = null;
let djangoUrl = 'http://localhost:8000';

// Set up Python executable path
function getPythonPath() {
  if (isDev) {
    return 'python'; // Use system Python during development
  } else {
    if (process.platform === 'win32') {
      return path.join(process.resourcesPath, 'app', 'venv', 'Scripts', 'python.exe');
    } else {
      return path.join(process.resourcesPath, 'app', 'venv', 'bin', 'python');
    }
  }
}

// Function to start Django server
function startDjangoServer() {
  const appPath = isDev 
    ? path.join(__dirname, '..') 
    : path.join(process.resourcesPath, 'app');
  
  console.log('Starting Django server from:', appPath);
  
  if (isDev) {
    // In development mode, just run the Django server directly
    djangoProcess = child_process.spawn(
      getPythonPath(), 
      ['manage.py', 'runserver', '8000'], 
      { cwd: appPath }
    );
  } else {
    // In production, run using pythonshell
    const options = {
      mode: 'text',
      pythonPath: getPythonPath(),
      pythonOptions: ['-u'], // unbuffered output
      scriptPath: appPath,
      args: ['runserver', '8000']
    };
    
    djangoProcess = new PythonShell('manage.py', options);
  }
  
  if (isDev) {
    // Log output in development mode
    djangoProcess.stdout.on('data', (data) => {
      console.log(`Django server output: ${data}`);
    });
    
    djangoProcess.stderr.on('data', (data) => {
      console.error(`Django server error: ${data}`);
    });
    
    djangoProcess.on('close', (code) => {
      console.log(`Django server process exited with code ${code}`);
    });
  } else {
    djangoProcess.on('message', function (message) {
      console.log('Django server output:', message);
    });
    
    djangoProcess.on('error', function (error) {
      console.error('Django server error:', error);
    });
    
    djangoProcess.end(function (err, code, signal) {
      console.log('Django server process exited with code:', code);
    });
  }
}

// Function to create the main application window
async function createWindow() {
  // Check database connection first
  try {
    await dbManager.checkDatabaseConnection();
  } catch (error) {
    console.error('Database connection check failed:', error);
  }
  
  // Start Django server
  startDjangoServer();
  
  // Create the browser window
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    icon: path.join(__dirname, 'assets', 'icon.png')
  });
  
  // Wait for Django server to start
  setTimeout(() => {
    // Load the Django application URL
    mainWindow.loadURL(djangoUrl);
    
    // Show dev tools in development mode
    if (isDev) {
      mainWindow.webContents.openDevTools();
    }
    
    // Handle window closed event
    mainWindow.on('closed', function() {
      mainWindow = null;
    });
    
    // Create application menu
    createMenu();
    
    // Check for updates after app is ready (in production)
    if (!isDev) {
      setTimeout(() => {
        updater.checkForUpdates(mainWindow).catch(err => {
          console.error('Update check failed:', err);
        });
      }, 5000); // Wait 5 seconds after app launch
    }
  }, 2000); // Give Django 2 seconds to start
}

// Create the application menu
function createMenu() {
  const template = [
    {
      label: 'File',
      submenu: [
        {
          label: 'Backup Database',
          click() {
            dialog.showSaveDialog(mainWindow, {
              title: 'Backup Database',
              defaultPath: path.join(app.getPath('documents'), 'ppos_backup.sql'),
              filters: [{ name: 'SQL Files', extensions: ['sql'] }]
            }).then(result => {
              if (!result.canceled && result.filePath) {
                dbManager.backupDatabase(result.filePath)
                  .then(success => {
                    if (success) {
                      dialog.showMessageBox(mainWindow, {
                        type: 'info',
                        title: 'Backup Complete',
                        message: 'Database backup was created successfully.',
                        buttons: ['OK']
                      });
                    }
                  })
                  .catch(err => {
                    dialog.showErrorBox('Backup Failed', err.message);
                  });
              }
            });
          }
        },
        {
          label: 'Restore Database',
          click() {
            dialog.showOpenDialog(mainWindow, {
              title: 'Restore Database',
              defaultPath: app.getPath('documents'),
              filters: [{ name: 'SQL Files', extensions: ['sql'] }],
              properties: ['openFile']
            }).then(result => {
              if (!result.canceled && result.filePaths.length > 0) {
                dialog.showMessageBox(mainWindow, {
                  type: 'warning',
                  title: 'Confirm Restore',
                  message: 'Restoring will overwrite your current database. Are you sure you want to continue?',
                  buttons: ['Cancel', 'Restore'],
                  defaultId: 0,
                  cancelId: 0
                }).then(response => {
                  if (response.response === 1) {
                    dbManager.restoreDatabase(result.filePaths[0])
                      .then(success => {
                        if (success) {
                          dialog.showMessageBox(mainWindow, {
                            type: 'info',
                            title: 'Restore Complete',
                            message: 'Database has been restored successfully. The application will now restart.',
                            buttons: ['OK']
                          }).then(() => {
                            app.relaunch();
                            app.exit();
                          });
                        }
                      })
                      .catch(err => {
                        dialog.showErrorBox('Restore Failed', err.message);
                      });
                  }
                });
              }
            });
          }
        },
        { type: 'separator' },
        {
          label: 'Exit',
          accelerator: 'CmdOrCtrl+Q',
          click() {
            app.quit();
          }
        }
      ]
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { type: 'separator' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { role: 'resetZoom' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
        { 
          label: 'Developer Tools',
          accelerator: 'F12',
          click() {
            mainWindow.webContents.toggleDevTools();
          }
        }
      ]
    },
    {
      label: 'Help',
      submenu: [
        {
          label: 'Check for Updates',
          click() {
            updater.checkForUpdates(mainWindow).catch(err => {
              dialog.showErrorBox('Update Check Failed', err.message);
            });
          }
        },
        { type: 'separator' },
        {
          label: 'About',
          click() {
            dialog.showMessageBox(mainWindow, {
              type: 'info',
              title: 'About PPOS',
              message: 'PPOS - Point of Sale System v1.0',
              detail: 'A complete point of sale system for small businesses',
              buttons: ['OK']
            });
          }
        }
      ]
    }
  ];
  
  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

// Set up IPC handlers for communication with renderer
function setupIpcHandlers() {
  // Handle print receipt request
  ipcMain.on('print-receipt', (event, receiptData) => {
    // In a real application, implement receipt printing logic here
    console.log('Print receipt requested:', receiptData);
  });
  
  // Handle database backup request from renderer
  ipcMain.on('database-backup', (event) => {
    dialog.showSaveDialog(mainWindow, {
      title: 'Backup Database',
      defaultPath: path.join(app.getPath('documents'), 'ppos_backup.sql'),
      filters: [{ name: 'SQL Files', extensions: ['sql'] }]
    }).then(result => {
      if (!result.canceled && result.filePath) {
        dbManager.backupDatabase(result.filePath)
          .then(success => {
            event.reply('database-backup-result', { success });
          })
          .catch(err => {
            event.reply('database-backup-result', { success: false, error: err.message });
          });
      }
    });
  });
  
  // Handle check for updates request from renderer
  ipcMain.on('check-for-updates', (event) => {
    updater.checkForUpdates(mainWindow)
      .then(updateAvailable => {
        event.reply('update-status', { updateAvailable });
      })
      .catch(err => {
        event.reply('update-status', { error: err.message });
      });
  });
}

// When Electron has finished initialization
app.whenReady().then(() => {
  createWindow();
  setupIpcHandlers();
});

// Quit when all windows are closed, except on macOS
app.on('window-all-closed', function() {
  // Kill Django server when app is closed
  if (djangoProcess) {
    if (isDev) {
      // Kill the process in development mode
      if (process.platform === 'win32') {
        child_process.exec('taskkill /pid ' + djangoProcess.pid + ' /f /t');
      } else {
        djangoProcess.kill();
      }
    } else {
      // End PythonShell in production mode
      djangoProcess.end(function (err, code, signal) {
        console.log('Django server terminated');
      });
    }
  }
  
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// On macOS, recreate window when dock icon is clicked
app.on('activate', function() {
  if (mainWindow === null) {
    createWindow();
  }
});

// Handle any unhandled Promise rejections
process.on('unhandledRejection', (reason, p) => {
  console.error('Unhandled Rejection at Promise', p, 'reason:', reason);
}); 