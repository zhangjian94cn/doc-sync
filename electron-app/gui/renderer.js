const { ipcRenderer } = require('electron');

// State
let config = {
    feishu_app_id: '',
    feishu_app_secret: '',
    tasks: []
};
let ui = {};
let currentTaskIndex = -1; // -1 for adding new

// --- DOM Elements ---
const logOutput = document.getElementById('log-output');
const tasksList = document.getElementById('tasks-list');
const startSyncBtn = document.getElementById('start-sync-btn');
const appStatus = document.getElementById('app-status');
const lastSyncTime = document.getElementById('last-sync-time');
const themeToggleBtn = document.getElementById('theme-toggle-btn');
const forceSyncCheckbox = document.getElementById('force-sync-checkbox');
const pageTitle = document.getElementById('page-title');

// Modal Elements
const taskModal = document.getElementById('task-modal');
const modalTitle = document.getElementById('modal-title');
const modalNote = document.getElementById('modal-task-note');
const modalLocal = document.getElementById('modal-task-local');
const modalCloud = document.getElementById('modal-task-cloud');
const modalVault = document.getElementById('modal-task-vault');
const modalEnabled = document.getElementById('modal-task-enabled');
const modalForce = document.getElementById('modal-task-force');

// --- I18n ---
const i18n = {
    en: {
        brand: 'DocSync',
        dashboard: 'Dashboard',
        tasks: 'Tasks',
        settings: 'Settings',
        tools: 'Tools',
        appearance: 'Appearance',
        syncNow: 'Sync Now',
        syncing: 'Syncing...',
        ready: 'Ready to sync',
        error: 'Error',
        lastSynced: 'Last synced',
        never: 'Never',
        activityLog: 'Activity Log',
        clearLogs: 'Clear Logs',
        manageSyncPaths: 'Manage your synchronization paths',
        addTask: 'Add Task',
        editTask: 'Edit Task',
        saveCredentials: 'Save Credentials',
        savePreferences: 'Save Preferences',
        general: 'General',
        appWidePrefs: 'Application-wide preferences',
        language: 'Language / 语言',
        theme: 'Theme',
        system: 'System',
        dark: 'Dark',
        light: 'Light',
        accentColor: 'Accent Color',
        window: 'Window',
        titleBarOpts: 'Title bar and layout options',
        compactTitleBar: 'Compact title bar',
        hideTrafficLights: 'Hide window controls (macOS)',
        about: 'About',
        feishuCredentials: 'Feishu / Lark Credentials',
        credentialsDesc: 'Required for API access',
        appId: 'App ID',
        appSecret: 'App Secret',
        appDesc: 'Obsidian → Feishu document sync tool',
        deleteConfirm: 'Are you sure you want to delete this task?',
        plsFillIdSecret: 'Please fill in App ID and App Secret',
        saved: 'Saved successfully',
        syncCompleted: 'Sync completed!',
        syncFailed: 'Sync failed',
        initializing: 'Initializing...',
        removeTask: 'Remove',
        taskNamePlaceholder: 'Task Name',
        pathPlaceholder: 'Path...',
        folderTokenPlaceholder: 'Folder Token',
        vaultRootPlaceholder: 'Vault Root (optional)',
        browse: '📂',
        localPath: 'Local Path',
        cloudFolder: 'Cloud Token',
        vaultRoot: 'Vault Root',
        forceUpload: 'Force Upload',
        forceSync: 'Force Sync (overwrite cloud)',
        healthCheck: 'Health Check',
        healthCheckDesc: 'Check environment and configuration',
        runHealthCheck: 'Run Health Check',
        backupManagement: 'Backup Management',
        backupDesc: 'Manage backup files',
        cleanBackups: 'Clean All Backups',
        cleanBackupsNote: 'This will delete all .bak.* files',
        cleanConfirm: 'Delete all backup files?',
        cleaning: 'Cleaning...',
        cleaned: 'Backups cleaned!',
        checking: 'Checking...',
        checkPassed: '✅ All checks passed',
        checkFailed: '❌ Some checks failed',
        toastSaved: 'Configurations saved',
        toastDeleted: 'Task deleted',
        toastError: 'Operation failed'
    },
    zh: {
        brand: 'DocSync',
        dashboard: '仪表盘',
        tasks: '任务管理',
        settings: '设置',
        tools: '工具',
        appearance: '外观',
        syncNow: '立即同步',
        syncing: '同步中...',
        ready: '准备就绪',
        error: '错误',
        lastSynced: '上次同步',
        never: '从未',
        activityLog: '活动日志',
        clearLogs: '清空日志',
        manageSyncPaths: '管理同步任务配置',
        addTask: '添加任务',
        editTask: '编辑任务',
        saveCredentials: '保存凭据',
        savePreferences: '保存偏好',
        general: '通用',
        appWidePrefs: '应用级偏好设置',
        language: '语言 / Language',
        theme: '主题',
        system: '跟随系统',
        dark: '深色',
        light: '浅色',
        accentColor: '强调色',
        window: '窗口',
        titleBarOpts: '标题栏与布局选项',
        compactTitleBar: '紧凑标题栏',
        hideTrafficLights: '隐藏窗口控制按钮（macOS）',
        about: '关于',
        feishuCredentials: '飞书凭据',
        credentialsDesc: '调用 API 所需',
        appId: 'App ID',
        appSecret: 'App Secret',
        appDesc: 'Obsidian → 飞书文档同步工具',
        deleteConfirm: '确定要删除此任务吗？',
        plsFillIdSecret: '请填写 App ID 和 App Secret',
        saved: '保存成功',
        syncCompleted: '同步成功！',
        syncFailed: '同步失败',
        initializing: '正在初始化...',
        removeTask: '删除',
        taskNamePlaceholder: '任务名称',
        pathPlaceholder: '本地路径...',
        folderTokenPlaceholder: '云文件夹 Token',
        vaultRootPlaceholder: 'Vault 根目录（可选）',
        browse: '📂',
        localPath: '本地路径',
        cloudFolder: '云端 Token',
        vaultRoot: 'Vault 根目录',
        forceUpload: '强制上传',
        forceSync: '强制同步（覆盖云端）',
        healthCheck: '健康检查',
        healthCheckDesc: '检查环境和配置',
        runHealthCheck: '运行健康检查',
        backupManagement: '备份管理',
        backupDesc: '管理备份文件',
        cleanBackups: '清理所有备份',
        cleanBackupsNote: '将删除所有 .bak.* 文件',
        cleanConfirm: '确定删除所有备份文件？',
        cleaning: '清理中...',
        cleaned: '备份已清理！',
        checking: '检查中...',
        checkPassed: '✅ 所有检查通过',
        checkFailed: '❌ 部分检查失败',
        toastSaved: '配置已保存',
        toastDeleted: '任务已删除',
        toastError: '操作失败'
    }
};

