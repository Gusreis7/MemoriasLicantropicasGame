import {test, expect} from '@playwright/test';
import type {CasePublic, GamePublic, Location, WorldSnapshot} from '../shared/api';

/** Contract-level UI fixture: no inference and no private character data in the browser. */
async function cityFixture(page: import('@playwright/test').Page) {
  const now = Date.now();
  const names = {rubiao: 'Rubião', capitu: 'Capitu', escobar: 'Escobar', bentinho: 'Bentinho', virgilia: 'Virgília Neves', florenca: 'Florença', bacamarte: 'Dr. Bacamarte'};
  const cast: GamePublic = {id: 'case-ui', status: 'active', characters: Object.entries(names).map(([id, name]) => ({character: {id, name}, alive: true}))};
  const place: Location = {id: 'praca_verde', name: 'Praça Verde', width: 960, height: 360, ground_y: 300, background: '/assets/locations/praca_verde.png', exits: [
    {side: 'left', target_location_id: 'cabana_capitu', arrival_side: 'right'}, {side: 'right', target_location_id: 'cais_lanternas', arrival_side: 'left'},
  ]};
  const world: WorldSnapshot = {game_id: cast.id, world_version: '1', revision: 0, location: place,
    player: {location_id: place.id, x: 160, facing: 'right', movement_seq: 0},
    visible_npcs: [{npc_id: 'rubiao', name: 'Rubião', x: 440, sprite_id: 'rubiao', can_approach: false}], travel_targets: ['cais_lanternas']};
  const state: CasePublic = {game_id: cast.id, revision: 0, day: 1, phase: 'day', status: 'active',
    server_time: new Date(now).toISOString(), phase_ends_at: new Date(now + 300000).toISOString(), seconds_remaining: 300,
    journal: [{day: 1, title: 'O Clarim do Rio', headline: 'Brás Cubas encontrado morto', body: 'A cidade desperta com a notícia do crime na praça.', victim_id: 'bras_cubas', victim_name: 'Brás Cubas', location_id: 'praca_verde', detention_outcome: 'none'}],
    crimes: [{id: 'crime-ui', day: 0, victim_id: 'bras_cubas', victim_name: 'Brás Cubas', location_id: 'praca_verde', x: 600, remaining_clues: 2}],
    inventory: [], testimonies: [], accusations: [], detained_npc_id: null, ending: null};
  let previousDirection = 'idle'; let movementCalls = 0;
  const requests: Array<{path: string; body: unknown}> = [];
  const json = (route: import('@playwright/test').Route, body: unknown) => route.fulfill({json: body});
  await page.route('**/api/v1/**', async route => {
    const request = route.request(); const path = new URL(request.url()).pathname;
    const body = request.method() === 'POST' ? request.postDataJSON() : undefined;
    requests.push({path, body});
    if (path === '/api/v1/games' && body) return json(route, {id: cast.id});
    if (path === '/api/v1/world/locations') return json(route, [place]);
    if (path === `/api/v1/games/${cast.id}`) return json(route, cast);
    if (path.endsWith('/investigation')) {
      state.server_time = new Date().toISOString(); state.seconds_remaining = Math.max(0, (Date.parse(state.phase_ends_at) - Date.now()) / 1000);
      return json(route, state);
    }
    if (path.endsWith('/world')) return json(route, world);
    if (path.endsWith('/movement')) {
      movementCalls++;
      world.player.x = Math.max(32, Math.min(928, world.player.x + (previousDirection === 'right' ? 40 : previousDirection === 'left' ? -40 : 0)));
      previousDirection = body.direction; world.player.movement_seq = body.seq; world.revision++;
      if (body.direction !== 'idle') world.player.facing = body.direction;
      return json(route, world);
    }
    if (path.endsWith('/search')) {
      const index = state.inventory.length;
      state.inventory.push({id: `ev-${index + 1}`, crime_id: 'crime-ui', item_id: index ? 'ribbon' : 'handkerchief', name: index ? 'Fita de veludo' : 'Lenço de algodão', kind: index ? 'singular' : 'common', description: 'Vestígio encontrado junto à cena.'});
      state.crimes[0].remaining_clues--; state.revision++;
      return json(route, state);
    }
    if (path.endsWith('/approaches')) return json(route, {id: 'conversation-ui', game_id: cast.id, npc_id: body.npc_id, created_at: new Date().toISOString()});
    if (path.endsWith('/messages')) return json(route, {conversation_id: 'conversation-ui', messages: []});
    if (path.endsWith('/present')) {
      state.testimonies = [{id: 'testimony-ui', day: state.day, evidence_id: 'ev-2', witness_id: 'rubiao', witness_name: 'Rubião', recognition: 'recognizes', claimed_owner_id: 'capitu', text: 'Reconheço esta fita; já a vi com Capitu.'}];
      state.revision++; return json(route, state);
    }
    if (path.endsWith('/accusations')) {
      state.accusations.push({id: 'accusation-ui', day: state.day, suspect_id: body.suspect_id, suspect_name: 'Capitu', evidence_ids: body.evidence_ids, testimony_ids: body.testimony_ids, accepted: true, reason: 'Há elementos suficientes para uma detenção nesta noite.'});
      state.detained_npc_id = 'capitu'; state.revision++; return json(route, state);
    }
    return route.fulfill({status: 404, json: {detail: 'Rota não prevista no contrato do teste.'}});
  });
  return {state, world, cast, requests, movementCalls: () => movementCalls};
}

