const { app } = require('electron');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const isDev = require('electron-is-dev');

class DatabaseManager {
  constructor() {
    this.appPath = isDev 
      ? path.join(__dirname, '..') 
      : path.join(process.resourcesPath, 'app');
    
    this.dbSettingsPath = path.join(this.appPath, 'posproject', 'settings.py');
    this.offlineMode = false;
  }
  
  // Check if MySQL is available, fall back to SQLite if not
  async checkDatabaseConnection() {
    return new Promise((resolve, reject) => {
      const pythonPath = isDev ? 'python' : path.join(this.appPath, 'venv', 'bin', 'python');
      const checkProcess = spawn(
        pythonPath, 
        ['-c', 'import mysql.connector; mysql.connector.connect(host="localhost", user="root", password="msa123")'],
        { cwd: this.appPath }
      );
      
      checkProcess.on('close', (code) => {
        if (code === 0) {
          console.log('MySQL connection successful');
          this.offlineMode = false;
          resolve(true);
        } else {
          console.log('MySQL connection failed, switching to SQLite');
          this.offlineMode = true;
          this.switchToSqlite()
            .then(() => resolve(false))
            .catch(reject);
        }
      });
    });
  }
  
  // Modify Django settings to use SQLite instead of MySQL
  async switchToSqlite() {
    return new Promise((resolve, reject) => {
      fs.readFile(this.dbSettingsPath, 'utf8', (err, data) => {
        if (err) {
          console.error('Error reading settings file:', err);
          return reject(err);
        }
        
        // Replace MySQL database settings with SQLite
        const sqliteConfig = `
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}
`;
        
        // Find the database configuration block and replace it
        const mysqlPattern = /DATABASES = {[\s\S]*?}/m;
        const newData = data.replace(mysqlPattern, sqliteConfig);
        
        fs.writeFile(this.dbSettingsPath, newData, 'utf8', (err) => {
          if (err) {
            console.error('Error writing settings file:', err);
            return reject(err);
          }
          
          console.log('Successfully switched to SQLite');
          this.migrateDatabase()
            .then(resolve)
            .catch(reject);
        });
      });
    });
  }
  
  // Run migrations after switching to SQLite
  async migrateDatabase() {
    return new Promise((resolve, reject) => {
      const pythonPath = isDev ? 'python' : path.join(this.appPath, 'venv', 'bin', 'python');
      const migrateProcess = spawn(
        pythonPath,
        ['manage.py', 'migrate'],
        { cwd: this.appPath }
      );
      
      migrateProcess.stdout.on('data', (data) => {
        console.log(`Migration output: ${data}`);
      });
      
      migrateProcess.stderr.on('data', (data) => {
        console.error(`Migration error: ${data}`);
      });
      
      migrateProcess.on('close', (code) => {
        if (code === 0) {
          console.log('Database migration successful');
          resolve();
        } else {
          console.error('Database migration failed');
          reject(new Error('Database migration failed'));
        }
      });
    });
  }
  
  // Backup the MySQL database to a file
  async backupDatabase(backupPath) {
    if (this.offlineMode) {
      console.log('Cannot backup in offline mode');
      return Promise.resolve(false);
    }
    
    return new Promise((resolve, reject) => {
      const backupProcess = spawn(
        'mysqldump',
        [
          '-u', 'root', 
          `-p${'msa123'}`, 
          'ppos_db'
        ],
        { shell: true }
      );
      
      const writeStream = fs.createWriteStream(backupPath);
      
      backupProcess.stdout.pipe(writeStream);
      
      backupProcess.stderr.on('data', (data) => {
        console.error(`Backup error: ${data}`);
      });
      
      backupProcess.on('close', (code) => {
        if (code === 0) {
          console.log(`Database backup created at ${backupPath}`);
          resolve(true);
        } else {
          console.error('Database backup failed');
          reject(new Error('Database backup failed'));
        }
      });
    });
  }
  
  // Restore a MySQL database from a backup file
  async restoreDatabase(backupPath) {
    if (this.offlineMode) {
      console.log('Cannot restore in offline mode');
      return Promise.resolve(false);
    }
    
    return new Promise((resolve, reject) => {
      const restoreProcess = spawn(
        'mysql',
        [
          '-u', 'root', 
          `-p${'msa123'}`, 
          'ppos_db'
        ],
        { shell: true }
      );
      
      const readStream = fs.createReadStream(backupPath);
      
      readStream.pipe(restoreProcess.stdin);
      
      restoreProcess.stderr.on('data', (data) => {
        console.error(`Restore error: ${data}`);
      });
      
      restoreProcess.on('close', (code) => {
        if (code === 0) {
          console.log('Database restore completed');
          resolve(true);
        } else {
          console.error('Database restore failed');
          reject(new Error('Database restore failed'));
        }
      });
    });
  }
}

module.exports = new DatabaseManager(); 