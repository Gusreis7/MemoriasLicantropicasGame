import {test, expect} from '@playwright/test';
import type {CasePublic, CaseEvidence, GamePublic, Location, WorldSnapshot} from '../shared/api';

/** Mock server exercises the actual notebook UI without inference or private state. */
async function setup(page: import('@playwright/test').Page, legacy = false) {
  const gameID = `discoveries-${legacy ? 'legacy' : 'v3'}`;
  const now = Date.now();
  const place: Location = {id: 'praca_verde', name: 'Praça Verde', width: 960, height: 360, ground_y: 300,
    background: '/assets/locations/praca_verde.png', exits: []};
  const cast: GamePublic = {id: gameID, status: 'active', characters: [{character: {id: 'rubiao', name: 'Rubião'}, alive: true}]};
  const world: WorldSnapshot = {game_id: gameID, world_version: '1', revision: 0, location: place,
    player: {location_id: place.id, x: 160, facing: 'right', movement_seq: 0}, visible_npcs: [], travel_targets: []};
  const inventory: CaseEvidence[] = legacy
    ? [{id: 'old-ev', crime_id: 'crime', item_id: 'botao', name: 'Botão de madrepérola', kind: 'unique', description: 'Um botão achado na cena.'}]
    : [1, 2].map(index => ({id: `personal-${index}`, crime_id: 'crime', item_id: 'rosario_seminario', name: 'Rosário do seminário', kind: 'unique', description: 'Um rosário guardado entre os pertences.'}));
  const state: CasePublic = {game_id: gameID, revision: 0, day: 1, phase: 'day', status: 'active',
    server_time: new Date(now).toISOString(), phase_ends_at: new Date(now + 300000).toISOString(), seconds_remaining: 300,
    journal: [{day: 1, title: 'O Clarim do Rio', headline: 'Brás Cubas encontrado morto', body: 'A cidade desperta.', victim_id: 'bras_cubas', victim_name: 'Brás Cubas', location_id: place.id, detention_outcome: 'none'}],
    crimes: [{id: 'crime', day: 0, victim_id: 'bras_cubas', victim_name: 'Brás Cubas', location_id: place.id, x: 600, remaining_clues: 0}],
    inventory, testimonies: [], accusations: [], detained_npc_id: null, ending: null,
    ...(legacy ? {} : {achievements: [], achievement_total: 7})};
  let inspectCalls = 0;
  await page.route('**/api/v1/**', async route => {
    const request = route.request(); const path = new URL(request.url()).pathname;
    const body = request.method() === 'POST' ? request.postDataJSON() : undefined;
    const json = (data: unknown) => route.fulfill({json: data});
    if (path === '/api/v1/games' && body) return json({id: gameID});
    if (path === '/api/v1/world/locations') return json([place]);
    if (path === `/api/v1/games/${gameID}`) return json(cast);
    if (path.endsWith('/investigation')) {
      state.server_time = new Date().toISOString();
      state.seconds_remaining = Math.max(0, (Date.parse(state.phase_ends_at) - Date.now()) / 1000);
      return json(state);
    }
    if (path.endsWith('/world')) return json(world);
    if (path.endsWith('/inspect') && request.method() === 'POST') {
      inspectCalls++;
      expect(path).toBe(`/api/v1/games/${gameID}/evidence/personal-1/inspect`);
      expect(body).toEqual({});
      state.inventory[0] = {...state.inventory[0], examined: true, inspection_text: 'Fios de cobre prendem uma medalhinha ao rosário.'};
      state.achievements = [{id: 'personal_trace', title: 'Rastro pessoal', description: 'Um objeto íntimo revela uma marca de seu dono.', unlocked_at: new Date().toISOString()}];
      state.revision++;
      return json(state);
    }
    return route.fulfill({status: 404, json: {detail: `Rota não prevista: ${path}`} });
  });
  return {gameID, state, inspectCalls: () => inspectCalls};
}

async function openNotebook(page: import('@playwright/test').Page) {
  await page.goto('/');
  await page.locator('#start').click();
  await expect(page.locator('#scene-loading')).toBeHidden({timeout: 30000});
  await expect(page.locator('#journal-overlay')).toBeVisible();
  await page.locator('#read-journal').click();
  await page.locator('#open-notebook').click();
  await expect(page.locator('#notebook-overlay')).toBeVisible();
}

test('examina um objeto pessoal agrupado, libera a descoberta uma vez e não revela segredos bloqueados', async ({page}) => {
  const fixture = await setup(page);
  const errors: string[] = []; page.on('pageerror', error => errors.push(error.message));
  await openNotebook(page);
  await expect(page.locator('.evidence-card')).toHaveCount(1);
  await expect(page.locator('.evidence-card .item-stack-count')).toHaveText('×2');
  await expect(page.locator('.evidence-card .personal-trace-stamp')).toContainText('Rastro pessoal');
  const examine = page.getByRole('button', {name: 'Examinar: Rosário do seminário'});
  await expect(examine).toHaveCount(1);
  const response = page.waitForResponse(r => r.url().endsWith('/evidence/personal-1/inspect') && r.request().method() === 'POST');
  await examine.dblclick();
  expect((await response).status()).toBe(200);
  await expect(page.locator('.inspection-result')).toHaveText('Fios de cobre prendem uma medalhinha ao rosário.');
  await expect(page.locator('.evidence-inspect')).toHaveText('Examinado');
  await expect(page.locator('#achievement-progress')).toHaveText('1 / 7 descobertas');
  await expect(page.locator('.achievement-seal[data-achievement-id="personal_trace"]')).toHaveCount(1);
  await expect(page.locator('#toast')).toContainText('Rastro pessoal');
  await expect(page.locator('.achievement-seal')).toHaveCount(1);
  await expect(page.locator('.achievement-list')).not.toContainText(/segredo|identidade|conquista oculta/i);
  await expect.poll(fixture.inspectCalls).toBe(1);
  await expect(page.locator('#toast')).toBeHidden({timeout: 6500}); // Poll snapshots with the same unlock must not restart the toast.
  await expect(page.locator('.achievement-seal')).toHaveCount(1);
  expect(errors).toEqual([]);
});

test('snapshot antigo sem campos de exame ou conquistas mantém o caderno funcional', async ({page}) => {
  await setup(page, true);
  const errors: string[] = []; page.on('pageerror', error => errors.push(error.message));
  await openNotebook(page);
  await expect(page.locator('.evidence-card')).toHaveCount(1);
  await expect(page.locator('.evidence-inspect')).toHaveText('Examinar');
  await expect(page.locator('#achievements-section')).toBeHidden();
  expect(errors).toEqual([]);
});