let currentLang = 'en';

function t(key) {
    return i18n[currentLang]?.[key] ?? i18n.en[key] ?? key;
}

function applyTranslations() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.dataset.i18n;
        if (key) el.textContent = t(key);
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.dataset.i18nPlaceholder;
        if (key) el.placeholder = t(key);
    });
    if (pageTitle && pageTitle.dataset.key) {
        pageTitle.textContent = t(pageTitle.dataset.key);
    }
}

// --- Utils: Toast ---
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    // Icon based on type
    const icon = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';

    toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;
    container.appendChild(toast);

    // Animate in
    requestAnimationFrame(() => toast.classList.add('show'));

    // Animate out
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// --- Theme & Accent ---
function initTheme() {
    const sysDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const uiTheme = ui.theme || 'system';
    let targetTheme = uiTheme === 'system' ? (sysDark ? 'dark' : 'light') : uiTheme;
    document.documentElement.setAttribute('data-theme', targetTheme);
}

function setAccent(color) {
    document.documentElement.style.setProperty('--accent-color', color);
    document.documentElement.style.setProperty('--accent-hover', adjustColor(color, -10));
}

function adjustColor(col, amt) {
    const num = parseInt(col.slice(1), 16);
    const r = Math.max(0, Math.min(255, (num >> 16) + amt));
    const g = Math.max(0, Math.min(255, (num >> 8 & 0x00FF) + amt));
    const b = Math.max(0, Math.min(255, (num & 0x0000FF) + amt));
    return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')}`;
}

