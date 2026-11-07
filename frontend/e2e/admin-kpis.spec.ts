import {test, expect} from '@playwright/test';

test('admin acompanha sessões e partidas sem disponibilizar escrita', async ({page}) => {
  const game = await (await page.request.post('/api/v1/games', {data: {}})).json();
  await page.goto('/'); // inicia a sessão de visita sem criar outra partida
  await expect.poll(async () => (await page.context().cookies()).some(cookie => cookie.name === 'ml_visit')).toBe(true);
  await page.reload();
  await page.goto('/admin.html');
  await page.locator('#username').fill('admin');
  await page.locator('#password').fill('browser-test-password');
  await page.locator('#login-button').click();
  await expect(page.locator('#application-kpis .stat-card')).toHaveCount(6);
  const metrics = await (await page.request.get('/admin/api/v1/metrics')).json();
  expect(metrics.connections).toBeGreaterThanOrEqual(1);
  expect(metrics.active_connections).toBeGreaterThanOrEqual(1);
  expect(metrics.games).toBe(metrics.won + metrics.lost + metrics.unfinished);
  expect(metrics.games).toBeGreaterThanOrEqual(1);
  const card = (label: string) => page.locator('#application-kpis .stat-card').filter({hasText: label});
  await expect(card('PARTIDAS INICIADAS')).toContainText(metrics.games.toLocaleString('pt-BR'));
  await expect(card('SEM DESFECHO')).toContainText(metrics.unfinished.toLocaleString('pt-BR'));
  expect(await page.locator('#application-kpis button, #application-kpis input, #application-kpis form').count()).toBe(0);
  const before = await (await page.request.get(`/admin/api/v1/games/${game.id}/state`)).json();
  await page.locator('#refresh').click();
  await expect(page.locator('#status')).toContainText('Arquivo atualizado');
  const after = await (await page.request.get(`/admin/api/v1/games/${game.id}/state`)).json();
  expect(after.investigation.revision).toBe(before.investigation.revision);
  expect((await page.request.post('/admin/api/v1/metrics', {data: {won: 100}})).status()).toBe(405);
  await page.locator('#logout').click();
  expect((await page.request.get('/admin/api/v1/metrics')).status()).toBe(401);
});
