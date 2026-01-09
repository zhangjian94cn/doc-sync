const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');

// Set app name
app.name = 'DocSync';

let mainWindow;

function createWindow() {
  // Choose icon format based on platform
  const iconName = process.platform === 'darwin' ? 'icon.icns' :
    process.platform === 'win32' ? 'icon.ico' : 'icon.png';

  mainWindow = new BrowserWindow({
    width: 900,
    height: 700,
    title: 'DocSync',
    titleBarStyle: 'hiddenInset',
    icon: path.join(__dirname, 'build-assets', iconName),
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    },
    backgroundColor: '#1e1e1e'
  });

  mainWindow.webContents.session.clearCache();
  mainWindow.loadFile(path.join(__dirname, 'gui/index.html'));
  // mainWindow.webContents.openDevTools(); // Uncomment for debugging
}

app.whenReady().then(() => {
  // Set dock icon on macOS
  if (process.platform === 'darwin' && app.dock) {
    app.dock.setIcon(path.join(__dirname, 'build-assets/icon.png'));
  }
  createWindow();
});

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

function getPythonPath() {
  const isDev = !app.isPackaged;
  if (isDev) {
    return { command: 'python3', args: ['main.py'] };
  } else {
    let execName = process.platform === 'win32' ? 'doc-sync-core.exe' : 'doc-sync-core';
    const execPath = path.join(process.resourcesPath, 'python', execName);
    return { command: execPath, args: [] };
  }
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

ipcMain.handle('select-file', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'],
    filters: [{ name: 'Markdown', extensions: ['md'] }]
  });
  if (result.canceled) return null;
  return result.filePaths[0];
});

ipcMain.handle('get-config', async () => {
  const configPath = getConfigPath();

  let config = {
    feishu_app_id: '',
    feishu_app_secret: '',
    feishu_user_access_token: '',
    feishu_user_refresh_token: '',
    feishu_assets_token: '',
    tasks: []
  };

  try {
    if (fs.existsSync(configPath)) {
      const data = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
      if (typeof data === 'object' && !Array.isArray(data)) {
        config = { ...config, ...data };
      } else if (Array.isArray(data)) {
        // Legacy format: array of tasks
        config.tasks = data;
      }
    }
  } catch (e) {
    console.error('Error reading config', e);
  }

  return config;
});

ipcMain.handle('save-config', async (event, data) => {
  const configPath = getConfigPath();

  // Load existing config first
  let config = {};
  try {
    if (fs.existsSync(configPath)) {
      const existing = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
      if (typeof existing === 'object' && !Array.isArray(existing)) {
        config = existing;
      }
    }
  } catch (e) { }

  // Merge new data
  if (data.feishu_app_id !== undefined) {
    config.feishu_app_id = data.feishu_app_id;
  }
  if (data.feishu_app_secret !== undefined) {
    config.feishu_app_secret = data.feishu_app_secret;
  }
  if (data.tasks !== undefined) {
    config.tasks = data.tasks;
  }

  // Save
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2));

  return { success: true };
});

ipcMain.on('run-sync', (event, options = {}) => {
  const { command, args } = getPythonPath();

  // Add force flag if requested
  if (options.force) {
    args.push('--force');
  }

  const cwd = app.isPackaged ? process.resourcesPath : path.join(__dirname, '..');

  const spawnOptions = {
    cwd: cwd,
    env: { ...process.env }
  };

  event.reply('sync-log', `🚀 Starting sync process...\nCommand: ${command} ${args.join(' ')}\nCWD: ${spawnOptions.cwd}\n`);

  const child = spawn(command, args, spawnOptions);

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

// Health check handler
ipcMain.handle('health-check', async () => {
  const { command, args } = getPythonPath();
  const cwd = app.isPackaged ? process.resourcesPath : path.join(__dirname, '..');

  return new Promise((resolve) => {
    const checkArgs = [...args];
    // Just try to import and exit
    const child = spawn(command, ['--help'], { cwd, env: process.env });

    let output = '';
    child.stdout.on('data', (data) => output += data.toString());
    child.stderr.on('data', (data) => output += data.toString());

    child.on('close', (code) => {
      resolve({ success: code === 0, output });
    });

    // Timeout after 5 seconds
    setTimeout(() => {
      child.kill();
      resolve({ success: false, output: 'Timeout' });
    }, 5000);
  });
});

// Clean backups handler
ipcMain.on('run-clean', (event) => {
  const { command, args } = getPythonPath();
  const cwd = app.isPackaged ? process.resourcesPath : path.join(__dirname, '..');

  const cleanArgs = [...args, '--clean'];

  const child = spawn(command, cleanArgs, { cwd, env: process.env });

  let output = '';
  child.stdout.on('data', (data) => output += data.toString());
  child.stderr.on('data', (data) => output += data.toString());

  child.on('close', (code) => {
    event.reply('clean-finished', code === 0);
  });
});

