import {api, ApiError, type CharacterManifest, type Conversation, type Location, type LocationID, type Message, type WorldSnapshot} from '../shared/api';
import {closestNPC, MovementController} from './movement';
import {CityScene, makeGame} from './scene';
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
        <div class="scene-frame"><div class="frame-corner top-left"></div><div class="frame-corner top-right"></div><div id="game-canvas" aria-label="Cenário lateral. Use as setas para andar e E para conversar." tabindex="0"></div><div class="scene-vignette" aria-hidden="true"></div><div id="scene-loading" class="scene-loading" role="status">Preparando a cidade…</div><div class="world-caption"><span class="caption-dot"></span><span id="world-caption">O bairro guarda suas histórias.</span></div><button id="approach" class="approach-button" type="button" hidden><kbd>E</kbd><span></span></button></div>
        <div class="scene-footer"><div class="control-guide"><span><kbd>←</kbd><kbd>→</kbd> Caminhar</span><span><kbd>E</kbd> Conversar</span><span><kbd>M</kbd> Viajar</span></div><span class="connection-label" id="connection-label"><i></i> Caso em andamento</span></div>
        <div class="notebook"><div class="notebook-number">01</div><div><p class="eyebrow">O CADERNO DE FLORIANO</p><h2>Uma boa pergunta abre portas.</h2><p>Aproxime-se de um morador para ouvir sua versão. Às vezes, o que alguém evita dizer é tão revelador quanto o que conta.</p></div><span class="notebook-ornament" aria-hidden="true">✦</span></div>
      </section>
    </main>
    <footer class="site-footer"><span>MEMÓRIAS LICANTROPICAS</span><span>Nem toda história é contada por inteiro.</span><span>UMA INVESTIGAÇÃO EM PIXELS</span></footer>
  </div>

  <div id="map-overlay" class="overlay" hidden><section class="map-modal" role="dialog" aria-modal="true" aria-labelledby="map-title"><header class="modal-heading"><div><p class="eyebrow">ESCOLHA SEU PRÓXIMO DESTINO</p><h2 id="map-title">Os caminhos da cidade</h2></div><button class="icon-button" id="close-map" aria-label="Fechar mapa" type="button">×</button></header><div class="city-map"><img src="/assets/map/city.png" alt="Mapa ilustrado do bairro, entre a praça, a cabana, a Casa Verde, o café e o cais."/><div id="map-destinations"></div></div><p class="map-caption">Cada encontro pode mudar o rumo desta história.</p><p id="map-status" class="status" role="status" aria-live="polite"></p></section></div>

  <div id="dialogue-overlay" class="overlay dialogue-overlay" hidden><section class="dialogue-modal" role="dialog" aria-modal="true" aria-labelledby="dialogue-name"><aside class="persona-panel"><div class="persona-frame"><img id="persona-portrait" src="" alt=""/></div><p class="eyebrow">DEPOIMENTO</p><h2 id="dialogue-name"></h2><span class="persona-flourish" aria-hidden="true">— ✦ —</span><p>Nem toda verdade vem à primeira pergunta.</p></aside><div class="conversation-panel"><header class="conversation-heading"><div><span class="conversation-dot"></span><span>Conversa com Floriano</span></div><button id="close-dialogue" class="icon-button" type="button" aria-label="Encerrar conversa">×</button></header><div id="messages" class="messages" role="log" aria-live="polite"></div><div id="dialogue-status" class="status dialogue-status" role="status" aria-live="polite"></div><form id="message-form" class="message-form"><label class="sr-only" for="message-input">Sua pergunta</label><textarea id="message-input" rows="2" maxlength="8000" placeholder="O que você gostaria de perguntar?" required></textarea><button id="send-message" class="button primary" type="submit" aria-label="Enviar pergunta">Enviar <span aria-hidden="true">→</span></button></form><p class="form-hint">Enter para enviar · Shift + Enter para uma nova linha</p></div></section></div>
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
let modal: 'map' | 'dialogue' | null = null;
let busy = false;
let starting = false;
let conversation: Conversation | null = null;
let dialogueNPC: {npc_id: string; name: string} | null = null;
let lastNearest = '';
let toastTimer: ReturnType<typeof setTimeout> | undefined;

