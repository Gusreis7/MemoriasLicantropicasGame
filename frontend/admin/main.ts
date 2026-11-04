import './style.css';
import {personWords} from '../shared/language';
import {
  ApiError, request, nameOf, formatDate, locationNames, deathAuthor, eventDetails, eventLabels,
  type Page, type GameSummary, type GameState, type Conversation, type Message,
  type EventRecord, type Interactions, type SocialState, type UsageSummary, type UsageTotals,
} from './api';

const $ = <T extends HTMLElement = HTMLElement>(id: string): T => {
  const result = document.getElementById(id);
  if (!result) throw new Error(`Elemento ausente: ${id}`);
  return result as T;
};
const make = <K extends keyof HTMLElementTagNameMap>(tag: K, className = '', text?: string): HTMLElementTagNameMap[K] => {
  const node = document.createElement(tag);
  node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
};

const PAGE = 20;
const MESSAGE_PAGE = 100;
let username: string | null = null;
let selectedGame: string | null = null;
let selectedConversation: Conversation | null = null;
let gamesOffset = 0;
let conversationsOffset = 0;
let eventsOffset = 0;
let messagesOffset = 0;
let conversations: Conversation[] = [];
let polling = false;
let selectionVersion = 0;

const gameUrl = new URL(window.location.href);
gameUrl.port = '7077'; gameUrl.pathname = '/'; gameUrl.search = ''; gameUrl.hash = '';
$<HTMLAnchorElement>('game-link').href = gameUrl.href;
$<HTMLAnchorElement>('start-game-link').href = gameUrl.href;

function status(message = '', failed = false): void {
  $('status').textContent = message;
  $('status').classList.toggle('failed', failed);
}

function showLogin(message = ''): void {
  $('boot-state').hidden = true;
  username = null;
  selectedGame = null;
  selectedConversation = null;
  selectionVersion += 1;
  $('dashboard').hidden = true;
  $('login-view').hidden = false;
  $('login-error').textContent = message;
  $<HTMLInputElement>('password').value = '';
}

function handleError(error: unknown): void {
  if (error instanceof ApiError && error.status === 401) {
    showLogin('Sua sessão terminou. Entre novamente para continuar.');
    return;
  }
  status(error instanceof Error ? error.message : 'Não foi possível consultar o arquivo.', true);
}

async function authenticated(user: string): Promise<void> {
  $('boot-state').hidden = true;
  username = user;
  $('login-view').hidden = true;
  $('dashboard').hidden = false;
  $('session-user').textContent = user;
  $('game-content').hidden = true;
  $('empty-state').hidden = false;
  $('selected-folio').textContent = 'Selecione uma partida no arquivo';
  status();
  await Promise.all([loadGames(), loadHealth()]);
}

function pagination(target: HTMLElement, offset: number, total: number, limit: number, change: (offset: number) => void): void {
  target.replaceChildren();
  if (!total) return;
  const previous = make('button', '', '←');
  previous.type = 'button'; previous.disabled = offset === 0;
  previous.setAttribute('aria-label', 'Página anterior');
  previous.addEventListener('click', () => change(Math.max(0, offset - limit)));
  const next = make('button', '', '→');
  next.type = 'button'; next.disabled = offset + limit >= total;
  next.setAttribute('aria-label', 'Próxima página');
  next.addEventListener('click', () => change(offset + limit));
  target.append(previous, make('span', '', `${offset + 1}–${Math.min(offset + limit, total)} de ${total}`), next);
}

async function loadGames(): Promise<void> {
  const requestedUser = username;
  const offset = gamesOffset;
  const page = await request<Page<GameSummary>>(`/games?offset=${offset}&limit=${PAGE}`);
  if (!username || username !== requestedUser || gamesOffset !== offset) return;
  $('games-count').textContent = String(page.total);
  const list = $('games-list'); list.replaceChildren();
  if (!page.items.length) list.append(make('p', 'sidebar-empty', 'Nenhuma partida registrada.'));
  for (const game of page.items) {
    const button = make('button', 'game-item'); button.type = 'button';
    button.classList.toggle('selected', game.id === selectedGame);
    button.setAttribute('aria-pressed', String(game.id === selectedGame));
    button.dataset.gameId = game.id;
    const heading = make('span', 'game-item-title', `Caso ${game.id.slice(0, 8)}`);
    const meta = make('span', 'game-item-meta', formatDate(game.created_at));
    const badge = make('span', 'game-status', game.status === 'active' ? 'Em andamento' : game.status);
    button.append(heading, meta, badge);
    button.addEventListener('click', () => void selectGame(game.id).catch(handleError));
    list.append(button);
  }
  pagination($('games-pagination'), gamesOffset, page.total, PAGE, offset => {
    gamesOffset = offset; void loadGames().catch(handleError);
  });
}

