const { ipcRenderer } = require('electron');

// State
let tasks = [];
let env = {};
let ui = {}; // 通用外观配置

// DOM Elements
const logOutput = document.getElementById('log-output');
const tasksList = document.getElementById('tasks-list');
const taskTemplate = document.getElementById('task-template');
const pageTitle = document.getElementById('page-title');
const startSyncBtn = document.getElementById('start-sync-btn');
const appStatus = document.getElementById('app-status');
const lastSyncTime = document.getElementById('last-sync-time');

const themeToggleBtn = document.getElementById('theme-toggle-btn');

// --- I18n 简易映射 ---
const i18n = {
    en: {
        brand: 'FeishuSync',
        dashboard: 'Dashboard',
        tasks: 'Tasks',
        settings: 'Settings',
        appearance: 'Appearance',
        syncNow: 'Sync Now',
        syncing: 'Syncing...',
        ready: 'Ready to sync...',
        error: 'Error',
        lastSynced: 'Last synced',
        never: 'Never',
        activityLog: 'Activity Log',
        clearLogs: 'Clear Logs',
        manageSyncPaths: 'Manage your synchronization paths',
        addTask: 'Add Task',
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
        compactTitleBar: 'Compact title bar (smaller top margin)',
        hideTrafficLights: 'Hide window controls (macOS only)',
        about: 'About',
        feishuCredentials: 'Feishu / Lark Credentials',
        credentialsDesc: 'Required for API access',
        appId: 'App ID',
        appSecret: 'App Secret',
        appDesc: 'A modern bidirectional synchronization tool for Obsidian and Feishu.',
        deleteConfirm: 'Delete this task?',
        plsFillIdSecret: 'Please fill in both App ID and App Secret',
        saved: 'Saved!',
        syncCompleted: 'Sync completed successfully!',
        syncFailed: 'Sync failed or completed with errors.',
        initializing: 'Initializing sync engine...',
        processExited: 'Process exited with code',
        removeTask: 'Remove',
        taskNamePlaceholder: 'Task Name',
        pathPlaceholder: 'Path...',
        folderTokenPlaceholder: 'Folder Token',
        browse: '📂',
        localPath: 'Local',
        cloudFolder: 'Cloud',
        forceUpload: 'Force Upload'
    },
    zh: {
        brand: 'FeishuSync',
        dashboard: '仪表盘',
        tasks: '任务',
        settings: '设置',
        appearance: '外观',
        syncNow: '立即同步',
        syncing: '同步中...',
        ready: '准备就绪',
        error: '错误',
        lastSynced: '上次同步',
        never: '从未',
        activityLog: '活动日志',
        clearLogs: '清空日志',
        manageSyncPaths: '管理同步路径',
        addTask: '添加任务',
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
        compactTitleBar: '紧凑标题栏（更小上边距）',
        hideTrafficLights: '隐藏窗口控制按钮（仅 macOS）',
        about: '关于',
        feishuCredentials: '飞书凭据',
        credentialsDesc: '调用 API 所需',
        appId: 'App ID',
        appSecret: 'App Secret',
        appDesc: '一款用于 Obsidian 与飞书双向同步的现代化工具。',
        deleteConfirm: '确定删除此任务？',
        plsFillIdSecret: '请填写 App ID 和 App Secret',
        saved: '已保存！',
        syncCompleted: '同步成功完成！',
        syncFailed: '同步失败或出现错误。',
        initializing: '正在初始化同步引擎...',
        processExited: '进程退出码',
        removeTask: '删除',
        taskNamePlaceholder: '任务名称',
        pathPlaceholder: '本地路径...',
        folderTokenPlaceholder: '云文件夹 Token',
        browse: '📂',
        localPath: '本地',
        cloudFolder: '云端',
        forceUpload: '强制上传'
    }
};

let currentLang = 'en';

function t(key) {
    return i18n[currentLang]?.[key] ?? i18n.en[key] ?? key;
}

function applyTranslations() {
    // 普通文本
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.dataset.i18n;
        if (key) el.textContent = t(key);
    });
    // placeholder
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.dataset.i18nPlaceholder;
        if (key) el.placeholder = t(key);
    });
    // 动态标题
    if (pageTitle && pageTitle.dataset.key) {
        pageTitle.textContent = t(pageTitle.dataset.key);
    }
}

// --- Theme & Accent Management ---
function initTheme() {
    const sysDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const uiTheme = ui.theme || 'system';
    let targetTheme = uiTheme === 'system' ? (sysDark ? 'dark' : 'light') : uiTheme;
    document.documentElement.setAttribute('data-theme', targetTheme);
    const btn = document.getElementById('theme-toggle-btn');
    if (btn) btn.title = targetTheme === 'light' ? 'Switch to Dark' : 'Switch to Light';
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
        themeToggleBtn.title = next === 'light' ? 'Switch to Dark' : 'Switch to Light';
    });
}

// --- 通用外观配置读写 ---
async function loadUI() {
    try {
        const raw = localStorage.getItem('ui');
        ui = raw ? JSON.parse(raw) : { lang: 'en', theme: 'system', accent: '#00D6B9' };
        currentLang = ui.lang || 'en';
        // 填充表单
        const ls = document.getElementById('language-select');
        if (ls) ls.value = currentLang;
        const ts = document.getElementById('theme-select');
        if (ts) ts.value = ui.theme || 'system';
        // 选中色板
        document.querySelectorAll('.color-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.color === (ui.accent || '#00D6B9'));
        });
        // 应用
        initTheme();
        setAccent(ui.accent || '#00D6B9');
        applyTranslations();
    } catch {}
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
    // 视觉反馈
    const btn = document.getElementById('save-appearance-btn');
    if (btn) {
        const ot = btn.textContent;
        btn.textContent = t('saved');
        setTimeout(() => btn.textContent = ot, 1500);
    }
}

