import {api, ApiError, type CasePublic, type CaseEvidence, type GamePublic, type CharacterManifest, type Conversation, type ExitSide, type Location, type LocationID, type Message, type HeardReport, type WorldSnapshot} from '../shared/api';
import {closestNPC, MovementController} from './movement';
import {ExitBoundary} from './exits';
import {CaseClock, CasePoller, closestCrime, formatClock} from './case';
import {CityScene, makeGame} from './scene';
import {sendDialogue} from './dialogue';
import './style.css';

const app = document.querySelector<HTMLDivElement>('#app')!;
app.innerHTML = `
  <div class="site-shell">
    <header class="masthead">
      <a class="brand" href="/" aria-label="Memórias Licantropicas, início"><span class="brand-mark" aria-hidden="true">☾</span><span>Memórias<br><strong>Licantropicas</strong></span></a>
      <div class="edition">RIO DE JANEIRO, 1890<span>Um caso do detetive Floriano</span></div>
      <button class="button ghost small" id="new-case" type="button">Nova investigação <span aria-hidden="true">↗</span></button>
    </header>

    <main>
      <section class="introduction" id="introduction" aria-labelledby="intro-title">
        <div class="intro-art"><div class="intro-art-shade"></div><span class="chapter-tag">PRIMEIRO CAPÍTULO</span></div>
        <div class="intro-copy"><p class="eyebrow"><span></span> UMA CIDADE. SETE SUSPEITOS.</p><h1 id="intro-title">Toda cidade tem<br>algo a <em>esconder.</em></h1><p class="intro-description">Brás Cubas está morto. Entre as boas maneiras e os maus presságios, alguém guarda um segredo que a cidade prefere não enxergar.</p><p class="intro-invitation">Vista o casaco de Floriano. Caminhe pelas ruas, escute seus moradores e desconfie até das certezas.</p><div class="intro-actions"><button id="start" class="button primary" type="button">Iniciar investigação <span aria-hidden="true">→</span></button><button id="continue" class="button secondary" type="button" hidden>Continuar meu caso</button></div><p id="launch-status" class="status" role="status" aria-live="polite"></p><div class="intro-controls"><span><kbd>A</kbd><kbd>D</kbd> explorar</span><span><kbd>E</kbd> conversar</span><span><kbd>M</kbd> mapa</span></div></div>
      </section>

      <section id="investigation" class="investigation" aria-label="Sua investigação" hidden>
        <div class="scene-heading"><div><p class="eyebrow">OS CAMINHOS DA INVESTIGAÇÃO</p><h1 id="location-name">Praça Verde</h1></div><button id="open-map" class="button map-button" type="button"><span aria-hidden="true">⌘</span> Mapa da cidade <kbd>M</kbd></button></div>
        <div class="case-toolbar"><div class="day-clock"><span id="case-day">DIA 1</span><strong id="case-clock" aria-label="Tempo restante do período">05:00</strong><small id="case-phase">A cidade está acordada</small></div><nav aria-label="Ferramentas de investigação"><button id="open-journal" class="button secondary small" type="button">O Clarim do Rio</button><button id="open-notebook" class="button secondary small" type="button">Caderno <span id="evidence-count">0 pistas</span></button><button id="open-delegate" class="button secondary small" type="button">Chamar o delegado</button></nav></div><div class="scene-frame"><div class="frame-corner top-left"></div><div class="frame-corner top-right"></div><div id="game-canvas" aria-label="Cenário lateral. Use as setas para andar e E para conversar." tabindex="0"></div><div class="scene-vignette" aria-hidden="true"></div><div id="scene-loading" class="scene-loading" role="status">Preparando a cidade…</div><div class="world-caption"><span class="caption-dot"></span><span id="world-caption">O bairro guarda suas histórias.</span></div><button id="inspect-crime" class="approach-button inspect-button" type="button" hidden><kbd>E</kbd><span>Procurar vestígios</span></button><button id="approach" class="approach-button" type="button" hidden><kbd>E</kbd><span></span></button></div>
        <div class="scene-footer"><div class="touch-controls" aria-label="Caminhar pela cidade"><button id="walk-left" type="button" aria-label="Caminhar para a esquerda">←</button><button id="walk-right" type="button" aria-label="Caminhar para a direita">→</button></div><div class="control-guide"><span><kbd>←</kbd><kbd>→</kbd> Caminhar</span><span><kbd>E</kbd> Conversar</span><span><kbd>M</kbd> Viajar</span></div><span class="connection-label" id="connection-label"><i></i> Caso em andamento</span></div>
        <div class="notebook"><div class="notebook-number">01</div><div><p class="eyebrow">O CADERNO DE FLORIANO</p><h2 id="case-hint-title">Uma boa pergunta abre portas.</h2><p id="case-hint">Aproxime-se de um morador para ouvir sua versão. Procure marcas de cenas do crime e apresente os vestígios recolhidos.</p></div><span class="notebook-ornament" aria-hidden="true">✦</span></div>
      </section>
    </main>
    <footer class="site-footer"><span>MEMÓRIAS LICANTROPICAS</span><span>Nem toda história é contada por inteiro.</span><span>UMA INVESTIGAÇÃO EM PIXELS</span></footer>
  </div>

  <div id="map-overlay" class="overlay" hidden><section class="map-modal" role="dialog" aria-modal="true" aria-labelledby="map-title"><header class="modal-heading"><div><p class="eyebrow">ESCOLHA SEU PRÓXIMO DESTINO</p><h2 id="map-title">Os caminhos da cidade</h2></div><button class="icon-button" id="close-map" aria-label="Fechar mapa" type="button">×</button></header><div class="city-map"><img src="/assets/map/city.png" alt="Mapa ilustrado do bairro, entre a praça, a cabana, a Casa Verde, o café e o cais."/><div id="map-destinations"></div></div><p class="map-caption">Cada encontro pode mudar o rumo desta história.</p><p id="map-status" class="status" role="status" aria-live="polite"></p></section></div>

  <div id="exit-overlay" class="overlay" hidden><section class="exit-modal" role="dialog" aria-modal="true" aria-labelledby="exit-title" aria-describedby="exit-description"><header class="modal-heading"><div><p class="eyebrow">NO FIM DESTA RUA</p><h2 id="exit-title">Por onde seguimos?</h2></div><button class="icon-button" id="close-exit" aria-label="Ficar neste local" type="button">×</button></header><p id="exit-description">Escolha um caminho para continuar a investigação.</p><div id="exit-destinations" class="exit-destinations"></div><p id="exit-status" class="status" role="status" aria-live="polite"></p><button id="stay-here" class="button secondary" type="button">Ficar neste local</button></section></div>

  <div id="dialogue-overlay" class="overlay dialogue-overlay" hidden><section class="dialogue-modal" role="dialog" aria-modal="true" aria-labelledby="dialogue-name"><aside class="persona-panel"><div class="persona-frame"><img id="persona-portrait" src="" alt=""/></div><p class="eyebrow">DEPOIMENTO</p><h2 id="dialogue-name"></h2><span class="persona-flourish" aria-hidden="true">— ✦ —</span><p>Nem toda verdade vem à primeira pergunta.</p></aside><div class="conversation-panel"><header class="conversation-heading"><div><span class="conversation-dot"></span><span>Conversa com Floriano</span></div><button id="close-dialogue" class="icon-button" type="button" aria-label="Encerrar conversa">×</button></header><div id="messages" class="messages" role="log" aria-live="polite"></div><div id="dialogue-status" class="status dialogue-status" role="status" aria-live="polite"></div><div id="evidence-presenter" class="evidence-presenter" hidden><label for="present-evidence">Mostrar um vestígio</label><div><select id="present-evidence"></select><button id="present-button" class="button small" type="button">Apresentar</button></div><p id="presentation-status" role="status" aria-live="polite"></p></div><details id="interrogation-panel" class="interrogation-panel"><summary>Interrogar e confrontar versões</summary><p class="case-note">Pergunte onde estava, com quem e o que fazia. Um álibi é uma declaração que pode ser confrontada.</p><div class="interrogation-controls"><label>Dia <input id="interrogation-day" type="number" min="0" value="0"/></label><label>Período <select id="interrogation-period"><option value="night">Noite</option><option value="day">Dia</option></select></label><button id="interrogate-button" class="button small" type="button">Perguntar sobre o álibi</button></div><p id="interrogation-status" role="status" aria-live="polite"></p><details><summary>Confrontar com registros do caderno</summary><p class="case-note">Selecione vestígios, seus depoimentos e versões contraditórias. Insistir sem novos elementos não força uma confissão.</p><div id="confrontation-proofs" class="confrontation-proofs"></div><button id="confront-button" class="button small" type="button">Confrontar e pedir que admita</button><p id="confrontation-status" role="status" aria-live="polite"></p></details></details><form id="message-form" class="message-form"><label class="sr-only" for="message-input">Sua pergunta</label><textarea id="message-input" rows="2" maxlength="8000" placeholder="O que você gostaria de perguntar?" required></textarea><button id="send-message" class="button primary" type="submit" aria-label="Enviar pergunta">Enviar <span aria-hidden="true">→</span></button></form><p class="form-hint">Enter para enviar · Shift + Enter para uma nova linha</p></div></section></div>
  <div id="journal-overlay" class="overlay" hidden><section class="journal-modal case-modal" role="dialog" aria-modal="true" aria-labelledby="journal-title"><header class="newspaper-masthead"><div class="newspaper-dateline"><span>RIO DE JANEIRO</span><span>EDIÇÃO DA MANHÃ</span><button id="close-journal" class="icon-button" type="button" aria-label="Fechar jornal">×</button></div><h2 id="journal-title">O Clarim do Rio</h2><div class="newspaper-edition"><span>NOTÍCIAS DA CIDADE · 1890</span><span id="journal-day"></span></div></header><article class="newspaper-story"><p class="journal-motto">Os acontecimentos da cidade, à luz do dia.</p><h3 id="journal-headline"></h3><figure id="journal-snapshot" class="journal-snapshot" hidden><img src="/assets/press/crime-scene-snapshot.png" alt="Registro monocromático de uma rua carioca à noite, com um chapéu caído e pegadas no calçamento."/><figcaption id="journal-snapshot-caption"></figcaption></figure><p id="journal-body"></p><p id="journal-location" class="journal-location"></p></article><button id="read-journal" class="button primary" type="button">Continuar a investigação</button></section></div>
  <div id="notebook-overlay" class="overlay" hidden><section class="case-modal notebook-modal" role="dialog" aria-modal="true" aria-labelledby="notebook-title"><header class="modal-heading"><div><p class="eyebrow">O CADERNO DE FLORIANO</p><h2 id="notebook-title">Vestígios e versões</h2></div><button id="close-notebook" class="icon-button" type="button" aria-label="Fechar caderno">×</button></header><p class="case-note">Um objeto pode ter muitos donos. Um depoimento registra uma versão, não uma certeza.</p><h3>Vestígios recolhidos</h3><div id="evidence-list" class="evidence-list"></div><h3>Depoimentos sobre objetos</h3><div id="testimony-list" class="testimony-list"></div><h3>Álibis e interrogatórios</h3><div id="interrogation-list" class="testimony-list"></div><h3>Confrontos</h3><div id="confrontation-list" class="testimony-list"></div><h3>Cenas conhecidas</h3><div id="crime-list" class="crime-list"></div><h3>Relatos ouvidos por Floriano</h3><p class="case-note">Fofocas conservam a fonte de quem contou. Repetir uma história não a torna prova.</p><p id="reports-status" class="status" role="status" aria-live="polite"></p><div id="heard-report-list" class="testimony-list"></div></section></div>
  <div id="delegate-overlay" class="overlay" hidden>
    <section class="case-modal delegate-modal" role="dialog" aria-modal="true" aria-labelledby="delegate-title">
      <aside class="delegate-persona">
        <p class="eyebrow">A AUTORIDADE POLICIAL</p>
        <div class="delegate-portrait-frame"><img src="/assets/portraits/delegado.png" alt="Delegado de polícia, de bigode e casaca escura." width="192" height="220"/></div>
        <h3>Delegado<br> de polícia</h3><span class="persona-flourish" aria-hidden="true">— ✦ —</span>
        <blockquote>“Suspeitas abrem o caso, detetive. São os indícios que sustentam uma prisão.”</blockquote>
        <p class="delegate-rule">Uma acusação por dia.<br>A verdade será confirmada à noite.</p>
      </aside>
      <div class="delegate-case">
        <header class="modal-heading"><div><p class="eyebrow">UM PEDIDO DE PRISÃO</p><h2 id="delegate-title">Apresente seu caso</h2></div><button id="close-delegate" class="icon-button" type="button" aria-label="Dispensar delegado">×</button></header>
        <p class="case-note delegate-introduction">Escolha quem deseja acusar e apresente os vestígios e depoimentos que sustentam sua suspeita. A transformação na cela será a confirmação da culpa.</p>
        <form id="accusation-form">
          <fieldset class="suspect-fieldset"><legend><span class="case-step">01</span> Quem você acusa?</legend><p class="delegate-field-hint">Escolha um morador para examinar o pedido de prisão.</p><div id="accused-npc" class="suspect-gallery"></div><p id="accused-selection" class="accused-selection" role="status" aria-live="polite">Nenhum suspeito selecionado.</p></fieldset>
          <div class="accusation-records"><fieldset><legend><span class="case-step">02</span> Vestígios recolhidos</legend><div id="accusation-evidence"></div></fieldset><fieldset><legend><span class="case-step">03</span> Depoimentos registrados</legend><div id="accusation-testimonies"></div></fieldset></div>
          <div class="accusation-submit"><p id="accusation-status" class="status" role="status" aria-live="polite"></p><button id="submit-accusation" class="button primary" type="submit" disabled>Apresentar acusação <span aria-hidden="true">→</span></button></div>
        </form><div id="accusation-history"></div>
      </div>
    </section>
  </div>
  <div id="phase-overlay" class="overlay phase-overlay" hidden><section class="case-modal phase-modal" role="dialog" aria-modal="true" aria-labelledby="phase-title" aria-describedby="phase-description"><span class="phase-moon" aria-hidden="true">☾</span><p class="eyebrow" id="phase-eyebrow">A CIDADE RECOLHE-SE</p><h2 id="phase-title">A noite guarda seus segredos.</h2><p id="phase-description">Floriano aguarda a manhã. Os acontecimentos serão publicados no Clarim do Rio.</p><p id="phase-countdown" role="status" aria-live="polite"></p><button id="ending-new-case" class="button primary" type="button" hidden>Iniciar outro caso</button></section></div>
  <div id="toast" class="toast" role="status" aria-live="polite" hidden></div>
`;

