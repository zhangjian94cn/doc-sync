// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * DocSync Electron App - E2E Tests
 * 测试 GUI 静态结构（不依赖 Electron IPC）
 */

test.describe('DocSync GUI Structure', () => {

    test.beforeEach(async ({ page }) => {
        await page.goto(`file://${process.cwd()}/gui/index.html`);
        await page.waitForLoadState('domcontentloaded');
    });

    test('should display DocSync branding', async ({ page }) => {
        const brand = page.locator('.brand span');
        await expect(brand).toContainText('DocSync');
    });

    test('should have 5 navigation menu items', async ({ page }) => {
        const navItems = page.locator('.nav-item');
        await expect(navItems).toHaveCount(5);
    });

    test('should have all navigation tabs', async ({ page }) => {
        await expect(page.locator('[data-tab="dashboard"]')).toBeAttached();
        await expect(page.locator('[data-tab="tasks"]')).toBeAttached();
        await expect(page.locator('[data-tab="settings"]')).toBeAttached();
        await expect(page.locator('[data-tab="tools"]')).toBeAttached();
        await expect(page.locator('[data-tab="appearance"]')).toBeAttached();
    });

    test('should have sync button on dashboard', async ({ page }) => {
        const syncBtn = page.locator('#start-sync-btn');
        await expect(syncBtn).toBeAttached();
    });

    test('should have force sync checkbox', async ({ page }) => {
        const forceCheckbox = page.locator('#force-sync-checkbox');
        await expect(forceCheckbox).toBeAttached();
    });

    test('should have activity log panel', async ({ page }) => {
        await expect(page.locator('.log-panel')).toBeAttached();
        await expect(page.locator('#log-output')).toBeAttached();
        await expect(page.locator('#clear-log-btn')).toBeAttached();
    });

    test('should have add task button', async ({ page }) => {
        await expect(page.locator('#add-task-btn')).toBeAttached();
    });

    test('should have settings form elements', async ({ page }) => {
        await expect(page.locator('#app-id')).toBeAttached();
        await expect(page.locator('#app-secret')).toBeAttached();
        await expect(page.locator('#save-env-btn')).toBeAttached();
    });

    test('should have tools page elements', async ({ page }) => {
        await expect(page.locator('#run-health-check-btn')).toBeAttached();
        await expect(page.locator('#clean-backups-btn')).toBeAttached();
    });

    test('should have appearance options', async ({ page }) => {
        await expect(page.locator('#language-select')).toBeAttached();
        await expect(page.locator('#theme-select')).toBeAttached();
        await expect(page.locator('.color-palette')).toBeAttached();
    });

    test('should have theme toggle button', async ({ page }) => {
        await expect(page.locator('#theme-toggle-btn')).toBeAttached();
    });
});

test.describe('View Switching (simulated)', () => {

    test.beforeEach(async ({ page }) => {
        await page.goto(`file://${process.cwd()}/gui/index.html`);
        await page.waitForLoadState('domcontentloaded');
    });

    test('should switch to tasks view via DOM manipulation', async ({ page }) => {
        await page.evaluate(() => {
            document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
            document.getElementById('tasks')?.classList.add('active');
        });

        await expect(page.locator('#tasks')).toHaveClass(/active/);
    });

    test('should switch to settings view via DOM manipulation', async ({ page }) => {
        await page.evaluate(() => {
            document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
            document.getElementById('settings')?.classList.add('active');
        });

        await expect(page.locator('#settings')).toHaveClass(/active/);
    });

    test('should switch to tools view via DOM manipulation', async ({ page }) => {
        await page.evaluate(() => {
            document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
            document.getElementById('tools')?.classList.add('active');
        });

        await expect(page.locator('#tools')).toHaveClass(/active/);
    });
});

test.describe('Task Template Structure', () => {

    test.beforeEach(async ({ page }) => {
        await page.goto(`file://${process.cwd()}/gui/index.html`);
    });

    test('should have task template with all required fields', async ({ page }) => {
        const templateContent = await page.locator('#task-template').innerHTML();

        expect(templateContent).toContain('task-note-input');
        expect(templateContent).toContain('task-local');
        expect(templateContent).toContain('task-cloud');
        expect(templateContent).toContain('task-vault');
        expect(templateContent).toContain('task-enabled');
        expect(templateContent).toContain('task-force');
    });

    test('should have browse buttons for path selection', async ({ page }) => {
        const templateContent = await page.locator('#task-template').innerHTML();

        expect(templateContent).toContain('browse-btn');
        expect(templateContent).toContain('browse-vault-btn');
    });
});

test.describe('Theme Functionality', () => {

    test.beforeEach(async ({ page }) => {
        await page.goto(`file://${process.cwd()}/gui/index.html`);
    });

    test('should set theme via attribute', async ({ page }) => {
        await page.evaluate(() => {
            document.documentElement.setAttribute('data-theme', 'light');
        });

        const theme = await page.evaluate(() =>
            document.documentElement.getAttribute('data-theme')
        );

        expect(theme).toBe('light');
    });

    test('should toggle theme via attribute', async ({ page }) => {
        // Set initial theme
        await page.evaluate(() => {
            document.documentElement.setAttribute('data-theme', 'dark');
        });

        // Toggle
        await page.evaluate(() => {
            const current = document.documentElement.getAttribute('data-theme');
            document.documentElement.setAttribute('data-theme', current === 'dark' ? 'light' : 'dark');
        });

        const theme = await page.evaluate(() =>
            document.documentElement.getAttribute('data-theme')
        );

        expect(theme).toBe('light');
    });
});

test.describe('CSS Styles', () => {

    test.beforeEach(async ({ page }) => {
        await page.goto(`file://${process.cwd()}/gui/index.html`);
    });

    test('should have CSS variables defined', async ({ page }) => {
        const accentColor = await page.evaluate(() =>
            getComputedStyle(document.documentElement).getPropertyValue('--accent-color').trim()
        );

        expect(accentColor).toBeTruthy();
    });

    test('should have sidebar styled correctly', async ({ page }) => {
        const sidebarBg = await page.evaluate(() => {
            const sidebar = document.querySelector('.sidebar');
            return sidebar ? getComputedStyle(sidebar).backgroundColor : null;
        });

        expect(sidebarBg).toBeTruthy();
    });
});
