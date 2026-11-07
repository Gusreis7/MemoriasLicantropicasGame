import {expect, test} from '@playwright/test';
import type {CasePublic, Location, WorldSnapshot} from '../shared/api';

const places: Location[] = [
  ['praca_verde', 'Praça Verde'], ['cabana_capitu', 'Cabana da Capitu'],
  ['casa_verde', 'Casa Verde'], ['cafe_largo', 'Café do Largo'], ['cais_lanternas', 'Cais das Lanternas'],
].map(([id, name]) => ({id: id as Location['id'], name, width: 960, height: 360, ground_y: 300,
  background: `/assets/locations/${id}.png`, exits: []}));

test('cinco locais usam manhã e pôr do sol; Floriano alterna o ciclo e para na borda', async ({page}) => {
  const errors: string[] = []; page.on('pageerror', error => errors.push(error.message));
  const midnightRequests = new Map<string, number>();
  page.on('request', request => {
    const path = new URL(request.url()).pathname;
    midnightRequests.set(path, (midnightRequests.get(path) ?? 0) + 1);
  });
  // Mount the production scene alone, with controlled time and movement hooks.
  await page.route('**/__visual_cycle__', route => route.fulfill({contentType: 'text/html', body: '<html><body style="margin:0"><main id="scene"></main></body></html>'}));
  await page.goto('/__visual_cycle__');
  await page.evaluate(async locations => {
    // @ts-expect-error Browser imports the actual Vite module.
    const {CityScene, makeGame} = await import('/game/scene.ts');
    const manifest = await (await fetch('/assets/characters/manifest.json')).json();
    const state = {progress: 0, x: 160, blocked: false, ready: false, frames: new Set<string>(), scene: null as any, game: null as any};
    (window as any).__visual = state;
    const world = {game_id: 'visual-cycle', world_version: '1', revision: 0, location: locations[0],
      player: {location_id: locations[0].id, x: 160, facing: 'right', movement_seq: 0}, visible_npcs: [], travel_targets: []};
    state.scene = new CityScene(manifest, locations, world, {
      dayProgress: () => state.progress, blocked: () => state.blocked,
      frame: (delta: number, direction: string) => {
        state.x = Math.max(32, Math.min(928, state.x + (direction === 'left' ? -1 : direction === 'right' ? 1 : 0) * 210 * Math.min(delta, 50) / 1000));
        const player = state.scene.children.getByName('player');
        if (player?.anims.isPlaying) state.frames.add(player.frame.name);
        return {x: state.x, facing: direction === 'left' ? 'left' : 'right'};
      },
      approach: () => {}, map: () => {}, loaded: () => {state.ready = true;},
      failed: () => {throw new Error('Falha ao carregar arte da cena');},
    });
    state.game = makeGame(document.querySelector('#scene'), state.scene);
  }, places);
  await expect.poll(() => page.evaluate(() => (window as any).__visual.ready), {timeout: 30000}).toBe(true);
  const nightURLs = await page.evaluate(async () => {
    // @ts-expect-error Browser imports the actual Vite module.
    const {assetURL} = await import('/shared/assets.ts');
    return ['praca_verde', 'cabana_capitu', 'casa_verde', 'cafe_largo', 'cais_lanternas'].map(id => assetURL(`/assets/locations/${id}-00h.png`));
  });
  expect(midnightRequests.get(nightURLs[0])).toBe(1);
  for (const url of nightURLs.slice(1)) expect(midnightRequests.get(url) ?? 0).toBe(0);
  const nightTexture = await page.evaluate(() => {
    const scene = (window as any).__visual.scene;
    return {key: scene.children.getByName('background-midnight').texture.key,
      duplicate: scene.textures.exists('midnight-praca_verde')};
  });
  expect(nightTexture).toEqual({key: 'location-praca_verde-00h', duplicate: false});
  for (const location of places) {
    for (const [hour, progress] of [['09h', 0], ['18h', 1]] as const) {
      await page.evaluate(({location, progress}) => {
        const state = (window as any).__visual; state.progress = progress;
        state.scene.apply({game_id: 'visual-cycle', world_version: '1', revision: 0, location,
          player: {location_id: location.id, x: state.x, facing: 'right', movement_seq: 0}, visible_npcs: [], travel_targets: []});
      }, {location, progress});
      await expect.poll(() => page.evaluate(() => (window as any).__visual.scene.children.getByName('background-sunset').alpha)).toBe(progress);
      await expect.poll(() => page.evaluate(() => (window as any).__visual.scene.loading)).toBe(false);
      const layers = await page.evaluate(() => {
        const scene = (window as any).__visual.scene;
        return ['background-morning', 'background-sunset'].map(name => {
          const layer = scene.children.getByName(name);
          return {key: layer.texture.key, x: layer.x, y: layer.y, width: layer.displayWidth, height: layer.displayHeight};
        });
      });
      expect(layers.map(layer => layer.key)).toEqual([`location-${location.id}-09h`, `location-${location.id}-18h`]);
      expect(layers.every(layer => layer.x === 0 && layer.y === 0 && layer.width === 960 && layer.height === 360)).toBe(true);
      await page.locator('canvas').screenshot({path: `../artifacts/lighting-${location.id}-${hour}.png`});
    }
  }
  await page.evaluate(() => {(window as any).__visual.progress = 5 / 6;});
  await expect.poll(() => page.evaluate(() => (window as any).__visual.scene.children.getByName('background-sunset').alpha)).toBeCloseTo(.5);
  await page.evaluate(() => {const s = (window as any).__visual; s.frames.clear(); s.scene.setTouchDirection('right');});
  await expect.poll(() => page.evaluate(() => (window as any).__visual.frames.size), {timeout: 3000}).toBe(8);
  expect(await page.evaluate(() => (window as any).__visual.x)).toBeGreaterThan(160);
  await page.evaluate(() => {(window as any).__visual.x = 928;});
  await expect.poll(() => page.evaluate(() => (window as any).__visual.scene.children.getByName('player').anims.isPlaying)).toBe(false);
  await page.evaluate(() => {(window as any).__visual.scene.setTouchDirection('left');});
  await expect.poll(() => page.evaluate(() => (window as any).__visual.scene.children.getByName('player').flipX)).toBe(true);
  await page.evaluate(() => {(window as any).__visual.blocked = true;});
  await expect.poll(() => page.evaluate(() => (window as any).__visual.scene.children.getByName('player').anims.isPlaying)).toBe(false);
  for (const url of nightURLs) expect(midnightRequests.get(url)).toBe(1);
  expect(errors).toEqual([]);
  await page.evaluate(() => {(window as any).__visual.game.destroy(true);});
});