const $ = <T extends HTMLElement = HTMLElement>(selector: string) => document.querySelector<T>(selector)!;
const STORAGE_KEY = 'memorias-licantropicas:game';
const locationDescription: Record<LocationID, string> = {
  praca_verde: 'Entre árvores e rumores, a cidade segue seu curso.',
  cabana_capitu: 'Há coisas que nem as cartas revelam.',
  casa_verde: 'Aqui, até a razão tem suas dúvidas.',
  cafe_largo: 'Uma xícara de café. Muitas versões da mesma história.',
  cais_lanternas: 'O que chega com a maré nem sempre volta com ela.',
};
const mapPositions: Record<LocationID, {left: string; top: string; caption: string}> = {
  praca_verde: {left: '50%', top: '48%', caption: 'O coração do bairro'},
  cabana_capitu: {left: '23%', top: '23%', caption: 'Cartas e confidências'},
  casa_verde: {left: '76%', top: '23%', caption: 'Às portas da razão'},
  cafe_largo: {left: '24%', top: '75%', caption: 'Conversas à meia voz'},
  cais_lanternas: {left: '77%', top: '75%', caption: 'Histórias à beira-mar'},
};

let world: WorldSnapshot | null = null;
let locations: Location[] = [];
let manifest: CharacterManifest;
let controller: MovementController | null = null;
let scene: CityScene | null = null;
let game: ReturnType<typeof makeGame> | null = null;
let modal: 'map' | 'dialogue' | 'exit' | 'journal' | 'notebook' | 'delegate' | 'phase' | null = null;
let exitSide: ExitSide | null = null;
let exitBoundary = new ExitBoundary();
let busy = false;
let transitioning = false;
let pendingWorldSync = false;
let caseState: CasePublic | null = null;
let heardReports: HeardReport[] = [];
let cast: GamePublic['characters'] = [];
const caseClock = new CaseClock();
const casePoller = new CasePoller();
let starting = false;
let conversation: Conversation | null = null;
let conversationMessages: Message[] = [];
let historyReady = false;
const dialogueDrafts = new Map<string, string>();
let dialogueNPC: {npc_id: string; name: string} | null = null;
let lastNearest = '';
let toastTimer: ReturnType<typeof setTimeout> | undefined;