async function loadHealth(): Promise<void> {
  let healthy = false;
  try { healthy = (await request<{redis: string}>('/health')).redis === 'ok'; }
  catch (error) { if (error instanceof ApiError && error.status === 401) throw error; }
  $('health-dot').classList.toggle('healthy', healthy);
  $('health-label').textContent = healthy ? 'Redis conectado' : 'Redis indisponível';
}

async function selectGame(id: string): Promise<void> {
  selectedGame = id;
  selectedConversation = null;
  conversationsOffset = eventsOffset = messagesOffset = 0;
  conversations = [];
  selectionVersion += 1;
  const version = selectionVersion;
  status('Consultando os registros da partida…');
  $('game-content').hidden = true;
  $('empty-state').hidden = true;
  $('transcript-title').textContent = 'Selecione um encontro';
  $('messages').replaceChildren(make('p', 'empty-copy', 'A transcrição será exibida aqui.'));
  $('messages-pagination').replaceChildren();
  $('messages-count').textContent = '';
  switchTab('overview');
  await Promise.all([loadOverview(version), loadConversations(version), loadEvents(version)]);
  if (version !== selectionVersion) return;
  $('game-content').hidden = false;
  $('selected-folio').textContent = `Partida ${id}`;
  document.querySelectorAll<HTMLButtonElement>('.game-item').forEach(button => {
    button.classList.toggle('selected', button.dataset.gameId === id);
    button.setAttribute('aria-pressed', String(button.dataset.gameId === id));
  });
  status();
}

async function loadOverview(version = selectionVersion): Promise<void> {
  const game = selectedGame;
  if (!game) return;
  const [record, interactions, social, usage] = await Promise.all([
    request<GameState>(`/games/${game}/state`), request<Interactions>(`/games/${game}/interactions`),
    request<SocialState>(`/games/${game}/social`),
    request<UsageSummary>(`/games/${game}/usage`).catch(error => {
      if (error instanceof ApiError && error.status === 401) throw error;
      return null;
    }),
  ]);
  if (version !== selectionVersion || game !== selectedGame || !username) return;
  renderState(record);
  renderGraph(interactions);
  renderSocial(social);
  renderUsage(usage);
  $('game-content').hidden = false;
  $('empty-state').hidden = true;
}

const purposeNames: Record<string, string> = {
  player_dialogue: 'Conversas com Floriano', social_speech: 'Conversas entre moradores',
  knowledge_extraction: 'Extração de memórias', evaluation: 'Avaliação',
};
const tokenNumber = (value: number): string => new Intl.NumberFormat('pt-BR').format(value);
const estimatedUSD = (value: string): string => new Intl.NumberFormat('pt-BR', {
  style: 'currency', currency: 'USD', minimumFractionDigits: 6, maximumFractionDigits: 8,
}).format(Number(value));