if (themeToggleBtn) {
    themeToggleBtn.addEventListener('click', () => {
        const current = document.documentElement.getAttribute('data-theme');
        const next = current === 'light' ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('theme', next);
    });
}

// --- UI Config ---
async function loadUI() {
    try {
        const raw = localStorage.getItem('ui');
        ui = raw ? JSON.parse(raw) : { lang: 'en', theme: 'system', accent: '#00D6B9' };
        currentLang = ui.lang || 'en';

        const ls = document.getElementById('language-select');
        if (ls) ls.value = currentLang;
        const ts = document.getElementById('theme-select');
        if (ts) ts.value = ui.theme || 'system';

        document.querySelectorAll('.color-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.color === (ui.accent || '#00D6B9'));
        });

        initTheme();
        setAccent(ui.accent || '#00D6B9');
        applyTranslations();
    } catch { }
}

async function saveUI() {
    const ls = document.getElementById('language-select');
    const ts = document.getElementById('theme-select');
    ui.lang = ls ? ls.value : 'en';
    ui.theme = ts ? ts.value : 'system';
    ui.accent = document.querySelector('.color-btn.active')?.dataset.color || '#00D6B9';
    localStorage.setItem('ui', JSON.stringify(ui));
    currentLang = ui.lang;
    applyTranslations();
    initTheme();
    setAccent(ui.accent);

    showToast(t('saved'));
}

// --- Init ---
document.addEventListener('DOMContentLoaded', async () => {
    await loadUI();

    document.getElementById('save-appearance-btn')?.addEventListener('click', saveUI);
    document.getElementById('language-select')?.addEventListener('change', saveUI);
    document.getElementById('theme-select')?.addEventListener('change', saveUI);
    document.querySelectorAll('.color-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.color-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            saveUI();
        });
    });

    // Tools page bindings
    document.getElementById('run-health-check-btn')?.addEventListener('click', runHealthCheck);
    document.getElementById('clean-backups-btn')?.addEventListener('click', cleanBackups);

    // Modal bindings
    document.getElementById('modal-close').addEventListener('click', hideModal);
    document.getElementById('modal-cancel').addEventListener('click', hideModal);
    document.getElementById('modal-save').addEventListener('click', saveTaskFromModal);

    // Modal Browse
    document.getElementById('modal-browse-local').addEventListener('click', async () => {
        const path = await ipcRenderer.invoke('select-folder');
        if (path) {
            modalLocal.value = path;
            // Auto fill vault root if empty
            if (!modalVault.value) modalVault.value = path;
        }
    });

    document.getElementById('modal-browse-vault').addEventListener('click', async () => {
        const path = await ipcRenderer.invoke('select-folder');
        if (path) modalVault.value = path;
    });

    await init();

    // Navigation
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(btn => {
        btn.addEventListener('click', () => {
            navItems.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.querySelectorAll('.view').forEach(c => c.classList.remove('active'));
            const tabId = btn.dataset.tab;
            document.getElementById(tabId)?.classList.add('active');
            if (pageTitle) {
                pageTitle.dataset.key = tabId;
                pageTitle.textContent = t(tabId);
            }
        });
    });
});

async function init() {
    try {
        config = await ipcRenderer.invoke('get-config');

        document.getElementById('app-id').value = config.feishu_app_id || '';
        document.getElementById('app-secret').value = config.feishu_app_secret || '';

        renderTasks();
    } catch (e) {
        log("Error loading config: " + e.message);
    }
}

// --- Logging ---
function log(msg) {
    const placeholder = logOutput.querySelector('.log-placeholder');
    if (placeholder) placeholder.remove();

    const isScrolledToBottom = logOutput.scrollHeight - logOutput.scrollTop === logOutput.clientHeight;

    const line = document.createElement('div');
    line.textContent = msg;
    logOutput.appendChild(line);

    if (isScrolledToBottom) {
        logOutput.scrollTop = logOutput.scrollHeight;
    }
}