function savedGame() { try { return localStorage.getItem(STORAGE_KEY); } catch { return null; } }
function saveGame(id: string) { try { localStorage.setItem(STORAGE_KEY, id); } catch { /* A sessão ainda funciona sem armazenamento local. */ } }
function status(selector: string, text: string, error = false) {const el = $(selector); el.textContent = text; el.classList.toggle('error', error);}
function explain(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 409) return 'O estado da investigação mudou. Aguarde um instante e tente novamente.';
    return error.message;
  }
  return 'Algo interrompeu a investigação. Tente novamente em instantes.';
}
function toast(message: string) {
  clearTimeout(toastTimer); $('#toast').textContent = message; $('#toast').hidden = false;
  toastTimer = setTimeout(() => {$('#toast').hidden = true;}, 5000);
}

function setModal(next: typeof modal) {
  modal = next;
  for (const name of ['map', 'dialogue', 'exit', 'journal', 'notebook', 'delegate', 'phase']) $(`#${name}-overlay`).hidden = next !== name;
  scene?.setInputEnabled(next === null && !caseClock.blocked());
  $('#approach').hidden = true; $('#inspect-crime').hidden = true;
  lastNearest = '';
  if (next === null) $('#game-canvas').focus({preventScroll: true});
}

async function settleMovement() {
  busy = true;
  try { await controller?.stop(); } finally { busy = false; }
}

function applySnapshot(snapshot: WorldSnapshot) {
  world = snapshot;
  $('#location-name').textContent = snapshot.location.name;
  $('#world-caption').textContent = locationDescription[snapshot.location.id];
  scene?.apply(snapshot);
}

async function launch(resume: boolean) {
  if (starting) return;
  starting = true; casePoller.stop();
  $('#start').setAttribute('disabled', ''); $('#continue').setAttribute('disabled', '');
  status('#launch-status', resume ? 'Reabrindo seu caderno…' : 'Preparando uma nova investigação…');
  try {
    const id = resume ? savedGame() : (await api.createGame()).id;
    if (!id) throw new Error('Não há caso salvo');
    saveGame(id);
    casePoller.stop();
    const investigation = await api.investigation(id);
    const [snapshot, places, characters, publicGame] = await Promise.all([api.world(id), api.locations(), api.manifest(), api.game(id)]);
    caseState = null; heardReports = []; pendingWorldSync = false; transitioning = false; cast = publicGame.characters;
    locations = places; manifest = characters;
    controller?.dispose(); game?.destroy(true);
    exitBoundary = new ExitBoundary();
    controller = new MovementController(snapshot, api.move, () => api.world(id), applySnapshot, error => toast(explain(error)));
    scene = new CityScene(manifest, locations, snapshot, {
      blocked: () => Boolean(modal || busy || transitioning || starting || caseClock.blocked() || document.hidden || $('#investigation').hidden),
      frame: (delta, direction) => {
        if (!caseClock.blocked() && !transitioning) controller?.update(delta, direction);
        if (controller && world) {
          if (!modal && !busy && !transitioning && !starting && !caseClock.blocked()) {
            const boundary = exitBoundary.observe(controller.world, controller.x, direction);
            if (boundary) void openExit(boundary);
          }
          const crime = !modal && !busy && !caseClock.blocked() ? closestCrime(caseState, world, controller.x) : undefined;
          $('#inspect-crime').hidden = !crime;
          const nearest = !crime && !modal && !busy && !caseClock.blocked() ? closestNPC(world, controller.x) : undefined;
          if ((nearest?.npc_id ?? '') !== lastNearest) {
            lastNearest = nearest?.npc_id ?? '';
            $('#approach').hidden = !nearest;
            $('#approach span').textContent = nearest ? `Conversar com ${nearest.name}` : '';
          }
        }
        return {x: controller?.x ?? snapshot.player.x,
          facing: direction === 'left' ? 'left' : direction === 'right' ? 'right' : controller?.world.player.facing ?? 'right'};
      },
      approach: () => {void approach();}, inspect: crimeID => {void searchCrime(crimeID);}, map: () => {void openMap();},
      loaded: () => {$('#scene-loading').hidden = true; scene?.setInputEnabled(modal === null && !caseClock.blocked()); if (!modal) $('#game-canvas').focus({preventScroll: true});},
      failed: () => {$('#scene-loading').hidden = false; $('#scene-loading').textContent = 'Não foi possível carregar a arte da cidade. Recarregue para tentar novamente.';},
    });
    modal = null; busy = false; lastNearest = '';
    $('#introduction').hidden = true; $('#investigation').hidden = false;
    $('#scene-loading').hidden = false; $('#scene-loading').textContent = 'Abrindo os caminhos da cidade…';
    applySnapshot(snapshot);
    game = makeGame($('#game-canvas'), scene);
    await applyCase(investigation, true);
    casePoller.start(async () => {
      if (!world || world.game_id !== id || $('#investigation').hidden) return;
      try {
        const [next, snapshot] = await Promise.all([api.investigation(id), api.world(id)]);
        await applyCase(next);
        if (world?.game_id === id && !transitioning && !pendingWorldSync) controller?.observe(snapshot);
      }
      catch (error) {if (!(error instanceof ApiError && error.status === 409)) $('#case-phase').textContent = 'Sincronizando com a cidade…';}
    });
    document.body.classList.add('case-active');
    status('#launch-status', '');
  } catch (error) {
    const message = error instanceof ApiError && (error.status === 404 || error.status === 409)
      ? 'Este caso não está disponível nesta edição. Inicie uma nova investigação para continuar.' : explain(error);
    status('#launch-status', message, true);
    $('#continue').hidden = !savedGame();
  } finally {
    starting = false; $('#start').removeAttribute('disabled'); $('#continue').removeAttribute('disabled');
  }
}

