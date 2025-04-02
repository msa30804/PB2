const { dialog, app, BrowserWindow } = require('electron');
const https = require('https');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const isDev = require('electron-is-dev');

class Updater {
  constructor() {
    this.currentVersion = app.getVersion();
    this.updateUrl = 'https://api.github.com/repos/msa30804/ppos/releases/latest';
    this.downloadUrl = null;
    this.releaseNotes = null;
    this.newVersion = null;
  }

  // Check for updates
  checkForUpdates(mainWindow) {
    if (isDev) {
      console.log('Update checking disabled in dev mode');
      return Promise.resolve(false);
    }

    return new Promise((resolve, reject) => {
      console.log('Checking for updates...');
      
      const request = https.get(this.updateUrl, {
        headers: { 'User-Agent': 'PPOS-App' }
      }, (response) => {
        if (response.statusCode !== 200) {
          return reject(new Error(`Failed to check for updates: ${response.statusCode}`));
        }
        
        let data = '';
        
        response.on('data', (chunk) => {
          data += chunk;
        });
        
        response.on('end', () => {
          try {
            const releaseData = JSON.parse(data);
            this.newVersion = releaseData.tag_name.replace('v', '');
            this.releaseNotes = releaseData.body;
            
            if (this.newVersion && this.compareVersions(this.newVersion, this.currentVersion) > 0) {
              // Find the download URL for the appropriate platform
              const assets = releaseData.assets;
              let assetName = '';
              
              if (process.platform === 'win32') {
                assetName = 'PPOS-Setup.exe';
              } else if (process.platform === 'darwin') {
                assetName = 'PPOS.dmg';
              } else if (process.platform === 'linux') {
                assetName = 'PPOS.AppImage';
              }
              
              const asset = assets.find(a => a.name.includes(assetName));
              if (asset) {
                this.downloadUrl = asset.browser_download_url;
                
                // Ask user if they want to update
                this.promptForUpdate(mainWindow).then(shouldUpdate => {
                  resolve(shouldUpdate);
                });
              } else {
                console.log('No compatible release found');
                resolve(false);
              }
            } else {
              console.log('No update available');
              resolve(false);
            }
          } catch (error) {
            console.error('Error parsing update info:', error);
            reject(error);
          }
        });
      });
      
      request.on('error', (error) => {
        console.error('Error checking for updates:', error);
        reject(error);
      });
      
      request.end();
    });
  }
  
  // Compare version strings
  compareVersions(a, b) {
    const aParts = a.split('.').map(Number);
    const bParts = b.split('.').map(Number);
    
    for (let i = 0; i < 3; i++) {
      const aVal = aParts[i] || 0;
      const bVal = bParts[i] || 0;
      
      if (aVal > bVal) return 1;
      if (aVal < bVal) return -1;
    }
    
    return 0;
  }
  
  // Prompt user to update
  promptForUpdate(mainWindow) {
    return new Promise((resolve) => {
      dialog.showMessageBox(mainWindow, {
        type: 'info',
        title: 'Update Available',
        message: `A new version (${this.newVersion}) is available. Would you like to download it now?`,
        detail: this.releaseNotes || 'No release notes available',
        buttons: ['Later', 'Update Now'],
        defaultId: 1
      }).then(result => {
        if (result.response === 1) {
          this.downloadUpdate(mainWindow).then(() => {
            resolve(true);
          }).catch(() => {
            resolve(false);
          });
        } else {
          resolve(false);
        }
      });
    });
  }
  
  // Download and install update
  downloadUpdate(mainWindow) {
    return new Promise((resolve, reject) => {
      // Show a progress dialog
      const progressWin = new BrowserWindow({
        title: 'Downloading Update',
        width: 350,
        height: 150,
        useContentSize: true,
        resizable: false,
        minimizable: false,
        maximizable: false,
        fullscreenable: false,
        parent: mainWindow,
        modal: true,
        webPreferences: {
          nodeIntegration: true,
          contextIsolation: false
        }
      });
      
      progressWin.loadURL(`data:text/html,
        <html>
        <head>
          <style>
            body {
              font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
              margin: 20px;
              color: #333;
            }
            progress {
              width: 100%;
              height: 20px;
              margin-top: 10px;
            }
            h4 {
              margin-top: 0;
            }
          </style>
        </head>
        <body>
          <h4>Downloading update...</h4>
          <progress id="progress" value="0" max="100"></progress>
          <p id="status">Starting download...</p>
          <script>
            window.api = {
              updateProgress: (percent) => {
                document.getElementById('progress').value = percent;
              },
              updateStatus: (msg) => {
                document.getElementById('status').innerText = msg;
              }
            };
          </script>
        </body>
        </html>
      `);
      
      // Download the file
      const downloadPath = path.join(app.getPath('temp'), path.basename(this.downloadUrl));
      const file = fs.createWriteStream(downloadPath);
      
      https.get(this.downloadUrl, (response) => {
        if (response.statusCode !== 200) {
          progressWin.close();
          return reject(new Error(`Failed to download update: ${response.statusCode}`));
        }
        
        const totalLength = parseInt(response.headers['content-length'], 10);
        let downloaded = 0;
        
        response.on('data', (chunk) => {
          downloaded += chunk.length;
          const percent = Math.floor((downloaded / totalLength) * 100);
          progressWin.webContents.executeJavaScript(`window.api.updateProgress(${percent})`);
          progressWin.webContents.executeJavaScript(`window.api.updateStatus("Downloaded ${percent}%")`);
        });
        
        response.pipe(file);
        
        file.on('finish', () => {
          file.close();
          progressWin.webContents.executeJavaScript(`window.api.updateStatus("Download complete. Installing...")`);
          
          // Install the update (platform specific)
          setTimeout(() => {
            progressWin.close();
            
            if (process.platform === 'win32') {
              spawn(downloadPath, [], { detached: true });
            } else if (process.platform === 'darwin') {
              spawn('open', [downloadPath], { detached: true });
            } else {
              spawn('chmod', ['+x', downloadPath], () => {
                spawn(downloadPath, [], { detached: true });
              });
            }
            
            // Quit the app to install update
            app.quit();
            resolve();
          }, 1000);
        });
      }).on('error', (err) => {
        fs.unlink(downloadPath, () => {}); // Clean up the file
        progressWin.close();
        dialog.showErrorBox('Update Error', `Failed to download update: ${err.message}`);
        reject(err);
      });
    });
  }
}

module.exports = new Updater(); 