function renderUsage(usage: UsageSummary | null): void {
  let panel = document.getElementById('usage-section');
  if (!panel) {
    panel = make('section', 'paper-panel usage-panel'); panel.id = 'usage-section';
    $('overview-panel').append(panel);
  }
  panel.replaceChildren(make('span', 'eyebrow', 'CONSUMO POR PARTIDA'), make('h2', '', 'Tokens e custo estimado.'));
  if (!usage) {
    panel.append(make('p', 'empty-copy', 'A medição está indisponível. Atualize para tentar consultar novamente.'));
    return;
  }
  if (usage.coverage === 'not_recorded') {
    panel.append(make('p', 'empty-copy', 'Ainda não há chamadas medidas nesta partida. O consumo de conversas anteriores à medição é desconhecido.'));
    return;
  }
  const totals = usage.totals;
  const cards = make('div', 'usage-stats');
  cards.append(stat('TOKENS DE ENTRADA', tokenNumber(totals.known_input_tokens), 'Total conhecido informado pelo provedor'),
    stat('TOKENS DE SAÍDA', tokenNumber(totals.known_output_tokens), 'Total conhecido informado pelo provedor'),
    stat(totals.cost_complete ? 'CUSTO ESTIMADO' : 'SUBTOTAL ESTIMADO', estimatedUSD(totals.known_estimated_cost_usd),
      totals.cost_complete ? 'Das chamadas registradas, antes de créditos e impostos' : 'Parcial: existem chamadas sem tokens ou tarifa'));
  panel.append(cards, make('p', 'panel-description', `${totals.calls} chamada(s) · ${totals.completed_calls} concluída(s) · ${totals.failed_calls} falha(s) · ${totals.cancelled_calls} cancelada(s) · ${totals.calls_with_missing_tokens} sem contagem completa · ${totals.unpriced_calls} sem tarifa · ${(totals.duration_ms / 1000).toFixed(1)}s de inferência acumulada`));
  const breakdown = (heading: string, rows: Array<UsageTotals & {key: string}>, names: Record<string, string>) => {
    panel!.append(make('h3', '', heading));
    const scroll = make('div', 'usage-table-scroll'); const table = make('table', 'usage-table');
    const head = make('thead'); const header = make('tr');
    for (const label of ['Finalidade / modelo', 'Chamadas', 'Entrada', 'Saída', 'Estimativa USD']) header.append(make('th', '', label));
    head.append(header); table.append(head); const body = make('tbody');
    for (const row of rows) {
      const tr = make('tr');
      for (const text of [names[row.key] ?? row.key, String(row.calls), tokenNumber(row.known_input_tokens),
        tokenNumber(row.known_output_tokens), `${estimatedUSD(row.known_estimated_cost_usd)}${row.cost_complete ? '' : ' (parcial)'}`]) tr.append(make('td', '', text));
      body.append(tr);
    }
    table.append(body); scroll.append(table); panel!.append(scroll);
  };
  breakdown('Por finalidade', usage.by_purpose, purposeNames);
  breakdown('Por modelo configurado', usage.by_model, {});
  panel.append(make('p', 'panel-description', usage.note), make('p', 'panel-description', `Medição registrada de ${usage.first_recorded_at ? formatDate(usage.first_recorded_at) : 'data desconhecida'} até ${usage.last_recorded_at ? formatDate(usage.last_recorded_at) : 'data desconhecida'}.`));
  for (const rate of usage.pricing_snapshots) {
    const line = make('p', 'panel-description', `${rate.model}: entrada ${rate.input_usd_per_million ?? 'desconhecida'}, saída ${rate.output_usd_per_million ?? 'desconhecida'} USD por milhão de tokens · tarifa verificada em ${rate.checked_at ?? 'data não registrada'} · `);
    if (rate.source.startsWith('https://')) {
      const source = make('a', '', 'Fonte da tarifa'); source.href = rate.source; source.target = '_blank'; source.rel = 'noopener noreferrer'; line.append(source);
    }
    panel.append(line);
  }
}