async function openMap() {
  if (!world || !controller || busy || modal || caseClock.blocked() || transitioning) return;
  busy = true;
  await settleMovement();
  setModal('map');
  renderMap(); status('#map-status', '');
  $('#close-map').focus();
}

function renderMap() {
  const container = $('#map-destinations'); container.replaceChildren();
  for (const location of locations) {
    const position = mapPositions[location.id];
    const button = document.createElement('button'); button.type = 'button'; button.className = 'map-pin';
    button.style.left = position.left; button.style.top = position.top;
    button.classList.toggle('current', world?.location.id === location.id);
    button.disabled = busy || world?.location.id === location.id;
    const dot = document.createElement('span'); dot.className = 'map-pin-dot'; dot.textContent = world?.location.id === location.id ? '◆' : '◇';
    const name = document.createElement('strong'); name.textContent = location.name;
    const caption = document.createElement('small'); caption.textContent = world?.location.id === location.id ? 'Você está aqui' : position.caption;
    button.append(dot, name, caption); button.addEventListener('click', () => {void travel(location.id);}); container.append(button);
  }
}

async function openExit(side: ExitSide) {
  if (!world || !controller || busy || modal || caseClock.blocked() || transitioning) return;
  busy = true;
  await settleMovement();
  exitSide = side;
  setModal('exit');
  $('#exit-description').textContent = `Na saída à ${side === 'left' ? 'esquerda' : 'direita'} de ${world.location.name}, estes caminhos levam a outros encontros.`;
  status('#exit-status', '');
  renderExits();
  $('#exit-destinations button')?.focus();
}

function renderExits() {
  const container = $('#exit-destinations'); container.replaceChildren();
  if (!world || !exitSide) return;
  for (const exit of world.location.exits.filter(exit => exit.side === exitSide)) {
    const destination = locations.find(location => location.id === exit.target_location_id);
    if (!destination) continue;
    const button = document.createElement('button'); button.type = 'button'; button.className = 'exit-destination';
    button.disabled = busy; button.dataset.destination = destination.id;
    const name = document.createElement('strong'); name.textContent = destination.name;
    const caption = document.createElement('span'); caption.textContent = `Chegar pela ${exit.arrival_side === 'left' ? 'esquerda' : 'direita'} →`;
    button.append(name, caption);
    button.addEventListener('click', () => {if (exitSide) void travel(destination.id, exitSide);});
    container.append(button);
  }
  const otherEnd = document.createElement('button'); otherEnd.type = 'button'; otherEnd.className = 'exit-destination';
  otherEnd.disabled = busy; otherEnd.dataset.destination = world.location.id;
  otherEnd.textContent = 'Ir para a outra ponta deste local';
  otherEnd.addEventListener('click', () => {if (world && exitSide) void travel(world.location.id, exitSide);});
  container.append(otherEnd);
  $('#close-exit').toggleAttribute('disabled', busy);
  $('#stay-here').toggleAttribute('disabled', busy);
}

async function travel(target: LocationID, side?: ExitSide) {
  if (!world || !controller || busy || caseClock.blocked() || transitioning) return;
  const statusSelector = side ? '#exit-status' : '#map-status';
  busy = true; renderMap(); renderExits(); status(statusSelector, 'Seguindo por outro caminho…');
  try {
    const snapshot = await api.travel(controller.world, target, side);
    controller.accept(snapshot); if (!caseClock.blocked()) setModal(null); toast(`Você chegou: ${snapshot.location.name}.`);
  } catch (error) {
    status(statusSelector, explain(error), true);
    if (error instanceof ApiError && error.status === 409) {
      try {controller.accept(await api.world(world.game_id));} catch { /* mantém erro visível */ }
    }
  } finally {busy = false; renderMap(); renderExits(); lastNearest = '';}
}

async function approach() {
  if (!world || !controller || busy || modal || caseClock.blocked() || transitioning) return;
  const npc = closestNPC(world, controller.x);
  if (!npc) {toast('Aproxime-se de um morador para conversar.'); return;}
  busy = true;
  await settleMovement();
  busy = true; dialogueNPC = npc; conversation = null; conversationMessages = []; historyReady = false;
  $<HTMLTextAreaElement>('#message-input').value = ''; renderPresentation(); renderInterrogation(); status('#presentation-status', ''); status('#interrogation-status', ''); status('#confrontation-status', '');
  setModal('dialogue');
  $('#dialogue-name').textContent = npc.name;
  const image = $('#persona-portrait') as HTMLImageElement;
  image.src = manifest.characters.find(asset => asset.id === npc.npc_id)?.portraitPath ?? `/assets/portraits/${npc.npc_id}.png`;
  image.alt = `Retrato de ${npc.name}`;
  $('#messages').replaceChildren(); status('#dialogue-status', 'Abrindo o caderno desta conversa…');
  setSending(true);
  try {
    conversation = await api.approach(world.game_id, npc.npc_id);
    $<HTMLTextAreaElement>('#message-input').value = dialogueDrafts.get(`${world.game_id}:${conversation.id}`) ?? '';
    await refreshHistory(); status('#dialogue-status', '');
  } catch (error) {status('#dialogue-status', explain(error), true);}
  finally {busy = false; setSending(false); if (modal === 'dialogue' && !caseClock.blocked()) $('#message-input').focus();}
}

function appendMessage(message: Message) {
  const item = document.createElement('article'); item.className = `message ${message.speaker}`;
  const label = document.createElement('p'); label.className = 'message-author';
  label.textContent = message.speaker === 'player' ? 'FLORIANO' : dialogueNPC?.name.toLocaleUpperCase('pt-BR') ?? 'DEPOIMENTO';
  const content = document.createElement('p'); content.className = 'message-content'; content.textContent = message.content;
  item.append(label, content); $('#messages').append(item);
}