async function begin(page: import('@playwright/test').Page) {
  await page.goto('/'); await page.locator('#start').click();
  await expect(page.locator('#scene-loading')).toBeHidden({timeout: 30000});
  await expect(page.locator('#journal-overlay')).toBeVisible();
  await expect(page.locator('#journal-title')).toHaveText('O Clarim do Rio');
  await page.locator('#read-journal').click();
}

test('busca, apresenta vestígios e pede detenção antes de aguardar a noite', async ({page}) => {
  const city = await cityFixture(page); await begin(page);
  await expect(page.locator('#case-clock')).toHaveText(/04:5\d|05:00/);
  await page.locator('canvas').click(); await page.keyboard.down('ArrowRight');
  await expect(page.locator('#inspect-crime')).toBeVisible({timeout: 8000}); await page.keyboard.up('ArrowRight');
  await page.locator('#inspect-crime').click();
  await expect(page.locator('#evidence-count')).toHaveText('1 pista');
  await page.locator('#inspect-crime').click();
  await expect(page.locator('#evidence-count')).toHaveText('2 pistas');
  await page.keyboard.down('ArrowLeft');
  await expect.poll(() => city.world.player.x, {timeout: 8000, intervals: [25]}).toBeLessThanOrEqual(480);
  await page.keyboard.up('ArrowLeft'); await expect(page.locator('#approach')).toBeVisible();
  await page.locator('#approach').click(); await expect(page.locator('#message-input')).toBeEnabled();
  await page.locator('#present-evidence').selectOption('ev-2'); await page.locator('#present-button').click();
  await expect(page.locator('#presentation-status')).toContainText('já a vi com Capitu');
  await expect(page.locator('#close-dialogue')).toBeInViewport(); await page.locator('#close-dialogue').click();
  await page.locator('#open-notebook').click(); await expect(page.locator('.evidence-card')).toHaveCount(2);
  await expect(page.locator('#testimony-list')).toContainText('Rubião'); await page.locator('#close-notebook').click();
  await page.locator('#open-delegate').click(); await page.locator('#accused-npc').selectOption('capitu');
  for (const input of await page.locator('#accusation-evidence input').all()) await input.check();
  await page.locator('#accusation-testimonies input').check();
  await page.locator('#submit-accusation').click(); await expect(page.locator('#accusation-status')).toContainText('detenção');
  expect(city.requests.find(request => request.path.endsWith('/accusations'))?.body).toEqual({suspect_id: 'capitu', evidence_ids: ['ev-1', 'ev-2'], testimony_ids: ['testimony-ui']});
  city.state.phase = 'night'; city.state.revision++; city.state.phase_ends_at = new Date(Date.now() + 8000).toISOString();
  await expect(page.locator('#phase-overlay')).toBeVisible({timeout: 5000});
  await expect(page.locator('#open-map')).toBeDisabled(); const calls = city.movementCalls();
  await page.keyboard.press('Escape'); await page.keyboard.down('ArrowRight'); await page.waitForTimeout(350); await page.keyboard.up('ArrowRight');
  expect(city.movementCalls()).toBe(calls); await expect(page.locator('#phase-overlay')).toBeVisible();
  city.state.phase = 'finished'; city.state.status = 'won'; city.state.revision++;
  city.state.ending = {result: 'won', message: 'A transformação foi testemunhada na cela. A cidade expulsou o lobisomem.', werewolf_id: 'capitu'};
  await expect(page.locator('#phase-title')).toHaveText('O lobisomem foi descoberto.', {timeout: 5000});
  await expect(page.locator('#phase-description')).toContainText('expulsou'); await expect(page.locator('#ending-new-case')).toBeVisible();
});

test('amanhecer retorna à banca e publica a morte sem manter o NPC no cenário', async ({page}) => {
  const city = await cityFixture(page); await begin(page);
  city.state.phase = 'night'; city.state.revision++; city.state.phase_ends_at = new Date(Date.now() + 8000).toISOString();
  await expect(page.locator('#phase-overlay')).toBeVisible({timeout: 5000});
  city.state.phase = 'day'; city.state.day = 2; city.state.revision++; city.state.phase_ends_at = new Date(Date.now() + 300000).toISOString();
  city.state.journal.push({day: 2, title: 'O Clarim do Rio', headline: 'Rubião é encontrado morto', body: 'A manhã traz uma nova perda à praça.', victim_id: 'rubiao', victim_name: 'Rubião', location_id: 'praca_verde', detention_outcome: 'none'});
  city.world.player.x = 160; city.world.visible_npcs = []; city.world.revision++;
  city.cast.characters.find(member => member.character.id === 'rubiao')!.alive = false;
  await expect(page.locator('#journal-overlay')).toBeVisible({timeout: 5000});
  await expect(page.locator('#journal-headline')).toHaveText('Rubião é encontrado morto');
  await expect(page.locator('#case-day')).toHaveText('DIA 2'); await expect(page.locator('#location-name')).toHaveText('Praça Verde');
  await page.locator('#read-journal').click(); await expect(page.locator('#phase-overlay')).toBeHidden();
  await expect(page.locator('#approach')).toBeHidden(); await expect(page.locator('#open-map')).toBeEnabled();
});
