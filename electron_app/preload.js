const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld(
  'api', {
    // Send events to Main process
    send: (channel, data) => {
      // whitelist channels
      let validChannels = ['print-receipt', 'database-backup', 'open-drawer'];
      if (validChannels.includes(channel)) {
        ipcRenderer.send(channel, data);
      }
    },
    // Receive events from Main process
    receive: (channel, func) => {
      let validChannels = ['server-status', 'update-status', 'notification'];
      if (validChannels.includes(channel)) {
        // Deliberately strip event as it includes `sender` 
        ipcRenderer.on(channel, (event, ...args) => func(...args));
      }
    },
    // For desktop specific API access
    isElectron: true,
    platform: process.platform,
    appVersion: process.env.npm_package_version
  }
); 