async function refreshHistory() {
  if (!conversation || !world) return;
  const gameID = world.game_id, conversationID = conversation.id;
  const history = await api.history(gameID, conversationID);
  if (world?.game_id !== gameID || conversation?.id !== conversationID) return;
  historyReady = true;
  renderConversation(history.messages);
}

function renderConversation(messages: Message[]) {
  conversationMessages = messages;
  $('#messages').replaceChildren();
  if (!messages.length) {
    const empty = document.createElement('div'); empty.className = 'conversation-opening';
    empty.textContent = 'O primeiro passo de uma investigação é saber escutar. Faça sua pergunta.';
    $('#messages').append(empty);
  } else messages.forEach(appendMessage);
  $('#messages').scrollTop = $('#messages').scrollHeight;
}

function setSending(sending: boolean) {
  $('#send-message').toggleAttribute('disabled', sending || !conversation || !historyReady || caseClock.blocked());
  $('#message-input').toggleAttribute('disabled', sending || !conversation || !historyReady || caseClock.blocked());
  $('#close-dialogue').toggleAttribute('disabled', sending);
  $('#present-button').toggleAttribute('disabled', sending || caseClock.blocked());
  for (const id of ['interrogate-button', 'confront-button']) $(`#${id}`).toggleAttribute('disabled', sending || !conversation || caseClock.blocked());
}

async function sendMessage(event: Event) {
  event.preventDefault();
  if (!conversation || !world || !historyReady || busy || caseClock.blocked()) return;
  const input = $('#message-input') as HTMLTextAreaElement;
  const content = input.value.trim(); if (!content) return;
  const gameID = world.game_id, conversationID = conversation.id;
  const draftKey = `${gameID}:${conversationID}`;
  dialogueDrafts.set(draftKey, input.value);
  const isCurrent = () => world?.game_id === gameID && conversation?.id === conversationID;
  busy = true; setSending(true); status('#dialogue-status', `${dialogueNPC?.name ?? 'A persona'} está respondendo…`);
  try {
    const result = await sendDialogue({content, baseline: [...conversationMessages],
      send: async () => (await api.send(gameID, conversationID, content)).message,
      history: async () => (await api.history(gameID, conversationID)).messages,
      onConfirmed: messages => {
        dialogueDrafts.delete(draftKey);
        if (isCurrent()) {input.value = ''; renderConversation(messages);}
      }});
    if (result.clearDraft) dialogueDrafts.delete(draftKey);
    if (!isCurrent()) return;
    if (result.clearDraft) input.value = '';
    if (result.outcome === 'uncertain') historyReady = false;
    renderConversation(result.messages);
    status('#dialogue-status', result.status, result.outcome !== 'confirmed');
  } finally {busy = false; setSending(false); if (modal === 'dialogue' && !caseClock.blocked()) input.focus();}
}

function addText(parent: HTMLElement, tag: string, text: string, className?: string) {
  const element = document.createElement(tag); element.textContent = text;
  if (className) element.className = className;
  parent.append(element); return element;
}

function locationName(id: string) {return locations.find(location => location.id === id)?.name ?? id;}
function npcName(id: string) {return cast.find(member => member.character.id === id)?.character.name ?? id;}
function portraitPath(id: string) {return manifest?.characters.find(asset => asset.id === id)?.portraitPath ?? `/assets/portraits/${id}.png`;}
function periodLabel(day: number, period: 'night' | 'day') {return `${period === 'night' ? 'noite' : 'dia'} ${day}`;}
function itemKind(evidence: CaseEvidence) {return {unique: 'Exclusivo', singular: 'Singular', common: 'Comum'}[evidence.kind];}
function itemArt(itemId: string, kind: CaseEvidence['kind']) {
  const wrapper = document.createElement('span'); wrapper.className = `item-art item-art-${kind}`; wrapper.setAttribute('aria-hidden', 'true');
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); svg.setAttribute('viewBox', '0 0 64 64');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', `/assets/items/item-icons.svg#${itemId}`); svg.append(use); wrapper.append(svg);
  return wrapper;
}

async function applyCase(next: CasePublic, initial = false) {
  if (!world || (!initial && $('#investigation').hidden) || next.game_id !== world.game_id || (caseState && next.revision < caseState.revision)) return;
  const previous = caseState;
  const changed = !previous || previous.day !== next.day || previous.phase !== next.phase || previous.status !== next.status
    || previous.detained_npc_id !== next.detained_npc_id || pendingWorldSync;
  caseState = next; caseClock.accept(next); renderClock();
  if (!previous || previous.revision !== next.revision) {
    scene?.setInvestigation(next); renderCase();
  }
  if (!changed) return;
  transitioning = true; pendingWorldSync = true; scene?.setInputEnabled(false);
  try {
    if (!initial) {
      await controller?.suspend();
      const [snapshot, publicGame] = await Promise.all([api.world(next.game_id), api.game(next.game_id)]);
      if (caseState?.revision !== next.revision || world?.game_id !== next.game_id) return;
      controller?.accept(snapshot); cast = publicGame.characters; renderCase();
    }
    pendingWorldSync = false;
    if (next.phase !== 'day' || next.status !== 'active') showPhase();
    else if (initial || previous?.day !== next.day) {
      conversation = null; dialogueNPC = null; exitBoundary = new ExitBoundary();
      renderJournal(); setModal('journal'); $('#read-journal').focus();
    } else if (modal === 'phase') setModal(null);
  } catch {toast('A manhã chegou. Estamos atualizando os caminhos da cidade.');}
  finally {transitioning = pendingWorldSync; scene?.setInputEnabled(modal === null && !caseClock.blocked() && !transitioning);}
}

function renderClock() {
  if (!caseState || $('#investigation').hidden) return;
  $('#case-day').textContent = `DIA ${caseState.day}`;
  $('#case-clock').textContent = caseState.phase === 'finished' ? 'FIM' : formatClock(caseClock.seconds());
  $('#case-phase').textContent = caseState.phase === 'night' ? 'A noite não é jogável'
    : caseState.phase === 'finished' ? 'Este caso chegou ao fim'
    : caseClock.seconds() ? 'Cinco minutos até a noite' : 'Aguardando os acontecimentos da noite…';
  $('#open-delegate').toggleAttribute('disabled', caseClock.blocked());
  $('#open-map').toggleAttribute('disabled', caseClock.blocked());
  if (caseState.phase === 'day' && caseState.status === 'active' && !caseClock.seconds() && modal !== 'phase') {
    scene?.setInputEnabled(false); showPhase();
  }
  if (modal === 'phase') $('#phase-countdown').textContent = caseState.phase === 'finished' ? ''
    : caseState.phase === 'night' ? `A manhã se aproxima · ${formatClock(caseClock.seconds())}` : 'Aguardando confirmação da cidade…';
}

