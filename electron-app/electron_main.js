const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 900,
    height: 700,
    titleBarStyle: 'hiddenInset', // Mac-style seamless title bar
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false, // For simplicity in this local tool
    },
    backgroundColor: '#1e1e1e'
  });

  // Force clear cache
  mainWindow.webContents.session.clearCache();

  mainWindow.loadFile(path.join(__dirname, 'gui/index.html'));
  // mainWindow.webContents.openDevTools(); // Uncomment for debugging
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// --- Helpers ---

// Get path to the python executable or script
function getPythonPath() {
  const isDev = !app.isPackaged;
  if (isDev) {
    // In dev, use system python and source script
    // Running from electron-app/ directory, so main.py is in ../main.py
    return { command: 'python3', args: ['main.py'] };
  } else {
    // In production, use the bundled executable
    let execName = process.platform === 'win32' ? 'doc-sync-core.exe' : 'doc-sync-core';
    const execPath = path.join(process.resourcesPath, 'python', execName);
    return { command: execPath, args: [] };
  }
}

function getEnvPath() {
  return app.isPackaged 
    ? path.join(process.resourcesPath, '.env') 
    : path.join(__dirname, '../.env');
}

function getConfigPath() {
  return app.isPackaged 
    ? path.join(process.resourcesPath, 'sync_config.json') 
    : path.join(__dirname, '../sync_config.json');
}

// --- IPC Handlers ---

ipcMain.handle('select-folder', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory']
  });
  if (result.canceled) return null;
  return result.filePaths[0];
});

ipcMain.handle('get-config', async () => {
  const envPath = getEnvPath();
  const configPath = getConfigPath();
  
  let envContent = '';
  let syncConfig = [];

  try {
    if (fs.existsSync(envPath)) {
      envContent = fs.readFileSync(envPath, 'utf-8');
    }
  } catch (e) { console.error('Error reading .env', e); }

  try {
    if (fs.existsSync(configPath)) {
      syncConfig = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
    }
  } catch (e) { console.error('Error reading config', e); }

  // Parse .env manually for simplicity
  const envVars = {};
  envContent.split('\n').forEach(line => {
    const [key, ...val] = line.split('=');
    if (key && val) envVars[key.trim()] = val.join('=').trim();
  });

  return { env: envVars, tasks: syncConfig };
});

ipcMain.handle('save-config', async (event, data) => {
  const { env, tasks } = data;
  const envPath = getEnvPath();
  const configPath = getConfigPath();

  // Save .env
  if (env) {
    const envStr = Object.entries(env)
      .map(([k, v]) => `${k}=${v}`)
      .join('\n');
    fs.writeFileSync(envPath, envStr);
  }

  // Save sync_config.json
  if (tasks) {
    fs.writeFileSync(configPath, JSON.stringify(tasks, null, 2));
  }
  
  return { success: true };
});

ipcMain.on('run-sync', (event) => {
  const { command, args } = getPythonPath();
  
  // In dev: cwd should be root (..) so python can import src and find config in root
  // In prod: cwd should be resourcesPath where .env and config are expected
  const cwd = app.isPackaged ? process.resourcesPath : path.join(__dirname, '..');

  const options = {
    cwd: cwd,
    env: { ...process.env }
  };
  
  event.reply('sync-log', `🚀 Starting sync process...\nCommand: ${command} ${args.join(' ')}\nCWD: ${options.cwd}\n`);

  const child = spawn(command, args, options);

  child.stdout.on('data', (data) => {
    event.reply('sync-log', data.toString());
  });

  child.stderr.on('data', (data) => {
    event.reply('sync-log', `[ERROR] ${data.toString()}`);
  });

  child.on('close', (code) => {
    event.reply('sync-log', `\n✨ Process exited with code ${code}`);
    event.reply('sync-finished', code === 0);
  });
});
