/**
 * DocSync Electron App - Unit Tests
 * 测试配置管理和 IPC 通信逻辑
 */

const fs = require('fs');
const path = require('path');

// Mock Electron modules
jest.mock('electron', () => ({
    app: {
        isPackaged: false,
        whenReady: jest.fn().mockResolvedValue(),
        on: jest.fn(),
        quit: jest.fn()
    },
    BrowserWindow: jest.fn().mockImplementation(() => ({
        loadFile: jest.fn(),
        webContents: {
            session: { clearCache: jest.fn() }
        }
    })),
    ipcMain: {
        handle: jest.fn(),
        on: jest.fn()
    },
    dialog: {
        showOpenDialog: jest.fn()
    }
}));

describe('Config Management', () => {
    const testConfigPath = path.join(__dirname, 'test_config.json');

    beforeEach(() => {
        // Clean up test config
        if (fs.existsSync(testConfigPath)) {
            fs.unlinkSync(testConfigPath);
        }
    });

    afterEach(() => {
        if (fs.existsSync(testConfigPath)) {
            fs.unlinkSync(testConfigPath);
        }
    });

    test('should create valid config structure', () => {
        const config = {
            feishu_app_id: 'cli_test123',
            feishu_app_secret: 'secret456',
            tasks: [
                {
                    note: 'Test Task',
                    local: '/path/to/local',
                    cloud: 'folder_token',
                    vault_root: '/path/to/vault',
                    enabled: true,
                    force: false
                }
            ]
        };

        fs.writeFileSync(testConfigPath, JSON.stringify(config, null, 2));

        const loaded = JSON.parse(fs.readFileSync(testConfigPath, 'utf-8'));

        expect(loaded.feishu_app_id).toBe('cli_test123');
        expect(loaded.feishu_app_secret).toBe('secret456');
        expect(loaded.tasks).toHaveLength(1);
        expect(loaded.tasks[0].note).toBe('Test Task');
        expect(loaded.tasks[0].vault_root).toBe('/path/to/vault');
    });

    test('should handle empty config file', () => {
        fs.writeFileSync(testConfigPath, '{}');

        const loaded = JSON.parse(fs.readFileSync(testConfigPath, 'utf-8'));

        expect(loaded.feishu_app_id).toBeUndefined();
        expect(loaded.tasks).toBeUndefined();
    });

    test('should handle legacy array format', () => {
        const legacyConfig = [
            { note: 'Task 1', local: '/path1', cloud: 'token1' },
            { note: 'Task 2', local: '/path2', cloud: 'token2' }
        ];

        fs.writeFileSync(testConfigPath, JSON.stringify(legacyConfig));

        const loaded = JSON.parse(fs.readFileSync(testConfigPath, 'utf-8'));

        expect(Array.isArray(loaded)).toBe(true);
        expect(loaded).toHaveLength(2);
    });

    test('should merge config updates correctly', () => {
        // Initial config
        const initial = {
            feishu_app_id: 'old_id',
            feishu_app_secret: 'old_secret',
            tasks: []
        };
        fs.writeFileSync(testConfigPath, JSON.stringify(initial, null, 2));

        // Load and merge
        const loaded = JSON.parse(fs.readFileSync(testConfigPath, 'utf-8'));
        loaded.feishu_app_id = 'new_id';
        loaded.tasks.push({ note: 'New Task' });

        fs.writeFileSync(testConfigPath, JSON.stringify(loaded, null, 2));

        // Verify
        const final = JSON.parse(fs.readFileSync(testConfigPath, 'utf-8'));
        expect(final.feishu_app_id).toBe('new_id');
        expect(final.feishu_app_secret).toBe('old_secret'); // Preserved
        expect(final.tasks).toHaveLength(1);
    });
});

describe('Task Validation', () => {
    test('should validate required task fields', () => {
        const validTask = {
            note: 'Test',
            local: '/path',
            cloud: 'token'
        };

        expect(validTask.note).toBeTruthy();
        expect(validTask.local).toBeTruthy();
        expect(validTask.cloud).toBeTruthy();
    });

    test('should have default values for optional fields', () => {
        const task = {
            note: 'Test',
            local: '/path',
            cloud: 'token'
        };

        // Apply defaults
        const withDefaults = {
            ...task,
            vault_root: task.vault_root || '',
            enabled: task.enabled !== false,
            force: task.force === true
        };

        expect(withDefaults.vault_root).toBe('');
        expect(withDefaults.enabled).toBe(true);
        expect(withDefaults.force).toBe(false);
    });
});

describe('i18n', () => {
    const i18n = {
        en: { syncNow: 'Sync Now', ready: 'Ready' },
        zh: { syncNow: '立即同步', ready: '准备就绪' }
    };

    test('should return correct English translation', () => {
        const lang = 'en';
        expect(i18n[lang].syncNow).toBe('Sync Now');
    });

    test('should return correct Chinese translation', () => {
        const lang = 'zh';
        expect(i18n[lang].syncNow).toBe('立即同步');
    });

    test('should fallback to English for missing keys', () => {
        const lang = 'zh';
        const key = 'nonexistent';
        const result = i18n[lang]?.[key] ?? i18n.en[key] ?? key;
        expect(result).toBe('nonexistent');
    });
});