function showPhase() {
  if (!caseState) return;
  const ending = caseState.ending;
  $('#phase-eyebrow').textContent = ending ? ending.result === 'won' ? 'A CIDADE RESPIRA ALIVIADA' : 'A CIDADE SILENCIOU' : 'A CIDADE RECOLHE-SE';
  $('#phase-title').textContent = ending ? ending.result === 'won' ? 'O lobisomem foi descoberto.' : 'A investigação chegou tarde demais.'
    : caseState.phase === 'night' ? 'A noite guarda seus segredos.' : 'O dia está terminando.';
  $('#phase-description').textContent = ending?.message ?? 'Floriano aguarda a manhã. Os acontecimentos serão publicados no Clarim do Rio.';
  $('#ending-new-case').hidden = !ending;
  setModal('phase');
  if (ending) $('#ending-new-case').focus();
  else {$('#phase-title').setAttribute('tabindex', '-1'); $('#phase-title').focus({preventScroll: true});}
}

function renderJournal() {
  const edition = caseState?.journal.at(-1);
  $('#journal-day').textContent = `DIA ${edition?.day ?? caseState?.day ?? 1}`;
  $('#journal-title').textContent = edition?.title ?? 'O Clarim do Rio';
  $('#journal-headline').textContent = edition?.headline ?? 'Uma cidade à espera de respostas';
  $('#journal-body').textContent = edition?.body ?? 'A edição desta manhã está sendo preparada.';
  $('#journal-location').textContent = edition?.location_id ? `Acontecimento registrado: ${locationName(edition.location_id)}.` : 'Nenhuma nova cena de crime foi anunciada.';
  const snapshot = $<HTMLElement>('#journal-snapshot');
  snapshot.hidden = !edition?.victim_id;
  $('#journal-snapshot-caption').textContent = edition?.location_id
    ? `Registro da madrugada · ${locationName(edition.location_id)}` : 'Registro de arquivo do Clarim do Rio';
}

function renderCase() {
  if (!caseState) return;
  $('#evidence-count').textContent = `${caseState.inventory.length} ${caseState.inventory.length === 1 ? 'pista' : 'pistas'}`;
  $('#case-hint-title').textContent = caseState.detained_npc_id
    ? 'Uma detenção. Uma noite de espera.' : `${caseState.inventory.length} vestígios, ${caseState.testimonies.length} depoimentos.`;
  $('#case-hint').textContent = caseState.detained_npc_id
    ? 'O acusado ficará na cela esta noite. O jornal trará os acontecimentos da manhã.'
    : 'Recolha vestígios nas cenas do crime. Mostre-os aos moradores e confronte versões antes de chamar o delegado.';
  renderJournal(); renderPresentation(); renderInterrogation(); renderNotebook();
  if (modal !== 'delegate') renderAccusation();
}

function renderNotebook() {
  if (!caseState) return;
  const inventory = $('#evidence-list'); inventory.replaceChildren();
  for (const evidence of caseState.inventory) {
    const item = document.createElement('article'); item.className = 'evidence-card'; item.dataset.evidenceId = evidence.id;
    item.append(itemArt(evidence.item_id, evidence.kind));
    const details = document.createElement('div'); details.className = 'evidence-details';
    addText(details, 'span', itemKind(evidence), 'evidence-kind'); addText(details, 'h4', evidence.name);
    addText(details, 'p', evidence.description); item.append(details); inventory.append(item);
  }
  if (!caseState.inventory.length) addText(inventory, 'p', 'Nenhum vestígio recolhido. Procure as marcas de cena do crime no cenário.', 'empty-case');
  const testimonyList = $('#testimony-list'); testimonyList.replaceChildren();
  for (const testimony of caseState.testimonies) {
    const item = document.createElement('article'); item.className = 'testimony-card';
    const evidence = caseState.inventory.find(item => item.id === testimony.evidence_id);
    if (evidence) item.append(itemArt(evidence.item_id, evidence.kind));
    addText(item, 'h4', `${testimony.witness_name} · dia ${testimony.day}`);
    addText(item, 'small', evidence?.name ?? 'Vestígio apresentado'); addText(item, 'p', testimony.text); testimonyList.append(item);
  }
  if (!caseState.testimonies.length) addText(testimonyList, 'p', 'Apresente um objeto durante uma conversa para registrar um depoimento.', 'empty-case');
  const crimes = $('#crime-list'); crimes.replaceChildren();
  for (const crime of caseState.crimes) addText(crimes, 'p', `${crime.victim_name} · ${locationName(crime.location_id)} · ${crime.remaining_clues ? `${crime.remaining_clues} vestígio(s) por encontrar` : 'busca concluída'}`);
  const alibis = $('#interrogation-list'); alibis.replaceChildren();
  for (const record of caseState.interrogations ?? []) {
    const card = document.createElement('article'); card.className = 'testimony-card';
    addText(card, 'h4', `${record.npc_name} · ${periodLabel(record.day, record.period)}`);
    addText(card, 'p', record.text);
    for (const observation of record.observations) addText(card, 'small', `${observation.source === 'observed' ? 'Diz ter visto' : 'Diz ter ouvido sobre'} ${npcName(observation.npc_id)} em ${locationName(observation.location_id ?? '')}: ${observation.activity}`);
    alibis.append(card);
  }
  if (!alibis.childElementCount) addText(alibis, 'p', 'Interrogue os moradores sobre onde estavam, o que faziam e quem os acompanhava.', 'empty-case');
  const confrontations = $('#confrontation-list'); confrontations.replaceChildren();
  for (const record of caseState.confrontations ?? []) {
    const card = document.createElement('article'); card.className = 'testimony-card';
    addText(card, 'h4', `${npcName(record.npc_id)} · dia ${record.day}`); addText(card, 'p', record.text); confrontations.append(card);
  }
  renderReports();
}

function renderReports() {
  const reports = $('#heard-report-list'); reports.replaceChildren();
  for (const report of heardReports) {
    const item = document.createElement('article'); item.className = 'testimony-card';
    addText(item, 'h4', report.speaker_name);
    addText(item, 'small', report.source_name ? `Fonte atribuída: ${report.source_name}` : 'Versão ouvida em conversa');
    addText(item, 'p', report.content); reports.append(item);
  }
  if (!heardReports.length) addText(reports, 'p', 'As versões que os moradores contarem a Floriano ficarão registradas aqui.', 'empty-case');
}

function renderPresentation() {
  const panel = $('#evidence-presenter'); const select = $<HTMLSelectElement>('#present-evidence');
  let preview = $('#presented-evidence-art');
  if (!preview) {preview = document.createElement('span'); preview.id = 'presented-evidence-art'; preview.className = 'item-art-preview'; select.before(preview);}
  const selected = select.value; select.replaceChildren();
  for (const evidence of caseState?.inventory ?? []) {
    const option = document.createElement('option'); option.value = evidence.id; option.textContent = evidence.name; select.append(option);
  }
  if ([...select.options].some(option => option.value === selected)) select.value = selected;
  const selectedEvidence = caseState?.inventory.find(item => item.id === select.value);
  preview.replaceChildren();
  if (selectedEvidence) preview.append(itemArt(selectedEvidence.item_id, selectedEvidence.kind));
  panel.hidden = !caseState?.inventory.length;
  $('#present-button').toggleAttribute('disabled', busy || caseClock.blocked());
}

