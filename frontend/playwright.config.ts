import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e', timeout: 45000, workers: 1,
  use: {
    storageState: {cookies: [], origins: [{origin: 'http://127.0.0.1:7081', localStorage: [{name: 'memorias-licantropicas:tutorial-seen', value: '1'}]}]},
    baseURL: 'http://127.0.0.1:7081', viewport: {width: 1440, height: 1000},
    launchOptions: {
      executablePath: process.env.BRAVE_PATH ?? '/usr/bin/brave-browser',
      args: ['--no-sandbox', '--disable-dev-shm-usage', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
    },
    screenshot: 'only-on-failure', trace: 'retain-on-failure',
  },
  webServer: [
    {command: '../.venv/bin/python ../tests/browser_server.py', url: 'http://127.0.0.1:17079/health', reuseExistingServer: false},
    {command: 'npm run dev', url: 'http://127.0.0.1:7081', env: {API_PROXY_TARGET: 'http://127.0.0.1:17079'}, reuseExistingServer: false},
  ],
});