function savedGame() { try { return localStorage.getItem(STORAGE_KEY); } catch { return null; } }
function saveGame(id: string) { try { localStorage.setItem(STORAGE_KEY, id); } catch { /* A sessão ainda funciona sem armazenamento local. */ } }
function status(selector: string, text: string, error = false) {const el = $(selector); el.textContent = text; el.classList.toggle('error', error);}
function explain(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 503) return 'A resposta não pôde chegar agora. Confira o histórico antes de reenviar sua pergunta.';
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
  $('#map-overlay').hidden = next !== 'map';
  $('#dialogue-overlay').hidden = next !== 'dialogue';
  scene?.setInputEnabled(next === null);
  $('#approach').hidden = true;
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
  starting = true;
  $('#start').setAttribute('disabled', ''); $('#continue').setAttribute('disabled', '');
  status('#launch-status', resume ? 'Reabrindo seu caderno…' : 'Preparando uma nova investigação…');
  try {
    const id = resume ? savedGame() : (await api.createGame()).id;
    if (!id) throw new Error('Não há caso salvo');
    saveGame(id);
    const [snapshot, places, characters] = await Promise.all([api.world(id), api.locations(), api.manifest()]);
    locations = places; manifest = characters;
    controller?.dispose(); game?.destroy(true);
    controller = new MovementController(snapshot, api.move, () => api.world(id), applySnapshot, error => toast(explain(error)));
    scene = new CityScene(manifest, locations, snapshot, {
      blocked: () => Boolean(modal || busy || starting || document.hidden || $('#investigation').hidden),
      frame: (delta, direction) => {
        controller?.update(delta, direction);
        if (controller && world) {
          const nearest = !modal && !busy ? closestNPC(world, controller.x) : undefined;
          if ((nearest?.npc_id ?? '') !== lastNearest) {
            lastNearest = nearest?.npc_id ?? '';
            $('#approach').hidden = !nearest;
            $('#approach span').textContent = nearest ? `Conversar com ${nearest.name}` : '';
          }
        }
        return {x: controller?.x ?? snapshot.player.x,
          facing: direction === 'left' ? 'left' : direction === 'right' ? 'right' : controller?.world.player.facing ?? 'right'};
      },
      approach: () => {void approach();}, map: () => {void openMap();},
      loaded: () => {$('#scene-loading').hidden = true; $('#game-canvas').focus({preventScroll: true});},
      failed: () => {$('#scene-loading').hidden = false; $('#scene-loading').textContent = 'Não foi possível carregar a arte da cidade. Recarregue para tentar novamente.';},
    });
    modal = null; busy = false; lastNearest = '';
    $('#introduction').hidden = true; $('#investigation').hidden = false;
    $('#scene-loading').hidden = false; $('#scene-loading').textContent = 'Abrindo os caminhos da cidade…';
    applySnapshot(snapshot);
    game = makeGame($('#game-canvas'), scene);
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
  if (!world || !controller || busy || modal) return;
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

async function travel(target: LocationID) {
  if (!world || !controller || busy) return;
  busy = true; renderMap(); status('#map-status', 'Seguindo por outro caminho…');
  try {
    const snapshot = await api.travel(controller.world, target);
    controller.accept(snapshot); setModal(null); toast(`Você chegou: ${snapshot.location.name}.`);
  } catch (error) {
    status('#map-status', explain(error), true);
    if (error instanceof ApiError && error.status === 409) {
      try {controller.accept(await api.world(world.game_id));} catch { /* mantém erro visível */ }
    }
  } finally {busy = false; renderMap(); lastNearest = '';}
}

async function approach() {
  if (!world || !controller || busy || modal) return;
  const npc = closestNPC(world, controller.x);
  if (!npc) {toast('Aproxime-se de um morador para conversar.'); return;}
  busy = true;
  await settleMovement();
  busy = true; dialogueNPC = npc; conversation = null;
  setModal('dialogue');
  $('#dialogue-name').textContent = npc.name;
  const image = $('#persona-portrait') as HTMLImageElement;
  image.src = manifest.characters.find(asset => asset.id === npc.npc_id)?.portraitPath ?? `/assets/portraits/${npc.npc_id}.png`;
  image.alt = `Retrato de ${npc.name}`;
  $('#messages').replaceChildren(); status('#dialogue-status', 'Abrindo o caderno desta conversa…');
  setSending(true);
  try {
    conversation = await api.approach(world.game_id, npc.npc_id);
    await refreshHistory(); status('#dialogue-status', '');
  } catch (error) {status('#dialogue-status', explain(error), true);}
  finally {busy = false; setSending(false); $('#message-input').focus();}
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
  const history = await api.history(world.game_id, conversation.id);
  $('#messages').replaceChildren();
  if (!history.messages.length) {
    const empty = document.createElement('div'); empty.className = 'conversation-opening';
    empty.textContent = 'O primeiro passo de uma investigação é saber escutar. Faça sua pergunta.';
    $('#messages').append(empty);
  } else history.messages.forEach(appendMessage);
  $('#messages').scrollTop = $('#messages').scrollHeight;
}

function setSending(sending: boolean) {
  $('#send-message').toggleAttribute('disabled', sending || !conversation);
  $('#message-input').toggleAttribute('disabled', sending || !conversation);
  $('#close-dialogue').toggleAttribute('disabled', sending);
}

async function sendMessage(event: Event) {
  event.preventDefault();
  if (!conversation || !world || busy) return;
  const input = $('#message-input') as HTMLTextAreaElement;
  const content = input.value.trim(); if (!content) return;
  busy = true; setSending(true); status('#dialogue-status', `${dialogueNPC?.name ?? 'A persona'} está respondendo…`);
  try {
    await api.send(world.game_id, conversation.id, content);
    input.value = ''; await refreshHistory(); status('#dialogue-status', '');
  } catch (error) {
    // A confirmação pode ter se perdido; ler é seguro, reenviar automaticamente não é.
    try {await refreshHistory();} catch { /* mantém a mensagem original de erro */ }
    status('#dialogue-status', explain(error), true);
  } finally {busy = false; setSending(false); input.focus();}
}

$('#start').addEventListener('click', () => {void launch(false);});
$('#continue').hidden = !savedGame();
$('#continue').addEventListener('click', () => {void launch(true);});
$('#new-case').addEventListener('click', async () => {
  if (busy) return;
  await settleMovement(); setModal(null); $('#investigation').hidden = true; $('#introduction').hidden = false;
  $('#continue').hidden = !savedGame(); document.body.classList.remove('case-active');
});
$('#open-map').addEventListener('click', () => {void openMap();});
$('#close-map').addEventListener('click', () => {if (!busy) setModal(null);});
$('#approach').addEventListener('click', () => {void approach();});
$('#close-dialogue').addEventListener('click', () => {if (!busy) setModal(null);});
$('#message-form').addEventListener('submit', event => {void sendMessage(event);});
$('#message-input').addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey) {event.preventDefault(); $('#message-form').dispatchEvent(new Event('submit', {cancelable: true}));}
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && modal && !busy) {event.preventDefault(); setModal(null);}
  if (event.key === 'Tab' && modal) {
    const overlay = modal === 'map' ? $('#map-overlay') : $('#dialogue-overlay');
    const focusable = [...overlay.querySelectorAll<HTMLElement>('button:not([disabled]),textarea:not([disabled])')];
    if (!focusable.length) return;
    const first = focusable[0], last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {event.preventDefault(); last.focus();}
    else if (!event.shiftKey && document.activeElement === last) {event.preventDefault(); first.focus();}
  }
});
window.addEventListener('blur', () => {void controller?.stop();});
window.addEventListener('pagehide', () => {controller?.dispose();});