function renderInterrogation() {
  if (!caseState) return;
  const day = $<HTMLInputElement>('#interrogation-day'); day.max = String(caseState.day);
  const proofs = $('#confrontation-proofs');
  const selected = new Set([...proofs.querySelectorAll<HTMLInputElement>('input:checked')].map(input => input.value));
  proofs.replaceChildren();
  const choice = (kind: string, id: string, text: string) => {
    const label = document.createElement('label'); label.className = 'proof-choice';
    const input = document.createElement('input'); input.type = 'checkbox'; input.name = kind; input.value = id;
    input.checked = selected.has(id); const caption = document.createElement('span'); caption.textContent = text;
    label.append(input, caption); proofs.append(label);
  };
  for (const evidence of caseState.inventory) choice('confront-evidence', evidence.id, evidence.name);
  for (const testimony of caseState.testimonies) choice('confront-testimony', testimony.id, `${testimony.witness_name}: ${testimony.text}`);
  for (const record of caseState.interrogations ?? []) choice('confront-interrogation', record.id, `${record.npc_name} · ${periodLabel(record.day, record.period)}: ${record.text}`);
  if (!proofs.childElementCount) addText(proofs, 'p', 'Reúna provas e registre versões antes de confrontar.', 'empty-case');
}

async function interrogateNPC() {
  if (!world || !dialogueNPC || !conversation || busy || modal !== 'dialogue' || caseClock.blocked()) return;
  const day = $<HTMLInputElement>('#interrogation-day');
  if (!day.reportValidity()) return;
  const period = $<HTMLSelectElement>('#interrogation-period').value as 'night' | 'day';
  const gameID = world.game_id, npcID = dialogueNPC.npc_id;
  busy = true; setSending(true); status('#interrogation-status', 'Registrando a versão do morador…');
  try {
    const result = await api.interrogate(gameID, npcID, Number(day.value), period);
    if (world?.game_id !== gameID) return;
    await applyCase(result);
    const record = result.interrogations?.find(item => item.npc_id === npcID && item.day === Number(day.value) && item.period === period);
    status('#interrogation-status', record?.text ?? 'Versão registrada no caderno.');
  } catch (error) {status('#interrogation-status', explain(error), true);}
  finally {busy = false; setSending(false);}
}

async function confrontNPC() {
  if (!world || !dialogueNPC || !conversation || busy || modal !== 'dialogue' || caseClock.blocked()) return;
  const chosen = (kind: string) => [...$('#confrontation-proofs').querySelectorAll<HTMLInputElement>(`input[name="${kind}"]:checked`)].map(input => input.value);
  const gameID = world.game_id, npcID = dialogueNPC.npc_id;
  busy = true; setSending(true); status('#confrontation-status', 'O morador examina os elementos apresentados…');
  try {
    const result = await api.confront(gameID, npcID, chosen('confront-evidence'), chosen('confront-testimony'), chosen('confront-interrogation'));
    if (world?.game_id !== gameID) return;
    await applyCase(result);
    status('#confrontation-status', result.confrontations?.filter(record => record.npc_id === npcID).at(-1)?.text ?? 'Confronto registrado.');
  } catch (error) {status('#confrontation-status', explain(error), true);}
  finally {busy = false; setSending(false);}
}

function renderAccusation() {
  if (!caseState) return;
  const gallery = $('#accused-npc');
  const selected = gallery.querySelector<HTMLInputElement>('input:checked')?.value;
  gallery.replaceChildren();
  for (const member of cast) {
    const detained = member.character.id === caseState.detained_npc_id;
    const label = document.createElement('label'); label.className = 'suspect-card';
    const input = document.createElement('input'); input.type = 'radio'; input.name = 'accused-npc';
    input.value = member.character.id; input.required = true; input.disabled = !member.alive || detained;
    input.checked = !input.disabled && input.value === selected;
    const portrait = document.createElement('img'); portrait.src = portraitPath(member.character.id);
    portrait.alt = ''; portrait.width = 88; portrait.height = 96;
    const name = document.createElement('strong'); name.textContent = member.character.name;
    const availability = document.createElement('small'); availability.textContent = !member.alive ? 'Falecido' : detained ? 'Sob custódia' : 'Selecionar';
    label.append(input, portrait, name, availability); gallery.append(label);
  }
  const renderChoice = (container: HTMLElement, name: string, id: string, text: string, item?: CaseEvidence, witnessID?: string) => {
    const label = document.createElement('label'); label.className = 'proof-choice';
    const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.name = name; checkbox.value = id;
    const title = document.createElement('span'); title.textContent = text; label.append(checkbox);
    if (witnessID) {
      const portrait = document.createElement('img'); portrait.className = 'witness-portrait';
      portrait.src = portraitPath(witnessID); portrait.alt = ''; portrait.width = 36; portrait.height = 42;
      label.append(portrait);
    }
    if (item) label.append(itemArt(item.item_id, item.kind));
    label.append(title); container.append(label);
  };
  const evidence = $('#accusation-evidence'); evidence.replaceChildren();
  caseState.inventory.forEach(item => renderChoice(evidence, 'evidence', item.id, `${item.name} · ${itemKind(item)}`, item));
  if (!caseState.inventory.length) addText(evidence, 'p', 'Você ainda não recolheu vestígios.', 'empty-case');
  const testimonies = $('#accusation-testimonies'); testimonies.replaceChildren();
  const inventorySnapshot = caseState.inventory;
  caseState.testimonies.forEach(item => renderChoice(testimonies, 'testimony', item.id, `${item.witness_name}: ${item.text}`, inventorySnapshot.find(evidence => evidence.id === item.evidence_id), item.witness_id));
  if (!caseState.testimonies.length) addText(testimonies, 'p', 'Nenhum depoimento sobre objetos registrado.', 'empty-case');
  const attempted = caseState.accusations.some(accusation => accusation.day === caseState?.day);
  updateAccusationSelection();
  if (attempted) status('#accusation-status', 'O delegado já examinou uma acusação neste dia. Aguarde a próxima manhã.');
  const history = $('#accusation-history'); history.replaceChildren();
  for (const accusation of caseState.accusations) {
    const card = document.createElement('article'); card.className = 'accusation-result';
    addText(card, 'strong', `${accusation.suspect_name} · ${accusation.accepted ? 'detenção autorizada' : 'pedido recusado'} · dia ${accusation.day}`);
    addText(card, 'p', accusation.reason); history.append(card);
  }
}

function updateAccusationSelection() {
  const selected = $('#accused-npc').querySelector<HTMLInputElement>('input:checked:not(:disabled)');
  for (const input of $('#accused-npc').querySelectorAll<HTMLInputElement>('input:not(:disabled)')) {
    input.closest('label')!.querySelector('small')!.textContent = input.checked ? 'Selecionado' : 'Selecionar';
  }
  $('#accused-selection').textContent = selected ? `Pedido de prisão contra ${npcName(selected.value)}.` : 'Nenhum suspeito selecionado.';
  const attempted = caseState?.accusations.some(accusation => accusation.day === caseState?.day);
  $('#submit-accusation').toggleAttribute('disabled', !selected || busy || caseClock.blocked() || Boolean(attempted));
}