// --- Init & Navigation ---
document.addEventListener('DOMContentLoaded', async () => {
    await loadUI();
    // 绑定外观页事件
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

    // Init Config
    await init();

    // Navigation Logic
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(btn => {
        btn.addEventListener('click', (e) => {
            // Active State
            navItems.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // View Switching
            document.querySelectorAll('.view').forEach(c => c.classList.remove('active'));
            const tabId = btn.dataset.tab;
            const targetView = document.getElementById(tabId);
            if (targetView) {
                targetView.classList.add('active');
            } else {
                log(`Error: View ${tabId} not found`);
            }
            
            // Update Header Title & key
            if (pageTitle) {
                pageTitle.dataset.key = tabId;
                pageTitle.textContent = t(tabId);
            }
        });
    });
});

// --- Init ---
async function init() {
    try {
        const config = await ipcRenderer.invoke('get-config');
        env = config.env || {};
        tasks = config.tasks || [];
        
        // Fill Env
        document.getElementById('app-id').value = env.FEISHU_APP_ID || '';
        document.getElementById('app-secret').value = env.FEISHU_APP_SECRET || '';

        // Fill Tasks
        renderTasks();
    } catch (e) {
        log("Error loading config: " + e.message);
    }
}

init();

// --- Logging ---
function log(msg) {
    // Check if empty placeholder exists
    const placeholder = logOutput.querySelector('.log-placeholder');
    if (placeholder) placeholder.remove();

    const isScrolledToBottom = logOutput.scrollHeight - logOutput.scrollTop === logOutput.clientHeight;
    
    // Append content safely
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
    appStatus.textContent = t('syncing');
    appStatus.style.color = 'var(--accent-color)';
    
    logOutput.innerHTML = ''; // Auto clear log on new run
    log(t('initializing'));
    
    ipcRenderer.send('run-sync');
});

ipcRenderer.on('sync-log', (event, msg) => {
    log(msg.trim());
});

ipcRenderer.on('sync-finished', (event, success) => {
    startSyncBtn.classList.remove('syncing');
    startSyncBtn.querySelector('span').textContent = t('syncNow');
    
    if (success) {
        log('\n✅ ' + t('syncCompleted'));
        appStatus.textContent = t('ready');
        appStatus.style.color = 'var(--text-secondary)';
        
        const now = new Date();
        lastSyncTime.textContent = now.toLocaleTimeString();
    } else {
        log('\n❌ ' + t('syncFailed'));
        appStatus.textContent = t('error');
        appStatus.style.color = 'var(--danger-color)';
    }
});

// --- Config Management ---
document.getElementById('save-env-btn').addEventListener('click', async () => {
    const appId = document.getElementById('app-id').value.trim();
    const appSecret = document.getElementById('app-secret').value.trim();
    
    if (!appId || !appSecret) {
        alert(t('plsFillIdSecret'));
        return;
    }

    env.FEISHU_APP_ID = appId;
    env.FEISHU_APP_SECRET = appSecret;
    
    await ipcRenderer.invoke('save-config', { env });
    
    // Visual feedback
    const btn = document.getElementById('save-env-btn');
    const originalText = btn.textContent;
    btn.textContent = t('saved');
    btn.style.backgroundColor = 'var(--accent-color)';
    setTimeout(() => {
        btn.textContent = originalText;
        btn.style.backgroundColor = '';
    }, 2000);
});

// --- Task Management ---
document.getElementById('add-task-btn').addEventListener('click', () => {
    tasks.push({
        note: t('taskNamePlaceholder'),
        local: '',
        cloud: '',
        enabled: true,
        force: false
    });
    renderTasks();
    
    // Switch to Tasks view if not already
    if (!document.getElementById('tasks').classList.contains('active')) {
        document.querySelector('[data-tab="tasks"]').click();
    }
});

function renderTasks() {
    tasksList.innerHTML = '';
    tasks.forEach((task, index) => {
        const clone = taskTemplate.content.cloneNode(true);
        const el = clone.querySelector('.task-card');
        
        const noteInput = el.querySelector('.task-note-input');
        const localInput = el.querySelector('.task-local');
        const cloudInput = el.querySelector('.task-cloud');
        const enabledCheck = el.querySelector('.task-enabled');
        const forceCheck = el.querySelector('.task-force');
        
        noteInput.value = task.note || '';
        localInput.value = task.local || '';
        cloudInput.value = task.cloud || '';
        enabledCheck.checked = task.enabled !== false;
        forceCheck.checked = task.force === true;
        
        // Event Listeners for Data Binding
        const saveTaskState = () => {
            task.note = noteInput.value;
            task.local = localInput.value;
            task.cloud = cloudInput.value;
            task.enabled = enabledCheck.checked;
            task.force = forceCheck.checked;
            ipcRenderer.invoke('save-config', { tasks });
        };

        [noteInput, cloudInput, enabledCheck, forceCheck].forEach(input => {
            input.addEventListener('change', saveTaskState);
        });

        // 删除按钮已存在，绑定事件
        el.querySelector('.delete-task-btn').addEventListener('click', async () => {
            if(confirm(t('deleteConfirm'))) {
                tasks.splice(index, 1);
                await ipcRenderer.invoke('save-config', { tasks });
                renderTasks();
            }
        });

        // Browse
        el.querySelector('.browse-btn').addEventListener('click', async () => {
            const path = await ipcRenderer.invoke('select-folder');
            if (path) {
                localInput.value = path;
                saveTaskState();
            }
        });
        
        tasksList.appendChild(el);
    });
}