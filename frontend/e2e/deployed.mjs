// Verificação manual do build Docker no Brave. Não instala navegador.
import { chromium } from '@playwright/test';
import { readFileSync, mkdirSync } from 'node:fs';
import assert from 'node:assert/strict';

const envFile = readFileSync('../.env', 'utf8');
const value = key => process.env[key] ?? envFile.split('\n').find(line => line.startsWith(key + '='))?.slice(key.length + 1).trim();
const browser = await chromium.launch({executablePath: process.env.BRAVE_PATH ?? '/usr/bin/brave-browser',
  args: ['--no-sandbox', '--disable-dev-shm-usage', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']});
const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
const errors = [];
page.on('pageerror', error => errors.push(error.message));
mkdirSync('../artifacts', {recursive: true});
try {
  await page.goto('http://localhost:7077');
  await page.locator('#start').click();
  await page.locator('#scene-loading').waitFor({state: 'hidden', timeout: 30000});
  await page.locator('canvas').click();
  await page.keyboard.down('ArrowRight');
  await page.locator('#approach').waitFor({state: 'visible', timeout: 10000});
  await page.keyboard.up('ArrowRight');
  await page.locator('#approach').click();
  await page.locator('#message-input').waitFor({state: 'visible'});
  await page.waitForFunction(() => !document.querySelector('#message-input').disabled);
  if (process.env.REAL_LLM_SMOKE === '1') {
    await page.locator('#message-input').fill('Boa tarde. Como devo chamá-lo? Responda brevemente.');
    await page.locator('#send-message').click();
    await page.waitForFunction(() => !document.querySelector('#send-message').disabled, undefined, {timeout: 130000});
    assert.equal(await page.locator('.message.npc').count(), 1, await page.locator('#dialogue-status').textContent());
    await page.locator('.message.npc').waitFor({state: 'visible', timeout: 130000});
    console.log('Uma resposta real da persona foi recebida e persistida.');
  }
  await page.screenshot({path: '../artifacts/deployed-dialogue.png', fullPage: true});
  const gameID = await page.evaluate(() => localStorage.getItem('memorias-licantropicas:game'));
  assert.equal((await page.request.get('http://localhost:7077/admin/api/v1/games')).status(), 404);
  await page.goto('http://localhost:7078');
  await page.locator('#login-view').waitFor({state: 'visible'});
  assert.equal((await page.request.get('http://localhost:7078/admin/api/v1/games')).status(), 401);
  await page.locator('#username').fill(value('ADMIN_USERNAME') || 'admin');
  await page.locator('#password').fill(value('ADMIN_PASSWORD'));
  await page.locator('#login-button').click();
  await page.locator('#dashboard').waitFor({state: 'visible'});
  await page.locator(`[data-game-id="${gameID}"]`).click();
  await page.locator('.character-card').first().waitFor({state: 'visible'});
  assert.equal(await page.locator('.character-card').count(), 7);
  assert.equal(await page.locator('.role-badge.wolf').count(), 1);
  await page.screenshot({path: '../artifacts/deployed-admin.png', fullPage: true});
  await page.locator('#logout').click();
  await page.locator('#login-view').waitFor({state: 'visible'});
  assert.deepEqual(errors, []);
  console.log('Build Docker verificado no Brave: jogo7077, admin7078, bloqueios, login, estado e logout OK.');
} finally {
  await browser.close();
}