async function openCasePanel(panel: 'journal' | 'notebook' | 'delegate') {
  if (!world || busy || modal || caseClock.blocked()) return;
  await settleMovement();
  if (caseClock.blocked()) return;
  if (panel === 'delegate') {renderAccusation(); status('#accusation-status', '');}
  setModal(panel); $(`#close-${panel}`).focus();
  if (panel === 'notebook') {
    const gameID = world.game_id;
    status('#reports-status', 'Consultando suas anotações…');
    try {
      const result = await api.reports(gameID);
      if (world?.game_id !== gameID) return;
      heardReports = result.reports; renderReports(); status('#reports-status', '');
    } catch {
      if (world?.game_id === gameID) status('#reports-status', 'Não foi possível atualizar os relatos. Tente reabrir o caderno.', true);
    }
  }
}

async function searchCrime(id?: string) {
  if (!world || !controller || busy || modal || caseClock.blocked()) return;
  const crime = closestCrime(caseState, world, controller.x);
  if (!crime || (id && crime.id !== id)) return;
  busy = true;
  try {
    await controller.stop();
    const before = new Set(caseState?.inventory.map(item => item.id));
    const result = await api.search(world.game_id, crime.id);
    await applyCase(result);
    const found = result.inventory.find(item => !before.has(item.id));
    toast(found ? `Vestígio recolhido: ${found.name}. Você pode apresentá-lo aos moradores.` : 'A busca nesta cena foi concluída.');
  } catch (error) {toast(explain(error));}
  finally {busy = false;}
}

async function presentEvidence() {
  if (!world || !dialogueNPC || busy || modal !== 'dialogue' || caseClock.blocked()) return;
  const evidenceID = $<HTMLSelectElement>('#present-evidence').value; if (!evidenceID) return;
  busy = true; setSending(true); status('#presentation-status', 'O morador examina o objeto…');
  try {
    const result = await api.present(world.game_id, evidenceID, dialogueNPC.npc_id);
    await applyCase(result);
    const testimony = result.testimonies.find(item => item.evidence_id === evidenceID && item.witness_id === dialogueNPC?.npc_id);
    status('#presentation-status', testimony?.text ?? 'Depoimento registrado no caderno.');
  } catch (error) {status('#presentation-status', explain(error), true);}
  finally {busy = false; setSending(false);}
}

async function submitAccusation(event: Event) {
  event.preventDefault(); if (!world || busy || modal !== 'delegate' || caseClock.blocked()) return;
  const suspectID = $('#accused-npc').querySelector<HTMLInputElement>('input:checked:not(:disabled)')?.value;
  if (!suspectID) {status('#accusation-status', 'Selecione um suspeito antes de apresentar a acusação.', true); return;}
  const evidence = [...document.querySelectorAll<HTMLInputElement>('#accusation-evidence input:checked')].map(input => input.value);
  const testimony = [...document.querySelectorAll<HTMLInputElement>('#accusation-testimonies input:checked')].map(input => input.value);
  busy = true; $('#submit-accusation').setAttribute('disabled', ''); status('#accusation-status', 'O delegado examina os elementos apresentados…');
  try {
    const result = await api.accuse(world.game_id, suspectID, evidence, testimony);
    await applyCase(result); renderAccusation();
    const decision = result.accusations.at(-1);
    status('#accusation-status', decision?.reason ?? 'Pedido registrado.');
  } catch (error) {status('#accusation-status', explain(error), true);}
  finally {busy = false; updateAccusationSelection();}
}

setInterval(renderClock, 250);
$('#inspect-crime').addEventListener('click', () => {void searchCrime();});
$('#present-button').addEventListener('click', () => {void presentEvidence();});
$('#present-evidence').addEventListener('change', () => renderPresentation());
$('#interrogate-button').addEventListener('click', () => {void interrogateNPC();});
$('#confront-button').addEventListener('click', () => {void confrontNPC();});
$('#accusation-form').addEventListener('submit', event => {void submitAccusation(event);});
$('#accused-npc').addEventListener('change', updateAccusationSelection);
for (const panel of ['journal', 'notebook', 'delegate'] as const) {
  $(`#open-${panel}`).addEventListener('click', () => {void openCasePanel(panel);});
  $(`#close-${panel}`).addEventListener('click', () => {if (!busy) setModal(null);});
}
$('#read-journal').addEventListener('click', () => {if (!busy) setModal(null);});
$('#ending-new-case').addEventListener('click', () => {setModal(null); void launch(false);});

$('#start').addEventListener('click', () => {void launch(false);});
$('#continue').hidden = !savedGame();
$('#continue').addEventListener('click', () => {void launch(true);});
$('#new-case').addEventListener('click', async () => {
  if (busy) return;
  casePoller.stop(); await settleMovement(); setModal(null); $('#investigation').hidden = true; $('#introduction').hidden = false;
  $('#continue').hidden = !savedGame(); document.body.classList.remove('case-active');
});
$('#open-map').addEventListener('click', () => {void openMap();});
$('#close-map').addEventListener('click', () => {if (!busy) setModal(null);});
$('#close-exit').addEventListener('click', () => {if (!busy) setModal(null);});
$('#stay-here').addEventListener('click', () => {if (!busy) setModal(null);});
$('#approach').addEventListener('click', () => {void approach();});
for (const [id, direction] of [['walk-left', 'left'], ['walk-right', 'right']] as const) {
  const button = $(`#${id}`);
  button.addEventListener('pointerdown', event => {
    if (modal || busy || caseClock.blocked()) return;
    event.preventDefault(); button.setPointerCapture(event.pointerId); scene?.setTouchDirection(direction);
  });
  for (const event of ['pointerup', 'pointercancel', 'lostpointercapture']) button.addEventListener(event, () => scene?.setTouchDirection('idle'));
}

$('#close-dialogue').addEventListener('click', () => {if (!busy) setModal(null);});
$('#message-form').addEventListener('submit', event => {void sendMessage(event);});
$('#message-input').addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey) {event.preventDefault(); $('#message-form').dispatchEvent(new Event('submit', {cancelable: true}));}
});
$('#message-input').addEventListener('input', () => {
  if (world && conversation) dialogueDrafts.set(`${world.game_id}:${conversation.id}`, $<HTMLTextAreaElement>('#message-input').value);
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && modal && modal !== 'phase' && !busy) {event.preventDefault(); setModal(null);}
  if (event.key === 'Tab' && modal) {
    const overlay = $(`#${modal}-overlay`);
    const focusable = [...overlay.querySelectorAll<HTMLElement>('button:not([disabled]):not([hidden]),textarea:not([disabled]),select:not([disabled]),input:not([disabled])')].filter(element => element.getClientRects().length);
    if (!focusable.length) {event.preventDefault(); if (modal === 'phase') $('#phase-title').focus(); return;}
    const first = focusable[0], last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {event.preventDefault(); last.focus();}
    else if (!event.shiftKey && document.activeElement === last) {event.preventDefault(); first.focus();}
  }
});
window.addEventListener('blur', () => {if (!caseClock.blocked()) void controller?.stop(); else void controller?.suspend();});
window.addEventListener('pagehide', () => {casePoller.stop(); controller?.dispose();});