function renderSocial(state: SocialState): void {
  let panel = document.getElementById('social-section');
  if (!panel) {
    panel = make('section', 'paper-panel social-panel'); panel.id = 'social-section';
    $('overview-panel').append(panel);
  }
  const expanded = new Set([...panel.querySelectorAll<HTMLDetailsElement>('details[open]')].map(item => item.dataset.recordId));
  panel.replaceChildren(make('span', 'eyebrow', 'CONVIVÊNCIA E PROVENIÊNCIA'), make('h2', '', 'As versões que circulam.'));
  const usage = state.days.map(day => `Dia ${day.day}: ${day.speech_calls}/16 falas · ${day.extraction_calls}/8 extrações`).join(' | ');
  panel.append(make('p', 'panel-description', `${state.knowledge.length} lembranças · ${state.encounters.length} encontros · revisão ${state.revision}${usage ? ` · ${usage}` : ''}`));

  const relations = make('details', 'social-details'); relations.dataset.recordId = 'relations'; relations.open = expanded.has('relations');
  relations.append(make('summary', '', 'Relações direcionais'));
  for (const relation of state.relationships) {
    relations.append(make('p', 'panel-description', `${nameOf(relation.actor_id)} → ${nameOf(relation.target_id)}: ${relation.sentiment_label ?? ""} ${Object.entries(relation.sentiments ?? {}).map(([name,value]) => `${name} ${value}`).join(", ")} · afinidade ${relation.affinity}, confiança ${relation.trust}, ressentimento ${relation.resentment} · ${relation.causes.length} causa(s)`));
  }
  panel.append(relations, make('h3', '', 'Encontros e falas confirmadas'));
  if (!state.encounters.length) panel.append(make('p', 'empty-copy', 'Nenhum encontro social registrado.'));
  for (const encounter of [...state.encounters].reverse()) {
    const details = make('details', 'social-details'); details.dataset.recordId = encounter.id; details.open = expanded.has(encounter.id);
    details.append(make('summary', '', `${encounter.participant_ids.map(nameOf).join(' ↔ ')} · dia ${encounter.day} · ${locationNames[encounter.location_id] ?? encounter.location_id} · ${encounter.phase}`));
    if (encounter.reason) details.append(make('p', 'panel-description', encounter.reason));
    for (const message of encounter.messages) {
      const speech = make('article', 'message');
      speech.append(make('strong', '', `${nameOf(message.sender_id)} · ${message.intent}`), make('p', 'message-content', message.content),
        make('small', 'source-tag', `Relatos: ${message.claim_ids.map(id => id.slice(0, 8)).join(', ') || 'nenhum'} · ${formatDate(message.created_at)}`));
      details.append(speech);
    }
    panel.append(details);
  }
  panel.append(make('h3', '', 'Memórias e cadeias de transmissão'));
  if (!state.knowledge.length) panel.append(make('p', 'empty-copy', 'Nenhum relato processado.'));
  for (const entry of [...state.knowledge].reverse()) {
    const details = make('details', 'social-details'); details.dataset.recordId = entry.id; details.open = expanded.has(entry.id);
    details.append(make('summary', '', `${nameOf(entry.owner_id)} ouviu ${nameOf(entry.speaker_id)} · ${entry.kind} · ${entry.day === null ? 'dia não registrado' : `dia ${entry.day}`}`));
    details.append(make('p', 'message-content', entry.proposition), make('blockquote', 'panel-description', entry.source_span));
    details.append(make('p', 'panel-description', `Fonte alegada: ${entry.claimed_source_id ? nameOf(entry.claimed_source_id) : 'não indicada'} · posição: ${entry.stance} · confiança: ${entry.confidence}`),
      make('p', 'social-identifiers', `ID ${entry.id} · raiz ${entry.root_id} · mensagem ${entry.source_message_id} · deriva de ${entry.parent_ids.join(', ') || 'origem'}`));
    panel.append(details);
  }
}

function stat(label: string, value: string, note: string, highlighted = false): HTMLElement {
  const card = make('article', `stat-card${highlighted ? ' secret' : ''}`);
  card.append(make('span', 'eyebrow', label), make('strong', 'stat-value', value), make('span', 'stat-note', note));
  return card;
}