document.getElementById('clear-log-btn').addEventListener('click', () => {
    logOutput.innerHTML = '<div class="log-placeholder">' + t('ready') + '</div>';
});

// --- Sync Control ---
startSyncBtn.addEventListener('click', () => {
    if (startSyncBtn.classList.contains('syncing')) return;

    startSyncBtn.classList.add('syncing');
    startSyncBtn.querySelector('span').textContent = t('syncing');

    // Spinner
    const iconBox = startSyncBtn.querySelector('.icon-box');
    iconBox.innerHTML = '<div class="spinner"></div>';

    appStatus.textContent = t('syncing');
    appStatus.style.color = 'var(--accent-color)';

    logOutput.innerHTML = '';
    log(t('initializing'));

    const options = {
        force: forceSyncCheckbox?.checked || false
    };

    ipcRenderer.send('run-sync', options);
});

ipcRenderer.on('sync-log', (event, msg) => {
    log(msg.trim());
});

ipcRenderer.on('sync-finished', (event, success) => {
    startSyncBtn.classList.remove('syncing');
    startSyncBtn.querySelector('span').textContent = t('syncNow');

    // Restore icon
    startSyncBtn.querySelector('.icon-box').innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2" />
        </svg>
    `;

    if (success) {
        log('\n✅ ' + t('syncCompleted'));
        appStatus.textContent = t('ready');
        appStatus.style.color = 'var(--text-secondary)';
        lastSyncTime.textContent = new Date().toLocaleTimeString();
        showToast(t('syncCompleted'), 'success');
    } else {
        log('\n❌ ' + t('syncFailed'));
        appStatus.textContent = t('error');
        appStatus.style.color = 'var(--danger-color)';
        showToast(t('syncFailed'), 'error');
    }
});

// --- Settings ---
document.getElementById('save-env-btn').addEventListener('click', async () => {
    const appId = document.getElementById('app-id').value.trim();
    const appSecret = document.getElementById('app-secret').value.trim();

    if (!appId || !appSecret) {
        showToast(t('plsFillIdSecret'), 'error');
        return;
    }

    await ipcRenderer.invoke('save-config', {
        feishu_app_id: appId,
        feishu_app_secret: appSecret
    });

    showToast(t('saved'));
});

document.getElementById('toggle-secret-btn')?.addEventListener('click', () => {
    const input = document.getElementById('app-secret');
    const type = input.type === 'password' ? 'text' : 'password';
    input.type = type;

    const btn = document.getElementById('toggle-secret-btn');
    const eyeOpen = btn.querySelectorAll('.eye-open');
    const eyeClosed = btn.querySelectorAll('.eye-closed');

    if (type === 'text') {
        eyeOpen.forEach(el => el.style.display = 'none');
        eyeClosed.forEach(el => el.style.display = 'block');
    } else {
        eyeOpen.forEach(el => el.style.display = 'block');
        eyeClosed.forEach(el => el.style.display = 'none');
    }
});

// --- Tools ---
async function runHealthCheck() {
    const btn = document.getElementById('run-health-check-btn');
    const resultDiv = document.getElementById('health-check-result');

    btn.textContent = t('checking');
    btn.disabled = true;
    resultDiv.innerHTML = '';

    try {
        const result = await ipcRenderer.invoke('health-check');
        if (result.success) {
            resultDiv.innerHTML = `<div class="check-success">${t('checkPassed')}</div>`;
        } else {
            resultDiv.innerHTML = `<div class="check-failed">${t('checkFailed')}</div><pre>${result.output}</pre>`;
        }
    } catch (e) {
        resultDiv.innerHTML = `<div class="check-failed">Error: ${e.message}</div>`;
    }

    btn.textContent = t('runHealthCheck');
    btn.disabled = false;
}

async function cleanBackups() {
    const btn = document.getElementById('clean-backups-btn');
    btn.textContent = t('cleaning');
    btn.disabled = true;

    ipcRenderer.send('run-clean');
}

ipcRenderer.on('clean-finished', (event, success) => {
    const btn = document.getElementById('clean-backups-btn');
    btn.textContent = success ? t('cleaned') : t('error');
    btn.disabled = false;
    showToast(success ? t('cleaned') : t('error'), success ? 'success' : 'error');
    setTimeout(() => {
        btn.textContent = t('cleanBackups');
    }, 2000);
});

// --- Task Management (Refactored) ---

// Add Task Button
document.getElementById('add-task-btn').addEventListener('click', () => {
    showModal(-1);
});

function showModal(index) {
    currentTaskIndex = index;
    const isEdit = index >= 0;

    modalTitle.textContent = isEdit ? t('editTask') : t('addTask');

    if (isEdit) {
        const task = config.tasks[index];
        modalNote.value = task.note || '';
        modalLocal.value = task.local || '';
        modalCloud.value = task.cloud || '';
        modalVault.value = task.vault_root || '';
        modalEnabled.checked = task.enabled !== false;
        modalForce.checked = task.force === true;
    } else {
        // Clear for new
        modalNote.value = '';
        modalLocal.value = '';
        modalCloud.value = '';
        modalVault.value = '';
        modalEnabled.checked = true;
        modalForce.checked = false;
    }

    taskModal.classList.add('active');
}

function hideModal() {
    taskModal.classList.remove('active');
}

async function saveTaskFromModal() {
    const newTask = {
        note: modalNote.value.trim(),
        local: modalLocal.value.trim(),
        cloud: modalCloud.value.trim(),
        vault_root: modalVault.value.trim(),
        enabled: modalEnabled.checked,
        force: modalForce.checked
    };

    // Validation
    if (!newTask.note || !newTask.local || !newTask.cloud) {
        showToast('Please fill in required fields', 'error');
        return;
    }

    if (!config.tasks) config.tasks = [];

    if (currentTaskIndex >= 0) {
        config.tasks[currentTaskIndex] = newTask;
    } else {
        config.tasks.push(newTask);
    }

    await ipcRenderer.invoke('save-config', { tasks: config.tasks });

    hideModal();
    renderTasks();
    showToast(t('saved'));
}

async function deleteTask(index) {
    // Custom dialog or confirm
    if (confirm(t('deleteConfirm'))) {
        config.tasks.splice(index, 1);
        await ipcRenderer.invoke('save-config', { tasks: config.tasks });
        renderTasks();
        showToast(t('toastDeleted'));
    }
}

function renderTasks() {
    tasksList.innerHTML = '';
    tasksList.className = 'tasks-list-container'; // Changed from grid

    if (!config.tasks || config.tasks.length === 0) {
        tasksList.innerHTML = `<div class="empty-state">
            <div style="font-size:40px;margin-bottom:10px">📝</div>
            <p>${t('i18n') ? t('addTask') : 'No tasks yet. Add one to start syncing!'}</p>
        </div>`;
        return;
    }

    config.tasks.forEach((task, index) => {
        const item = document.createElement('div');
        item.className = `task-list-item ${task.enabled !== false ? 'enabled' : 'disabled'}`;

        item.innerHTML = `
            <div class="task-info">
                <div class="task-title">${task.note || 'Untitled Task'}</div>
                <div class="task-detail">
                    <span>📂 ${task.local || '...'}</span>
                    <span style="opacity:0.5">➜</span>
                    <span>☁️ ${task.cloud ? task.cloud.substring(0, 8) + '...' : '...'}</span>
                </div>
            </div>
            <div class="task-actions-group">
                <button class="icon-btn edit-btn" title="${t('editTask')}">✎</button>
                <button class="icon-btn delete-btn" title="${t('removeTask')}" style="color:var(--danger-color)">🗑</button>
            </div>
        `;

        // Bind events
        item.querySelector('.edit-btn').addEventListener('click', () => showModal(index));
        item.querySelector('.delete-btn').addEventListener('click', () => deleteTask(index));

        tasksList.appendChild(item);
    });
}