test('toolbar traduz o prazo do servidor para hora do jogo e retoma após recarregar', async ({page}) => {
  const errors: string[] = []; page.on('pageerror', error => errors.push(error.message));
  const gameID = 'daylight-clock'; let remaining = 300;
  const world: WorldSnapshot = {game_id: gameID, world_version: '1', revision: 0, location: places[0],
    player: {location_id: places[0].id, x: 160, facing: 'right', movement_seq: 0}, visible_npcs: [], travel_targets: []};
  const state: CasePublic = {game_id: gameID, revision: 0, day: 1, phase: 'day', status: 'active',
    server_time: '', phase_ends_at: '', seconds_remaining: remaining,
    journal: [{day: 1, title: 'O Clarim do Rio', headline: 'O caso de Brás Cubas', body: 'Floriano inicia a investigação.', victim_id: null, victim_name: null, location_id: places[0].id, detention_outcome: 'none'}],
    crimes: [], inventory: [], testimonies: [], accusations: [], detained_npc_id: null, ending: null};
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname;
    const json = (data: unknown) => route.fulfill({json: data});
    if (path === '/api/v1/games') return json({id: gameID});
    if (path === '/api/v1/world/locations') return json(places);
    if (path === `/api/v1/games/${gameID}`) return json({id: gameID, status: 'active', characters: []});
    if (path.endsWith('/world')) return json(world);
    if (path.endsWith('/social/reports')) return json({reports: []});
    if (path.endsWith('/investigation')) return json({...state, server_time: new Date().toISOString(), phase_ends_at: new Date(Date.now() + remaining * 1000).toISOString(), seconds_remaining: remaining});
    return route.fulfill({status: 404, json: {detail: path}});
  });
  await page.goto('/'); await page.locator('#start').click();
  await expect(page.locator('#scene-loading')).toBeHidden({timeout: 30000});
  await page.locator('#read-journal').click();
  await expect(page.locator('#case-clock')).toHaveText(/09:0\d/);
  await expect(page.locator('#case-phase')).toHaveText('Investigue até as 18h');
  remaining = 150;
  await expect(page.locator('#case-clock')).toHaveText(/13:3\d/);
  remaining = 25;
  await expect(page.locator('#case-clock')).toHaveText(/17:1\d/);
  await page.screenshot({path: '../artifacts/lighting-clock-afternoon.png', fullPage: true});
  await page.reload(); await page.locator('#continue').click();
  await expect(page.locator('#scene-loading')).toBeHidden({timeout: 30000});
  await expect(page.locator('#case-clock')).toHaveText(/17:1\d/);
  expect(errors).toEqual([]);
});