function renderState(record: GameState): void {
  const cycle = record.investigation;
  $('cycle-section').hidden = !cycle;
  if (cycle) {
    const phase = cycle.phase === 'day' ? 'Dia' : cycle.phase === 'night' ? 'Noite' : 'Encerrado';
    $('cycle-summary').textContent = `Dia ${cycle.day} · ${phase} · ${cycle.detained_npc_id ? `Sob custódia: ${nameOf(cycle.detained_npc_id)}` : 'Sem detenção'} · Prazo: ${formatDate(cycle.phase_ends_at)}`;
    const story=cycle.night_story as {skipped_nights:number;plot?:{planner_id:string;target_id:string;status:string;stress:number}}|undefined;
    if(story?.plot) $('cycle-summary').textContent+=` · Plano civil: ${nameOf(story.plot.planner_id)} → ${nameOf(story.plot.target_id)} · ${story.plot.status} · estresse ${story.plot.stress} · noites poupadas pela fera: ${story.skipped_nights}`;
    $('cycle-details').textContent = JSON.stringify(cycle, null, 2);
  }
  const alive = record.characters.filter(character => character.alive).length;
  const wolf = record.characters.find(character => character.character_id === record.werewolf_id);
  $('case-meta').textContent = `Aberta em ${formatDate(record.created_at)} · fichas v${record.content_version} · mundo ${record.world_version || 'não inicializado'}`;
  $('stats').replaceChildren(
    stat('PAPEL SECRETO', wolf?.name || nameOf(record.werewolf_id), 'Lobisomem sorteado nesta partida', true),
    stat('PERSONAGENS VIVOS', `${alive} / ${record.characters.length}`, 'Estado registrado no sistema'),
    stat('LOCAL DO DETETIVE', locationNames[record.player?.location_id || ''] || 'Não registrado', 'Última posição confirmada'),
  );
  const cards = $('characters'); cards.replaceChildren();
  for (const character of record.characters) {
    const card = make('article', 'character-card');
    const portrait = make('img', 'portrait');
    portrait.src = `/assets/portraits/${encodeURIComponent(character.character_id)}.png`;
    portrait.alt = `Retrato de ${character.name}`;
    portrait.addEventListener('error', () => { portrait.hidden = true; }, {once: true});
    const details = make('div', 'character-details');
    const title = make('h3', '', character.name);
    const role = make('span', `role-badge ${character.role === 'werewolf' ? 'wolf' : ''}`, character.role === 'werewolf' ? 'Lobisomem' : 'Civil');
    const confirmedWolf = record.status === 'won' && character.character_id === record.werewolf_id;
    const confessed = confirmedWolf && cycle?.ending_method === 'confession';
    const expelled = confirmedWolf && !confessed;
    const words=personWords(character);
    const place = confessed ? 'Delegacia · confissão registrada' : expelled ? `${words.expelled} · expulsão confirmada` : locationNames[character.location_id || ''] || 'Local não registrado';
    details.append(title, role, make('p', 'character-location', place),
      make('span', `life-status${character.alive ? '' : ' deceased'}`, confessed ? '● Sob custódia · confessou' : expelled ? `↗ ${words.expelled}` : character.alive ? `● ${words.alive}` : `○ ${words.deceased}`));
    card.append(portrait, details); cards.append(card);
  }
  const deaths = $('deaths'); deaths.replaceChildren();
  if (!record.known_deaths.length) deaths.append(make('p', 'empty-copy', 'Nenhuma morte registrada.'));
  for (const death of record.known_deaths) {
    const item = make('article', 'death-item');
    item.append(make('span', 'death-symbol', '†'), make('h3', '', death.victim_name || nameOf(death.victim_id)),
      make('p', 'death-author', deathAuthor(death)), make('span', 'source-tag', death.source === 'scenario' || death.source === 'story' ? 'Contexto narrativo' : `Origem: ${death.source}`));
    deaths.append(item);
  }
}

