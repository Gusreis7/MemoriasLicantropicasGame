import {test, expect} from '@playwright/test';
import type {CasePublic, GamePublic, Location, Message, WorldSnapshot} from '../shared/api';

/** Contract-level UI fixture: no inference and no private character data in the browser. */
async function cityFixture(page: import('@playwright/test').Page) {
  const now = Date.now();
  const names = {rubiao: 'Rubião', capitu: 'Capitu', escobar: 'Escobar', bentinho: 'Bentinho', virgilia: 'Virgília Neves', florenca: 'Florença', bacamarte: 'Dr. Bacamarte'};
  const cast: GamePublic = {id: 'case-ui', status: 'active', characters: Object.entries(names).map(([id, name]) => ({character: {id, name, grammatical_gender: ['capitu','virgilia','florenca'].includes(id) ? 'feminine' : 'masculine'}, alive: true}))};
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
  const messages: Message[] = [];
  let previousDirection = 'idle'; let movementCalls = 0;
  const requests: Array<{path: string; body: unknown}> = [];
  const json = (route: import('@playwright/test').Route, body: unknown) => route.fulfill({json: body});
  await page.route('**/api/v1/**', async route => {
    const request = route.request(); const path = new URL(request.url()).pathname;
    const body = request.method() === 'POST' ? request.postDataJSON() : undefined;
    requests.push({path, body});
    if (path === '/api/v1/games' && body) return json(route, {id: cast.id});
    if (path === '/api/v1/world/locations') return json(route, [place, {...place,id:'cais_lanternas',name:'Cais das Lanternas'}]);
    if (path === `/api/v1/games/${cast.id}`) return json(route, cast);
    if (path.endsWith('/investigation')) {
      state.server_time = new Date().toISOString(); state.seconds_remaining = Math.max(0, (Date.parse(state.phase_ends_at) - Date.now()) / 1000);
      return json(route, state);
    }
    if (path.endsWith('/investigation/skip-day')) {
      state.day++; state.revision++; state.phase_ends_at = new Date(Date.now() + 300000).toISOString();
      state.journal.push({day: state.day, title: 'O Clarim do Rio', headline: 'Uma nova manhã na cidade', body: 'A noite revelou uma nova vítima.', victim_id: 'rubiao', victim_name: 'Rubião', location_id: 'praca_verde', detention_outcome: 'none'});
      cast.characters.find(member => member.character.id === 'rubiao')!.alive = false;
      world.visible_npcs = []; world.revision++; world.player.x = 160;
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
    if (path.endsWith('/messages')) {
      if (request.method() === 'POST') {
        messages.push({id:`m-${messages.length}`,speaker:'player',content:body.content,created_at:new Date().toISOString()});
        const confessing = body.content.includes('admita');
        const answer = confessing ? 'Confesso minha condição e me entrego ao delegado.' : 'Estava na praça, sozinho, lendo o jornal.';
        messages.push({id:`m-${messages.length}`,speaker:'npc',content:answer,created_at:new Date().toISOString()});
        state.revision++;
        if (confessing) {state.status='won';state.phase='finished';state.ending={result:'won',werewolf_id:'rubiao',method:'confession',message:'O morador confessou sua condição e se entregou ao delegado.'};}
        else state.interrogations=[{id:'alibi-ui',npc_id:'rubiao',npc_name:'Rubião',day:0,period:'night',location_id:'praca_verde',companion_ids:[],activity:'Lia o jornal.',text:answer,observations:[]}];
        return json(route,{conversation_id:'conversation-ui',message:messages.at(-1)});
      }
      return json(route, {conversation_id: 'conversation-ui', messages});
    }
    if (path.endsWith('/present')) {
      state.testimonies = [{id: 'testimony-ui', day: state.day, evidence_id: 'ev-2', witness_id: 'rubiao', witness_name: 'Rubião', recognition: 'recognizes', claimed_owner_id: 'capitu', text: 'Reconheço esta fita; já a vi com Capitu.'}];
      messages.push({id:`m-${messages.length}`,speaker:'player',content:'Mostro a fita ao morador.',created_at:new Date().toISOString()});
      messages.push({id:`m-${messages.length}`,speaker:'npc',content:state.testimonies[0].text,created_at:new Date().toISOString()});
      state.revision++; return json(route, state);
    }
    if (path.endsWith('/assembly')) {
      state.assembly = {suspect_id: body.suspect_id, day: 1, required_votes: 5, expelled: true, outcome: 'innocent',
        votes: Object.keys(names).map(voter_id => ({voter_id, expel: true, reason: 'Os registros apresentados sustentam o pedido.'}))};
      state.expelled_npc_ids = [body.suspect_id]; state.revision++; return json(route, state);
    }
    if (path.endsWith('/accusations')) {
      state.accusations.push({id: 'accusation-ui', day: state.day, suspect_id: body.suspect_id, suspect_name: 'Capitu', evidence_ids: body.evidence_ids, testimony_ids: body.testimony_ids, accepted: true, reason: 'Há elementos suficientes para uma detenção nesta noite.'});
      state.detained_npc_id = 'capitu'; state.revision++; return json(route, state);
    }
    if (path.endsWith('/interrogations')) {
      state.interrogations = [{id: 'alibi-ui', npc_id: body.npc_id, npc_name: 'Rubião', day: body.day, period: body.period,
        location_id: 'praca_verde', companion_ids: [], activity: 'Lia o jornal.', text: 'Estava na praça, sozinho, lendo o jornal.', observations: []}];
      state.revision++; return json(route, state);
    }
    if (path.endsWith('/confrontations')) {
      state.confrontations = [{id: 'confront-ui', npc_id: body.npc_id, day: state.day, evidence_ids: body.evidence_ids,
        testimony_ids: body.testimony_ids, interrogation_ids: body.interrogation_ids, confessed: true, text: 'Admito minha condição.'}];
      state.status = 'won'; state.phase = 'finished'; state.revision++;
      state.ending = {result: 'won', werewolf_id: body.npc_id, method: 'confession', message: 'O morador confessou sua condição diante dos registros apresentados.'};
      return json(route, state);
    }
    return route.fulfill({status: 404, json: {detail: 'Rota não prevista no contrato do teste.'}});
  });
  return {state, world, cast, requests, movementCalls: () => movementCalls};
}

async function begin(page: import('@playwright/test').Page) {
  await page.goto('/'); await page.locator('#start').click();
  await expect(page.locator('#scene-loading')).toBeHidden({timeout: 30000});
  await expect(page.locator('#journal-overlay:visible, #custody-overlay:visible')).toBeVisible();
  if(await page.locator('#custody-overlay').isVisible()) {await page.locator('#leave-custody').click();}
  else {await expect(page.locator('#journal-overlay')).toBeVisible();
  await expect(page.locator('#journal-title')).toHaveText('O Clarim do Rio');
  await page.locator('#read-journal').click();}
}

test('busca, apresenta vestígios e pede detenção antes de aguardar a noite', async ({page}) => {
  const city = await cityFixture(page); await begin(page);
  await expect(page.locator('#case-clock')).toHaveText(/09:[0-2]\d/);
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
  await expect(page.locator('#messages')).toContainText('já a vi com Capitu');
  await expect(page.locator('#close-dialogue')).toBeInViewport(); await page.locator('#close-dialogue').click();
  await page.locator('#open-notebook').click(); await expect(page.locator('.evidence-card')).toHaveCount(2);
  await expect(page.locator('#testimony-list')).toContainText('Rubião'); await page.locator('#close-notebook').click();
  await page.locator('#open-delegate').click(); await page.getByRole('radio', {name: /Capitu/}).check();
  for (const input of await page.locator('#accusation-evidence input').all()) await input.check();
  await page.locator('#accusation-testimonies input').check();
  await page.locator('#submit-accusation').click(); await expect(page.locator('#accusation-status')).toContainText('detenção');
  expect(city.requests.find(request => request.path.endsWith('/accusations'))?.body).toEqual({suspect_id: 'capitu', evidence_ids: ['ev-1', 'ev-2'], testimony_ids: ['testimony-ui']});
  city.state.phase = 'night'; city.state.revision++; city.state.phase_ends_at = new Date(Date.now() + 8000).toISOString();
  await expect(page.locator('#custody-overlay')).toBeVisible({timeout: 5000});
  await expect(page.locator('#open-map')).toBeDisabled(); const calls = city.movementCalls();
  await page.keyboard.press('Escape'); await page.keyboard.down('ArrowRight'); await page.waitForTimeout(350); await page.keyboard.up('ArrowRight');
  expect(city.movementCalls()).toBe(calls); await expect(page.locator('#custody-overlay')).toBeVisible();
  city.state.phase = 'finished'; city.state.status = 'won'; city.state.revision++;
  city.state.ending = {result: 'won', method:'detention', message: 'A transformação foi testemunhada na cela. A cidade expulsou o lobisomem.', werewolf_id: 'capitu'};
  await expect(page.locator('#custody-title')).toContainText('verdade');
  await page.waitForTimeout(1700);
  await page.screenshot({path:'../artifacts/custody-transformation.png',fullPage:true});
  await expect(page.locator('#phase-title')).toHaveText('O lobisomem foi descoberto.', {timeout: 10000});
  await expect(page.locator('#victory-paper')).toBeVisible();
  await expect(page.locator('#victory-headline')).toContainText('Floriano');
  await page.screenshot({path:'../artifacts/clarim-victory.png',fullPage:true});
  await expect(page.locator('#phase-description')).toContainText('expulsou'); await expect(page.locator('#ending-new-case')).toBeVisible();
});

for (const width of [1440, 390]) {
  test(`pular o dia abre o jornal da manhã seguinte em ${width}px`, async ({page}) => {
    await page.setViewportSize({width, height: 1000});
    const city = await cityFixture(page); await begin(page);
    await page.locator('#skip-day').click();
    await expect(page.locator('#night-attack-overlay')).toBeVisible();
    await page.locator('#night-attack-overlay button').click();
    await expect(page.locator('#journal-overlay')).toBeVisible();
    await expect(page.locator('#journal-headline')).toHaveText('Uma nova manhã na cidade');
    await expect(page.locator('#case-day')).toHaveText('DIA 2');
    await expect(page.locator('#case-clock')).toHaveText(/09:[0-1]\d/);
    expect(city.requests.filter(request => request.path.endsWith('/skip-day')).map(request => request.body)).toEqual([{day: 1}]);
    await page.locator('#read-journal').click();
    await expect(page.locator('#skip-day')).toBeEnabled();
    expect(city.cast.characters.find(member => member.character.id === 'rubiao')?.alive).toBe(false);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}

test('falha ao pular o dia permite tentar novamente sem avançar localmente', async ({page}) => {
  const city = await cityFixture(page); await begin(page);
  await page.route('**/investigation/skip-day', route => route.fulfill({status: 503, json: {detail: 'A cidade está indisponível.'}}));
  await page.locator('#skip-day').click();
  await expect(page.locator('#toast')).toContainText('A cidade está indisponível.');
  await expect(page.locator('#skip-day')).toBeEnabled();
  await expect(page.locator('#case-day')).toHaveText('DIA 1');
  expect(city.state.day).toBe(1);
});

test('quarta vítima encerra o caso com a edição de derrota do Clarim', async ({page}) => {
  await page.addInitScript(() => {
    const play=HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play=function() {
      const photo=document.querySelector<HTMLImageElement>('#defeat-photo');
      if(this.src.includes('/werewolf/howl-long.ogg') && photo && !photo.hidden) document.documentElement.dataset.defeatHowls=String(Number(document.documentElement.dataset.defeatHowls ?? 0)+1);
      return play.call(this);
    };
  });
  const city = await cityFixture(page); await begin(page);
  city.state.day = 5; city.state.phase = 'finished'; city.state.status = 'lost'; city.state.revision++;
  city.state.ending = {result: 'lost', method: 'survival', werewolf_id: 'bentinho', message: 'Floriano não conseguiu deter o lobisomem a tempo. A besta-fera venceu.'};
  city.state.journal.push({day: 5, title: 'O Clarim do Rio', headline: 'Floriano não chegou a tempo: a besta-fera venceu', body: 'Quatro dos sete moradores foram mortos pelo lobisomem. Floriano não conseguiu deter a fera a tempo.', victim_id: 'rubiao', victim_name: 'Rubião', location_id: 'praca_verde', detention_outcome: 'none', illustration: 'crime_street'});
  await expect(page.locator('#night-attack-overlay')).toBeVisible();
  await page.locator('#night-attack-overlay button').click();
  await expect(page.locator('#victory-paper')).toBeVisible({timeout: 10000});
  await expect(page.locator('#victory-headline')).toHaveText('Floriano não chegou a tempo: a besta-fera venceu');
  await expect(page.locator('#victory-body')).toContainText('Quatro dos sete moradores');
  await expect(page.locator('#victory-paper .press-picture')).toBeHidden();
  await expect(page.locator('#defeat-photo')).toBeVisible();
  await expect(page.locator('#defeat-photo')).toHaveAttribute('data-loaded','true');
  await expect(page.locator('html')).toHaveAttribute('data-defeat-howls','1');
  await page.screenshot({path:'../artifacts/clarim-defeat.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:'../artifacts/clarim-defeat-mobile.png',fullPage:true});
  await expect(page.locator('#ending-new-case')).toBeVisible();
  await expect(page.locator('#open-map')).toBeDisabled();
  await expect(page.locator('#skip-day')).toBeDisabled();
});

test('amanhecer retorna à banca e publica a morte sem manter o NPC no cenário', async ({page}) => {
  await page.addInitScript(() => {
    const play=HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play=function() {
      if(this.src.includes('/werewolf/howl-long.ogg')) document.documentElement.dataset.howlBeat=document.querySelector<HTMLElement>('#night-attack-overlay')?.dataset.beat;
      return play.call(this);
    };
  });
  const audioFiles: string[] = [];
  page.on('response', response => {if(response.url().includes('/assets/audio/') && response.ok()) audioFiles.push(response.url());});
  const city = await cityFixture(page); await begin(page);
  city.state.phase = 'night'; city.state.revision++; city.state.phase_ends_at = new Date(Date.now() + 8000).toISOString();
  await expect(page.locator('#phase-overlay')).toBeVisible({timeout: 5000});
  city.state.phase = 'day'; city.state.day = 2; city.state.revision++; city.state.phase_ends_at = new Date(Date.now() + 300000).toISOString();
  city.state.journal.push({day: 2, title: 'O Clarim do Rio', headline: 'Rubião é encontrado morto', body: 'A manhã traz uma nova perda à praça.', victim_id: 'rubiao', victim_name: 'Rubião', location_id: 'praca_verde', detention_outcome: 'none'});
  city.world.player.x = 160; city.world.visible_npcs = []; city.world.revision++;
  city.cast.characters.find(member => member.character.id === 'rubiao')!.alive = false;
  await expect(page.locator('#night-attack-overlay')).toBeVisible({timeout: 5000});
  await expect(page.locator('#night-attack-overlay')).toHaveAttribute('data-strike', '0');
  await expect(page.locator('#night-attack-overlay')).toHaveAttribute('data-fallen-victim', 'rubiao');
  await expect(page.locator('#journal-overlay')).toBeHidden();
  const firstFrame = await page.locator('#night-attack-overlay').getAttribute('data-wolf-walk-frame');
  await expect.poll(() => page.locator('#night-attack-overlay').getAttribute('data-wolf-walk-frame')).not.toBe(firstFrame);
  await expect(page.locator('#night-attack-overlay')).toHaveAttribute('data-beat', 'strike');
  await expect(page.locator('#night-attack-overlay')).toHaveAttribute('data-beat', 'fallen');
  await page.screenshot({path:'../artifacts/night-fallen.png',fullPage:true});
  await expect(page.locator('#night-attack-overlay')).toHaveAttribute('data-beat', 'escape');
  await page.screenshot({path:'../artifacts/night-escape.png',fullPage:true});
  await expect(page.locator('#night-attack-overlay')).toBeHidden({timeout: 8000});
  expect(audioFiles.some(url=>url.includes('day-birds'))).toBe(true);
  expect(audioFiles.some(url=>url.includes('night-ominous'))).toBe(true);
  expect(audioFiles.some(url=>url.includes('knifeSlice'))).toBe(true);
  expect(audioFiles.some(url=>url.includes('werewolf/howl'))).toBe(true);
  expect(audioFiles.some(url=>url.includes('werewolf/impact-1'))).toBe(true);
  await expect(page.locator('html')).toHaveAttribute('data-howl-beat','strike');
  await expect(page.locator('#journal-overlay')).toBeVisible({timeout: 5000});
  await expect(page.locator('#journal-headline')).toHaveText('Rubião é encontrado morto');
  await expect(page.locator('#case-day')).toHaveText('DIA 2'); await expect(page.locator('#location-name')).toHaveText('Praça Verde');
  await page.locator('#read-journal').click(); await expect(page.locator('#phase-overlay')).toBeHidden();
  await expect(page.locator('#approach')).toBeHidden(); await expect(page.locator('#open-map')).toBeEnabled();
});

test('pergunta e confronta pela conversa, registra a versão e recebe a conclusão do mestre', async ({page}) => {
  const city = await cityFixture(page); city.world.visible_npcs[0].x = 190; city.world.visible_npcs[0].can_approach = true;
  await begin(page); await page.locator('#approach').click(); await expect(page.locator('#message-input')).toBeEnabled();
  await expect(page.locator('#interrogation-panel')).toHaveCount(0);
  await page.locator('#message-input').fill('Onde estava na noite de ontem?'); await page.locator('#send-message').click();
  await expect(page.locator('#messages')).toContainText('Estava na praça');
  await page.locator('#close-dialogue').click(); await page.locator('#open-notebook').click();
  await expect(page.locator('#interrogation-list')).toContainText('Rubião · noite 0');
  await page.locator('#close-notebook').click(); await page.locator('#approach').click(); await expect(page.locator('#message-input')).toBeEnabled();
  await page.locator('#message-input').fill('Sua versão contradiz os registros; admita o que fez e se entregue.'); await page.locator('#send-message').click();
  await expect(page.locator('#phase-overlay')).toBeVisible(); await expect(page.locator('#phase-description')).toContainText('confessou');
  expect(city.requests.filter(request => request.path.endsWith('/interrogations') || request.path.endsWith('/confrontations'))).toHaveLength(0);
});

test('delegado apresenta retratos, exige escolha e distingue moradores indisponíveis em desktop e celular', async ({page}) => {
  const city = await cityFixture(page);
  city.cast.characters.find(member => member.character.id === 'escobar')!.alive = false;
  city.state.detained_npc_id = 'bentinho';
  await begin(page); await page.locator('#open-delegate').click();
  await expect(page.locator('.delegate-portrait-frame img')).toBeVisible();
  await expect(page.locator('.suspect-card')).toHaveCount(7);
  await expect(page.locator('#submit-accusation')).toBeDisabled();
  await expect(page.getByRole('radio', {name: /Escobar/})).toBeDisabled();
  await expect(page.getByRole('radio', {name: /Bentinho/})).toBeDisabled();
  await page.getByRole('radio', {name: /Capitu/}).check();
  await expect(page.locator('#accused-selection')).toContainText('Capitu');
  await expect(page.locator('#submit-accusation')).toBeEnabled();
  await page.getByRole('radio', {name: /Capitu/}).focus(); await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('radio', {name: /Virgília/})).toBeChecked();
  await expect(page.locator('#accused-selection')).toContainText('Virgília');
  await expect.poll(() => page.locator('#delegate-overlay img').evaluateAll(images => images.every(image => (image as HTMLImageElement).complete && (image as HTMLImageElement).naturalWidth > 0))).toBe(true);
  await page.screenshot({path: '../artifacts/delegate-desktop.png', fullPage: true});
  await page.locator('#close-delegate').click(); await page.locator('#open-delegate').click();
  await expect(page.getByRole('radio', {name: /Virgília/})).toBeChecked();
  await page.setViewportSize({width: 390, height: 844});
  await expect(page.locator('.delegate-portrait-frame img')).toBeVisible();
  expect(await page.locator('.delegate-modal').evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
  await page.getByRole('radio', {name: /Capitu/}).check();
  await expect(page.locator('#accused-selection')).toContainText('Capitu');
  await page.locator('.delegate-modal').evaluate(element => {element.scrollTop = 0;});
  await page.screenshot({path: '../artifacts/delegate-mobile.png', fullPage: true});
  await page.locator('#close-delegate').click();
  await expect(page.locator('#delegate-overlay')).toBeHidden();
});


test('mapa acompanha moradores em viagem', async ({page}) => {
  const city = await cityFixture(page);
  city.world.npc_presences = [{npc_id:'capitu',name:'Capitu',location_id:'praca_verde',activity:'travelling',destination_id:'cais_lanternas'}];
  city.state.inventory = [{id:'ev-pixel',crime_id:'crime-ui',item_id:'relogio_quincas',name:'Relógio de bolso',kind:'unique',description:'Objeto recolhido.'}];
  await begin(page); await page.locator('#open-map').click();
  await expect(page.locator('#map-residents')).toContainText('Capitu · Praça Verde → Cais das Lanternas');
  city.world.npc_presences[0].location_id = 'cais_lanternas'; city.world.npc_presences[0].activity = 'talking'; city.world.npc_presences[0].destination_id = null;
  await expect(page.locator('#map-residents')).toContainText('Capitu · Cais das Lanternas · Conversando');
  await page.locator('#close-map').click();
});

test('rejeição de disponibilidade preserva rascunho e bloqueia envios repetidos até nova abordagem', async ({page}) => {
  const city=await cityFixture(page); city.world.visible_npcs[0].x=190;
  let sends=0;
  await page.route(/\/conversations\/[^/]+\/messages(?:\?.*)?$/,route=> {
    if(route.request().method()==='POST'){sends++;return route.fulfill({status:403,json:{detail:'O personagem saiu deste local. Feche a conversa e procure-o no mapa.',code:'npc_away'}});}
    return route.fulfill({json:{conversation_id:'conversation-ui',messages:[]}});
  });
  await begin(page);await page.locator('#approach').click();
  await expect(page.locator('#message-input')).toBeEnabled();
  await page.locator('#message-input').fill('O que aconteceu no cais?');await page.locator('#send-message').click();
  await expect(page.locator('#dialogue-status')).toContainText('saiu deste local');
  await expect(page.locator('#dialogue-status')).not.toContainText('Ainda não há resposta');
  await expect(page.locator('#send-message')).toBeDisabled();
  await expect(page.locator('#message-input')).toHaveValue('O que aconteceu no cais?');
  expect(sends).toBe(1);
  await page.locator('#close-dialogue').click();await page.locator('#approach').click();
  await expect(page.locator('#message-input')).toBeEnabled();
  await expect(page.locator('#message-input')).toHaveValue('O que aconteceu no cais?');
});


test('cadeia mostra detido, bloqueia a noite e solta inocente antes do jornal', async ({page}) => {
  const city=await cityFixture(page);await begin(page);
  city.state.detained_npc_id='rubiao';city.state.revision++;
  await expect(page.locator('#custody-overlay')).toBeVisible();
  await expect(page.locator('#custody-title')).toContainText('Rubião');
  await expect(page.locator('#custody-canvas canvas')).toHaveAttribute('width','960');
  await page.screenshot({path:'../artifacts/custody-waiting.png',fullPage:true});
  city.state.phase='night';city.state.phase_ends_at=new Date(Date.now()+8000).toISOString();city.state.revision++;
  await expect(page.locator('#leave-custody')).toBeHidden();
  await page.keyboard.press('Escape');await expect(page.locator('#custody-overlay')).toBeVisible();
  city.state.phase='day';city.state.day=2;city.state.detained_npc_id=null;city.state.revision++;
  city.state.phase_ends_at=new Date(Date.now()+300000).toISOString();
  city.state.journal.push({day:2,title:'O Clarim do Rio',headline:'Detido solto ao amanhecer',body:'Rubião não se transformou e foi solto.',victim_id:null,victim_name:null,location_id:null,detention_outcome:'released',illustration:'quiet'});
  await expect(page.locator('#custody-title')).toContainText('amanhecer');
  await expect(page.locator('#journal-overlay')).toBeVisible({timeout:10000});
  await expect(page.locator('#journal-body')).toContainText('foi solto');
});

test('personagem feminina aguarda na cela e recebe aviso de soltura no feminino', async ({page}) => {
  const city=await cityFixture(page);await begin(page);
  city.state.detained_npc_id='florenca';city.state.revision++;
  await expect(page.locator('#custody-title')).toContainText('Florença');
  await expect(page.locator('#case-hint')).toContainText('A acusada');
  await expect(page.locator('#custody-canvas')).toHaveAttribute('aria-label',/Florença na cela central/);
  await page.screenshot({path:'../artifacts/delegacia-florenca.png',fullPage:true});
  city.state.phase='night';city.state.revision++;
  await expect(page.locator('#leave-custody')).toBeHidden();
  city.state.phase='day';city.state.day=2;city.state.detained_npc_id=null;city.state.revision++;
  city.state.journal.push({day:2,title:'O Clarim do Rio',headline:'Florença volta à cidade',body:'Florença foi solta ao amanhecer.',victim_id:null,victim_name:null,location_id:null,detention_outcome:'released',illustration:'quiet'});
  await expect(page.locator('#custody-caption')).toContainText('Florença não se transformou e será solta');
  await expect(page.locator('#journal-body')).toContainText('Florença foi solta');
});

test('personagem masculino também se transforma na cela e chega à edição de vitória', async ({page}) => {
  const city=await cityFixture(page);await begin(page);
  city.state.detained_npc_id='bentinho';city.state.revision++;
  await expect(page.locator('#custody-title')).toContainText('Bentinho');
  await expect(page.locator('#case-hint')).toContainText('O acusado');
  city.state.phase='finished';city.state.status='won';city.state.revision++;
  city.state.ending={result:'won',method:'detention',werewolf_id:'bentinho',message:'Bentinho se transformou na cela. Floriano venceu.'};
  await expect(page.locator('#custody-caption')).toContainText('Bentinho se transformou');
  await page.waitForTimeout(1900);
  await page.screenshot({path:'../artifacts/delegacia-bentinho-feral.png',fullPage:true});
  await expect(page.locator('#victory-paper')).toBeVisible({timeout:10000});
});

for(const [id,name] of [['rubiao','Rubião'],['florenca','Florença']]) {
  test(`${name} entra caminhando antes de a grade fechar e a sequência não se repete`,async({page})=>{
    const city=await cityFixture(page);await begin(page);
    city.state.detained_npc_id=id;city.state.revision++;
    await expect(page.locator('#custody-caption')).toHaveText(`${name} caminha para dentro da cela.`);
    const box=(await page.locator('#custody-canvas canvas').boundingBox())!;
    const waitingRoom={x:Math.round(box.x+box.width*.70),y:Math.round(box.y+box.height*.1),width:Math.round(box.width*.27),height:Math.round(box.height*.65)};
    const openRoom=await page.screenshot({clip:waitingRoom});
    const entrance=await page.locator('#custody-canvas').screenshot({path:`../artifacts/cela-entrada-${id}.png`});
    await expect(page.locator('#custody-caption')).toContainText('A grade se fecha');
    await expect(page.locator('#custody-caption')).toContainText('A acusação ainda não confirma a culpa');
    const held=await page.locator('#custody-canvas').screenshot();
    expect(entrance.equals(held)).toBe(false);
    // The sliding gate must not cover the benches or archive beside the cell.
    expect((await page.screenshot({clip:waitingRoom})).equals(openRoom)).toBe(true);
    await page.screenshot({path:`../artifacts/cela-fechada-${id}.png`,fullPage:true});
    city.state.revision++;
    await page.waitForResponse(response=>response.url().endsWith('/investigation'));
    await expect(page.locator('#custody-caption')).toContainText('A acusação ainda não confirma a culpa');
    expect(city.state.detained_npc_id).toBe(id);expect(city.state.status).toBe('active');
  });
}

test('retomar um caso com pessoa já detida mostra a cela fechada diretamente',async({page})=>{
  const city=await cityFixture(page);city.state.detained_npc_id='capitu';
  await page.goto('/');await page.locator('#start').click();
  await expect(page.locator('#scene-loading')).toBeHidden({timeout:30000});
  await expect(page.locator('#custody-title')).toContainText('Capitu');
  await expect(page.locator('#custody-caption')).toContainText('A acusação ainda não confirma a culpa');
  await expect(page.locator('#leave-custody')).toBeVisible();
});

test('movimento reduzido mantém a pessoa dentro da cela sem animação de entrada',async({page})=>{
  await page.emulateMedia({reducedMotion:'reduce'});
  const city=await cityFixture(page);await begin(page);
  city.state.detained_npc_id='florenca';city.state.revision++;
  await expect(page.locator('#custody-title')).toContainText('Florença');
  await expect(page.locator('#custody-caption')).toContainText('A acusação ainda não confirma a culpa');
  await expect(page.locator('#leave-custody')).toBeVisible();
});