function renderGraph(data: Interactions): void {
  const root = $('graph'); root.replaceChildren(); $('graph-legend').replaceChildren();
  if (!data.nodes.length || !data.edges.length) {
    root.append(make('div', 'graph-empty', 'Ainda não há encontros registrados. As primeiras mensagens formarão os fios deste mapa.'));
    return;
  }
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('viewBox', '0 0 620 350'); svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', 'Grafo de interações registradas. As ligações abrem suas conversas.');
  const positions = new Map<string, {x: number; y: number}>();
  const ring = data.nodes.filter(node => node.id !== 'player');
  ring.forEach((node, index) => {
    const angle = (index / Math.max(1, ring.length)) * Math.PI * 2 - Math.PI / 2;
    positions.set(node.id, {x: 310 + Math.cos(angle) * 224, y: 175 + Math.sin(angle) * 124});
  });
  positions.set('player', {x: 310, y: 175});
  for (const edge of data.edges) {
    const start = positions.get(edge.source), end = positions.get(edge.target);
    if (!start || !end) continue;
    const group = document.createElementNS(ns, 'g');
    group.setAttribute('role', 'button'); group.setAttribute('tabindex', '0');
    group.classList.add('graph-edge');
    const label = `${nameOf(edge.source)} e ${nameOf(edge.target)}: ${edge.message_count} mensagens. Abrir conversa.`;
    group.setAttribute('aria-label', label);
    const title = document.createElementNS(ns, 'title'); title.textContent = label;
    const line = document.createElementNS(ns, 'line');
    line.setAttribute('x1', String(start.x)); line.setAttribute('y1', String(start.y));
    line.setAttribute('x2', String(end.x)); line.setAttribute('y2', String(end.y));
    line.classList.add('edge-visible'); line.style.strokeWidth = String(Math.min(5, 1.4 + edge.message_count / 10));
    const hit = line.cloneNode() as SVGLineElement; hit.classList.remove('edge-visible'); hit.classList.add('edge-hit');
    const activate = () => {
      switchTab('conversations');
      const existing = conversations.find(conversation => conversation.id === edge.conversation_id);
      void selectConversation(existing ?? {id: edge.conversation_id, game_id: selectedGame!, participant_ids: [edge.source, edge.target], created_at: edge.last_at || ''}).catch(handleError);
    };
    group.addEventListener('click', activate);
    group.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); activate(); } });
    group.append(title, line, hit); svg.append(group);
  }
  for (const node of data.nodes) {
    const point = positions.get(node.id); if (!point) continue;
    const group = document.createElementNS(ns, 'g'); group.classList.add('graph-node');
    const circle = document.createElementNS(ns, 'circle');
    circle.setAttribute('cx', String(point.x)); circle.setAttribute('cy', String(point.y)); circle.setAttribute('r', node.id === 'player' ? '20' : '13');
    if (node.id === 'player') circle.classList.add('player-node');
    const text = document.createElementNS(ns, 'text');
    text.setAttribute('x', String(point.x)); text.setAttribute('y', String(point.y + 34)); text.setAttribute('text-anchor', 'middle');
    text.textContent = node.name;
    const initials = document.createElementNS(ns, 'text');
    initials.setAttribute('x', String(point.x)); initials.setAttribute('y', String(point.y + 4)); initials.setAttribute('text-anchor', 'middle'); initials.classList.add('node-initial');
    initials.textContent = node.id === 'player' ? 'F' : node.name.slice(0, 1);
    group.append(circle, initials, text); svg.append(group);
  }
  root.append(svg);
  const messages = data.edges.reduce((total, edge) => total + edge.message_count, 0);
  $('graph-legend').append(make('span', '', `${data.edges.length} encontros`), make('span', '', `${messages} mensagens registradas`));
}

async function loadConversations(version = selectionVersion): Promise<void> {
  const game = selectedGame; if (!game) return;
  const offset = conversationsOffset;
  const page = await request<Page<Conversation>>(`/games/${game}/conversations?offset=${offset}&limit=${PAGE}`);
  if (version !== selectionVersion || game !== selectedGame || offset !== conversationsOffset) return;
  conversations = page.items;
  renderConversations();
  pagination($('conversations-pagination'), conversationsOffset, page.total, PAGE, offset => {
    conversationsOffset = offset; void loadConversations().catch(handleError);
  });
}

function renderConversations(): void {
  const filter = $<HTMLInputElement>('participant-filter').value.trim().toLocaleLowerCase('pt-BR');
  const list = $('conversations-list'); list.replaceChildren();
  const visible = conversations.filter(conversation => conversation.participant_ids.some(id => `${id} ${nameOf(id)}`.toLocaleLowerCase('pt-BR').includes(filter)));
  if (!visible.length) list.append(make('p', 'empty-copy', filter ? 'Nenhum encontro nesta página corresponde ao filtro.' : 'Nenhuma conversa registrada.'));
  for (const conversation of visible) {
    const button = make('button', 'conversation-item'); button.type = 'button';
    button.classList.toggle('selected', conversation.id === selectedConversation?.id);
    button.append(make('strong', '', conversation.participant_ids.map(nameOf).join(' ↔ ')),
      make('span', '', formatDate(conversation.created_at)), make('small', '', conversation.id.slice(0, 8)));
    button.addEventListener('click', () => void selectConversation(conversation).catch(handleError));
    list.append(button);
  }
}

async function selectConversation(conversation: Conversation): Promise<void> {
  selectedConversation = conversation; messagesOffset = 0;
  $('transcript-title').textContent = conversation.participant_ids.map(nameOf).join(' ↔ ');
  renderConversations();
  await loadMessages();
}

async function loadMessages(): Promise<void> {
  const game = selectedGame, conversation = selectedConversation;
  if (!game || !conversation) return;
  const version = selectionVersion;
  const offset = messagesOffset;
  const page = await request<Page<Message>>(`/games/${game}/conversations/${conversation.id}/messages?offset=${offset}&limit=${MESSAGE_PAGE}`);
  if (version !== selectionVersion || conversation.id !== selectedConversation?.id || offset !== messagesOffset) return;
  const list = $('messages'); list.replaceChildren();
  $('messages-count').textContent = `${page.total} mensagens`;
  if (!page.items.length) list.append(make('p', 'empty-copy', 'Este encontro ainda não tem mensagens.'));
  for (const message of page.items) {
    const item = make('article', `message${message.sender_id === 'player' ? ' player-message' : ''}`);
    const header = make('div', 'message-header');
    header.append(make('strong', '', nameOf(message.sender_id)), make('time', '', formatDate(message.created_at)));
    item.append(header, make('p', 'message-content', message.content)); list.append(item);
  }
  pagination($('messages-pagination'), messagesOffset, page.total, MESSAGE_PAGE, offset => {
    messagesOffset = offset; void loadMessages().catch(handleError);
  });
}

async function loadEvents(version = selectionVersion): Promise<void> {
  const game = selectedGame; if (!game) return;
  const offset = eventsOffset;
  const page = await request<Page<EventRecord>>(`/games/${game}/events?offset=${offset}&limit=50`);
  if (version !== selectionVersion || game !== selectedGame || offset !== eventsOffset) return;
  const list = $('events'); list.replaceChildren();
  if (!page.items.length) list.append(make('p', 'empty-copy', 'Nenhum acontecimento registrado nesta partida.'));
  for (const event of page.items) {
    const item = make('article', 'event-item');
    const mark = make('span', 'event-mark', event.type.includes('death') || event.type.includes('killed') ? '†' : '•');
    const details = make('div', 'event-details');
    const header = make('div', 'event-header');
    header.append(make('h3', '', eventLabels[event.type] || event.type), make('time', '', formatDate(event.occurred_at)));
    details.append(header, make('p', '', eventDetails(event)), make('span', 'source-tag', `Origem: ${event.source}`));
    item.append(mark, details); list.append(item);
  }
  pagination($('events-pagination'), eventsOffset, page.total, 50, offset => {
    eventsOffset = offset; void loadEvents().catch(handleError);
  });
}

function switchTab(name: string): void {
  document.querySelectorAll<HTMLButtonElement>('[data-tab]').forEach(button => button.setAttribute('aria-selected', String(button.dataset.tab === name)));
  for (const tab of ['overview', 'conversations', 'events']) $(`${tab}-panel`).hidden = tab !== name;
}

$<HTMLFormElement>('login-form').addEventListener('submit', async event => {
  event.preventDefault();
  const button = $<HTMLButtonElement>('login-button');
  const password = $<HTMLInputElement>('password');
  $('login-error').textContent = ''; button.disabled = true;
  try {
    const session = await request<{username: string}>('/auth/login', {username: $<HTMLInputElement>('username').value, password: password.value});
    password.value = '';
    await authenticated(session.username);
  } catch (error) { $('login-error').textContent = error instanceof Error ? error.message : 'Não foi possível entrar.'; }
  finally { password.value = ''; button.disabled = false; }
});
$('logout').addEventListener('click', async () => {
  try { await request('/auth/logout', {}); showLogin(); }
  catch (error) { handleError(error); }
});
document.querySelectorAll<HTMLButtonElement>('[data-tab]').forEach(button => button.addEventListener('click', () => switchTab(button.dataset.tab!)));
$<HTMLInputElement>('participant-filter').addEventListener('input', renderConversations);
$('refresh').addEventListener('click', async () => {
  const button = $<HTMLButtonElement>('refresh'); button.disabled = true;
  try {
    await Promise.all([loadGames(), loadHealth(), loadOverview(), loadConversations(), loadEvents(), loadMessages()]);
    status('Arquivo atualizado.');
  } catch (error) { handleError(error); }
  finally { button.disabled = false; }
});

setInterval(() => {
  if (!username || document.hidden || polling) return;
  const focus = document.activeElement;
  if (focus && ['games-list', 'games-pagination', 'graph'].some(id => $(id).contains(focus))) return;
  polling = true;
  // Não recriar transcrição, filtros ou paginação enquanto o operador lê/escreve.
  void Promise.all([loadGames(), loadHealth(), loadOverview()]).catch(handleError).finally(() => { polling = false; });
}, 5000);

void request<{username: string}>('/auth/session').then(session => authenticated(session.username)).catch(error => {
  showLogin(error instanceof ApiError && error.status === 401 ? '' : 'Não foi possível verificar a sessão. Tente entrar.');
});
