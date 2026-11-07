import {api, ApiError, type CasePublic, type CaseEvidence, type CaseTestimony, type GamePublic, type CharacterManifest, type Conversation, type ExitSide, type Location, type LocationID, type Message, type HeardReport, type WorldSnapshot} from '../shared/api';
import {closestNPC, MovementController} from './movement';
import {ExitBoundary} from './exits';
import {CaseClock, CasePoller, closestCrime, formatClock, formatGameTime, gameDayProgress} from './case';
import {CityScene, makeGame} from './scene';
import {sendDialogue} from './dialogue';
import {CustodyScene, makeCustodyGame, type CustodyMode} from './custody';
import {personWords} from '../shared/language';
import {POPULATION} from './population';
import './style.css';
import {cancelNightAttack, newNightVictim, playNightAttack} from './night-attack';
import {gameAudio} from './audio';
import {renderDefeatPhoto} from './defeat-photo';
import {canSubmitCaseReport, caseReportKind, caseReportStatus} from './table-reports';
import {dossierEvidence} from './dossier-selection';

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
        <div class="case-toolbar"><div class="day-clock"><span id="case-day">DIA 1</span><strong id="case-clock" aria-label="Horário na cidade">09:00</strong><small id="case-phase">Investigue até as 18h</small></div><nav aria-label="Ferramentas de investigação"><button id="open-journal" class="button secondary small" type="button">O Clarim do Rio</button><button id="open-notebook" class="button secondary small" type="button" title="Abrir ou fechar o caderno (C)">Caderno <kbd>C</kbd> <span id="evidence-count">0 pistas</span></button><button id="open-assembly" class="button secondary small" type="button">Assembleia da cidade</button><button id="open-delegate" class="button secondary small" type="button">Chamar o delegado</button><button id="skip-day" class="button secondary small" type="button" title="Encerrar o dia, resolver a noite e ler o jornal da manhã seguinte">Pular o dia <span aria-hidden="true">↠</span></button></nav></div><div class="scene-frame"><div class="frame-corner top-left"></div><div class="frame-corner top-right"></div><div id="game-canvas" aria-label="Cenário lateral. Use as setas para andar e E para conversar." tabindex="0"></div><div class="scene-vignette" aria-hidden="true"></div><div id="scene-loading" class="scene-loading" role="status">Preparando a cidade…</div><div class="world-caption"><span class="caption-dot"></span><span id="world-caption">O bairro guarda suas histórias.</span></div><button id="inspect-crime" class="approach-button inspect-button" type="button" hidden><kbd>E</kbd><span>Procurar vestígios</span></button><button id="approach" class="approach-button" type="button" hidden><kbd>E</kbd><span></span></button></div>
        <div class="scene-footer"><div class="touch-controls" aria-label="Caminhar pela cidade"><button id="walk-left" type="button" aria-label="Caminhar para a esquerda">←</button><button id="walk-right" type="button" aria-label="Caminhar para a direita">→</button></div><div class="control-guide"><span><kbd>←</kbd><kbd>→</kbd> Caminhar</span><span><kbd>E</kbd> Conversar</span><span><kbd>M</kbd> Viajar</span></div><span class="connection-label" id="connection-label"><i></i> Caso em andamento</span></div>
        <div class="notebook"><div class="notebook-number">01</div><div><p class="eyebrow">O CADERNO DE FLORIANO</p><h2 id="case-hint-title">Uma boa pergunta abre portas.</h2><p id="case-hint">Aproxime-se de um morador para ouvir sua versão. Procure marcas de cenas do crime e apresente os vestígios recolhidos.</p></div><span class="notebook-ornament" aria-hidden="true">✦</span></div>
      </section>
    </main>
    <footer class="site-footer"><span>MEMÓRIAS LICANTROPICAS</span><span>Nem toda história é contada por inteiro.</span><span>UMA INVESTIGAÇÃO EM PIXELS</span></footer>
  </div>

  <div id="map-overlay" class="overlay" hidden><section class="map-modal" role="dialog" aria-modal="true" aria-labelledby="map-title"><header class="modal-heading"><div><p class="eyebrow">ESCOLHA SEU PRÓXIMO DESTINO</p><h2 id="map-title">Os caminhos da cidade</h2></div><button class="icon-button" id="close-map" aria-label="Fechar mapa" type="button">×</button></header><div class="city-map"><img src="/assets/map/city.png" alt="Mapa ilustrado do bairro, entre a praça, a cabana, a Casa Verde, o café e o cais."/><div id="map-destinations"></div></div><div id="map-residents" class="map-residents" aria-live="polite"></div><p class="map-caption">Cada encontro pode mudar o rumo desta história.</p><p id="map-status" class="status" role="status" aria-live="polite"></p></section></div>

  <div id="exit-overlay" class="overlay" hidden><section class="exit-modal" role="dialog" aria-modal="true" aria-labelledby="exit-title" aria-describedby="exit-description"><header class="modal-heading"><div><p class="eyebrow">NO FIM DESTA RUA</p><h2 id="exit-title">Por onde seguimos?</h2></div><button class="icon-button" id="close-exit" aria-label="Ficar neste local" type="button">×</button></header><p id="exit-description">Escolha um caminho para continuar a investigação.</p><div id="exit-destinations" class="exit-destinations"></div><p id="exit-status" class="status" role="status" aria-live="polite"></p><button id="stay-here" class="button secondary" type="button">Ficar neste local</button></section></div>

  <div id="dialogue-overlay" class="overlay dialogue-overlay" hidden><section class="dialogue-modal" role="dialog" aria-modal="true" aria-labelledby="dialogue-name"><aside class="persona-panel"><div class="persona-frame"><img id="persona-portrait" src="" alt=""/></div><p class="eyebrow">DEPOIMENTO</p><h2 id="dialogue-name"></h2><span class="persona-flourish" aria-hidden="true">— ✦ —</span><p>Nem toda verdade vem à primeira pergunta.</p></aside><div class="conversation-panel"><header class="conversation-heading"><div><span class="conversation-dot"></span><span>Conversa com Floriano</span></div><button id="close-dialogue" class="icon-button" type="button" aria-label="Encerrar conversa">×</button></header><div id="messages" class="messages" role="log" aria-live="polite"></div><div id="dialogue-status" class="status dialogue-status" role="status" aria-live="polite"></div><div id="evidence-presenter" class="evidence-presenter" hidden><label for="present-evidence">Mostrar um vestígio</label><div><select id="present-evidence"></select><button id="present-button" class="button small" type="button">Apresentar</button></div><p id="presentation-status" role="status" aria-live="polite"></p></div><form id="message-form" class="message-form"><label class="sr-only" for="message-input">Sua pergunta</label><textarea id="message-input" rows="2" maxlength="8000" placeholder="Pergunte, retome uma pista ou confronte uma versão…" required></textarea><button id="send-message" class="button primary" type="submit" aria-label="Enviar pergunta">Enviar <span aria-hidden="true">→</span></button></form><p class="form-hint">Pergunte sobre álibis e contradições na conversa. Enter envia · Shift + Enter quebra a linha</p></div></section></div>
  <div id="journal-overlay" class="overlay" hidden><section class="journal-modal case-modal" role="dialog" aria-modal="true" aria-labelledby="journal-title"><header class="newspaper-masthead"><div class="newspaper-dateline"><span>RIO DE JANEIRO</span><span>EDIÇÃO DA MANHÃ</span><button id="close-journal" class="icon-button" type="button" aria-label="Fechar jornal">×</button></div><h2 id="journal-title">O Clarim do Rio</h2><div class="newspaper-edition"><span>NOTÍCIAS DA CIDADE · 1890</span><span id="journal-day"></span></div></header><article class="newspaper-story"><p class="journal-motto">Os acontecimentos da cidade, à luz do dia.</p><p id="journal-death-toll" class="journal-death-toll"></p><h3 id="journal-headline"></h3><figure id="journal-victim" class="journal-victim" hidden><img id="journal-victim-image" alt=""/><figcaption id="journal-victim-caption"></figcaption></figure><figure id="journal-snapshot" class="journal-snapshot" hidden><img id="journal-image" src="/assets/press/crime-scene-snapshot.png" alt="Registro monocromático de uma rua carioca à noite, com um chapéu caído e pegadas no calçamento."/><figcaption id="journal-snapshot-caption"></figcaption></figure><p id="journal-body"></p><p id="journal-location" class="journal-location"></p></article><button id="read-journal" class="button primary" type="button">Continuar a investigação</button></section></div>
  <div id="notebook-overlay" class="overlay notebook-overlay" hidden><section class="case-modal notebook-modal" role="dialog" aria-modal="true" aria-labelledby="notebook-title"><header class="notebook-heading"><div><p class="eyebrow">ANOTAÇÕES DE FLORIANO · 1890</p><h2 id="notebook-title">Caderno de campo</h2></div><button id="close-notebook" class="icon-button" type="button" aria-label="Fechar caderno">×</button></header><div class="notebook-book"><div class="notebook-page-stack" aria-hidden="true"></div><div class="notebook-page-markers" aria-hidden="true"><span class="notebook-page-marker notebook-page-marker-residents">01 · Moradores</span><span class="notebook-page-marker notebook-page-marker-clues">02 · Pistas</span><span class="notebook-page-marker notebook-page-marker-reports">03 · Relatos</span></div><div class="notebook-spread"><aside class="notebook-page notebook-suspect-page" aria-labelledby="notebook-suspects-title"><header class="notebook-page-heading"><span>FOLHA 01</span><h3 id="notebook-suspects-title">Os moradores</h3><p>Sete destinos, uma sombra.</p></header><div id="notebook-suspects" class="notebook-suspects" aria-live="polite"></div></aside><section class="notebook-page notebook-notes-page" aria-label="Anotações do caso"><div class="notebook-tabs" role="tablist" aria-label="Seções do caderno"><button id="notebook-tab-clues" class="notebook-tab" type="button" role="tab" aria-selected="true" aria-controls="notebook-clues" tabindex="0">Pistas <kbd>1</kbd></button><button id="notebook-tab-reports" class="notebook-tab" type="button" role="tab" aria-selected="false" aria-controls="notebook-reports" tabindex="-1">Relatos <kbd>2</kbd></button></div><div id="notebook-clues" class="notebook-tab-panel" role="tabpanel" aria-labelledby="notebook-tab-clues"><header class="notebook-page-heading"><span>FOLHA 02 · INDÍCIOS</span><h3>O que ficou para trás</h3><p>Vestígios, versões e contradições.</p></header><section class="notebook-section"><h4>Vestígios recolhidos</h4><div id="evidence-list" class="evidence-list"></div></section><section id="achievements-section" class="notebook-section discoveries-section"><h4>Descobertas</h4><p id="achievement-progress" class="achievement-progress"></p><div id="achievement-list" class="achievement-list"></div></section><section class="notebook-section"><h4>Depoimentos sobre objetos</h4><div id="testimony-list" class="testimony-list"></div></section><section class="notebook-section"><h4>Álibis e interrogatórios</h4><div id="interrogation-list" class="testimony-list"></div></section><section class="notebook-section"><h4>Confrontos</h4><div id="confrontation-list" class="testimony-list"></div></section><section class="notebook-section"><h4>Cenas conhecidas</h4><div id="crime-list" class="crime-list"></div></section></div><div id="notebook-reports" class="notebook-tab-panel" role="tabpanel" aria-labelledby="notebook-tab-reports" hidden><header class="notebook-page-heading"><span>FOLHA 02 · VOZES DA CIDADE</span><h3>O que dizem pelas ruas</h3><p>Uma notícia conserva a voz e a fonte de quem a contou.</p></header><p id="reports-status" class="status notebook-status" role="status" aria-live="polite"></p><div id="heard-report-list" class="testimony-list"></div></div></section></div></div><footer class="notebook-shortcuts"><span><kbd>C</kbd> guardar o caderno</span><span><kbd>1</kbd> pistas</span><span><kbd>2</kbd> relatos</span><span><kbd>Esc</kbd> fechar</span></footer></section></div>
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
        <p class="case-note delegate-introduction">Examine uma marca pessoal e reúna corroboração, ou apresente dois exclusivos distintos reconhecidos por duas testemunhas cada. Objetos comuns, sozinhos, não bastam. Escolha quem deseja acusar e apresente os vestígios e depoimentos que sustentam sua suspeita.</p>
        <form id="accusation-form">
          <fieldset class="suspect-fieldset"><legend><span class="case-step">01</span> Quem você acusa?</legend><p class="delegate-field-hint">Escolha um morador para examinar o pedido de prisão.</p><div id="accused-npc" class="suspect-gallery"></div><p id="accused-selection" class="accused-selection" role="status" aria-live="polite">Nenhum suspeito selecionado.</p></fieldset>
          <div class="accusation-records"><fieldset><legend><span class="case-step">02</span> Vestígios recolhidos</legend><div id="accusation-evidence"></div></fieldset><fieldset><legend><span class="case-step">03</span> Depoimentos registrados</legend><div id="accusation-testimonies"></div></fieldset></div>
          <p id="accusation-review" class="status" role="status" aria-live="polite">Confira o dossiê para saber o que ainda falta. Uma recusa permite completar as provas e tentar novamente hoje.</p><div class="accusation-submit"><button id="review-accusation" class="button secondary" type="button" disabled>Conferir dossiê</button><p id="accusation-status" class="status" role="status" aria-live="polite"></p><button id="submit-accusation" class="button primary" type="submit" disabled>Apresentar acusação <span aria-hidden="true">→</span></button></div>
        </form><div id="accusation-history"></div>
      </div>
    </section>
  </div>
  <div id="assembly-overlay" class="overlay assembly-overlay" hidden><section class="case-modal assembly-modal" role="dialog" aria-modal="true" aria-labelledby="assembly-title"><header class="modal-heading"><div><p class="eyebrow">A PALAVRA NA PRAÇA</p><h2 id="assembly-title">Assembleia da cidade</h2></div><button id="close-assembly" class="icon-button" type="button" aria-label="Guardar a assembleia">×</button></header><p class="case-note assembly-rule">Uma convocação por partida. Exponha seu caso, ouça os moradores e faça uma réplica antes da votação. O debate dura até um minuto. Eles também podem votar para expulsar Floriano — e encerrar sua investigação.</p><div id="assembly-preparation"><fieldset class="suspect-fieldset"><legend>Quem você acusa?</legend><div id="assembly-suspects" class="suspect-gallery"></div></fieldset><div class="assembly-dossier"><fieldset><legend>Pistas</legend><div id="assembly-evidence"></div></fieldset><fieldset><legend>Depoimentos</legend><div id="assembly-testimonies"></div></fieldset></div><form id="assembly-opening-form"><label for="assembly-opening">Conte à cidade o que aconteceu</label><textarea id="assembly-opening" rows="3" maxlength="800" placeholder="Explique por que suspeita desta pessoa e como as pistas sustentam sua versão." required></textarea><div class="assembly-form-footer"><small id="assembly-opening-count">0 / 800</small><button id="start-assembly" class="button primary" type="submit">Convocar e expor o caso</button></div></form></div><div id="assembly-debate" hidden><div class="assembly-session-heading"><p id="assembly-subject"></p><strong id="assembly-countdown" role="timer" aria-label="Tempo restante do debate"></strong></div><div id="assembly-chat" class="assembly-chat" role="log" aria-live="polite" aria-label="Falas da assembleia"></div><form id="assembly-reply-form"><label for="assembly-reply">Sua última palavra</label><textarea id="assembly-reply" rows="2" maxlength="500" placeholder="Responda às dúvidas e peça o voto dos moradores."></textarea><div class="assembly-form-footer"><small id="assembly-reply-count">0 / 500</small><button id="finish-assembly" class="button primary" type="submit">Concluir e votar</button></div></form></div><div id="assembly-result" aria-live="polite"></div><p id="assembly-status" class="status" role="status" aria-live="polite"></p></section></div>
  <div id="custody-overlay" class="overlay custody-overlay" hidden><section class="custody-modal" role="dialog" aria-modal="true" aria-labelledby="custody-title"><header><p class="eyebrow">NA DELEGACIA</p><h2 id="custody-title">Uma noite sob custódia</h2><p id="custody-caption" role="status" aria-live="polite"></p></header><div id="custody-canvas" aria-label="Cena da delegacia com a pessoa detida atrás das grades"></div><footer><span id="custody-clock"></span><button id="leave-custody" class="button secondary" type="button">Voltar à investigação</button></footer></section></div>
  <div id="phase-overlay" class="overlay phase-overlay" hidden><section class="case-modal phase-modal" role="dialog" aria-modal="true" aria-labelledby="phase-title" aria-describedby="phase-description"><article id="victory-paper" class="victory-paper" hidden><header class="newspaper-masthead"><div class="newspaper-dateline"><span>RIO DE JANEIRO · 1890</span><span>EDIÇÃO EXTRAORDINÁRIA</span></div><h2>O Clarim do Rio</h2><div class="newspaper-edition"><span>A VITÓRIA DE FLORIANO</span><span id="victory-day"></span></div></header><h3 id="victory-headline"></h3><div class="press-picture press-victory" role="img" aria-label="Ilustração em preto e branco da cidade celebrando Floriano"></div><p id="victory-body"></p><p class="victory-ending">O caso está encerrado. A cidade volta a respirar.</p></article><span class="phase-moon" aria-hidden="true">☾</span><p class="eyebrow" id="phase-eyebrow">A CIDADE RECOLHE-SE</p><h2 id="phase-title">A noite guarda seus segredos.</h2><p id="phase-description">Floriano aguarda a manhã. Os acontecimentos serão publicados no Clarim do Rio.</p><p id="phase-countdown" role="status" aria-live="polite"></p><button id="ending-new-case" class="button primary" type="button" hidden>Iniciar outro caso</button></section></div>
  <div id="toast" class="toast" role="status" aria-live="polite" hidden></div>
`;

const $ = <T extends HTMLElement = HTMLElement>(selector: string) => document.querySelector<T>(selector)!;
const defeatPhoto=document.createElement('img');
defeatPhoto.id='defeat-photo';defeatPhoto.className='press-defeat';defeatPhoto.width=600;defeatPhoto.height=400;defeatPhoto.hidden=true;
defeatPhoto.alt='Lobisomem nas sombras da cidade à meia-noite, em fotografia escurecida de jornal';
$('#victory-paper .press-picture').after(defeatPhoto);
let defeatEditionID:string|null=null;
let victoryEditionID:string|null=null;
let defeatPhotoAbort:AbortController|null=null;
const STORAGE_KEY = 'memorias-licantropicas:game';
const PERSONAL_ITEM_ICONS = new Set<string>([
  'rosario_seminario', 'carta_santiago', 'pente_olho_cobre', 'sinete_lua', 'caderneta_seminario',
  'abotoadeira_esmeralda', 'abotoadeira_sol', 'medalhao_quincas', 'camafeu_vn', 'frasco_violeta',
  'dedal_andorinha', 'fivela_manifesto', 'estilete_casa_verde', 'selo_casa_verde',
]);
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
let modal: 'map' | 'dialogue' | 'exit' | 'journal' | 'notebook' | 'delegate' | 'phase' | 'custody' | 'assembly' | null = null;
let exitSide: ExitSide | null = null;
let exitBoundary = new ExitBoundary();
let busy = false;
let transitioning = false;
let pendingWorldSync = false;
let caseState: CasePublic | null = null;
let heardReports: HeardReport[] = [];
let notebookTab: 'clues' | 'reports' = 'clues';
let cast: GamePublic['characters'] = [];
const caseClock = new CaseClock();
const casePoller = new CasePoller();
let starting = false;
let conversation: Conversation | null = null;
let conversationMessages: Message[] = [];
let historyReady = false;
let dialogueUnavailable = false;
let renewingDialogue = false;
const dialogueDrafts = new Map<string, string>();
let dialogueNPC: {npc_id: string; name: string} | null = null;
let custodyGame: ReturnType<typeof makeCustodyGame> | null = null;
let custodyScene: CustodyScene | null = null;
let custodyNpc: string | null = null;
let lastNearest = '';
let assemblyResolving = false;
let assemblyClockOffset = 0;
let assemblyTimeoutAttempt = '';
let assemblyRenderedRevision = '';
let assemblyDraftGame: string | null = null;
let toastTimer: ReturnType<typeof setTimeout> | undefined;
const inspectingEvidence = new Set<string>();

function savedGame() { try { return localStorage.getItem(STORAGE_KEY); } catch { return null; } }
function saveGame(id: string) { try { localStorage.setItem(STORAGE_KEY, id); } catch { /* A sessão ainda funciona sem armazenamento local. */ } }
function status(selector: string, text: string, error = false) {const el = $(selector); el.textContent = text; el.classList.toggle('error', error);}
function explain(error: unknown) {
  if (error instanceof ApiError) {
    return error.message;
  }
  return 'Algo interrompeu a investigação. Tente novamente em instantes.';
}
function toast(message: string) {
  clearTimeout(toastTimer); $('#toast').textContent = message; $('#toast').hidden = false;
  toastTimer = setTimeout(() => {$('#toast').hidden = true;}, 5000);
}

function setModal(next: typeof modal) {
  if(next!=='phase') {defeatPhotoAbort?.abort();defeatPhotoAbort=null;if(modal==='phase')gameAudio.stopCinematicEffects();}
  if (next !== modal && (next === 'journal' || next === 'notebook')) gameAudio.effect('paper');
  else if (next === null && (modal === 'journal' || modal === 'notebook')) gameAudio.effect('close');
  if (modal === 'dialogue' && next !== 'dialogue' && world && conversation) {
    dialogueDrafts.set(`${world.game_id}:${conversation.id}`, $<HTMLTextAreaElement>('#message-input').value);
    void api.closeConversation(world.game_id, conversation.id).catch(() => { /* Reserva expira automaticamente. */ });
  }
  modal = next;
  for (const name of ['map', 'dialogue', 'exit', 'journal', 'notebook', 'delegate', 'phase', 'custody', 'assembly']) $(`#${name}-overlay`).hidden = next !== name;
  scene?.setInputEnabled(next === null && !caseClock.blocked() && !activeAssembly());
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
  $('#game-canvas').setAttribute('aria-label',`${snapshot.location.name}. Use as setas para andar e E para conversar. Ao fundo: ${POPULATION[snapshot.location.id].map(person=>`${person.name}, ${person.occupation}`).join('; ')}.`);
  $('#world-caption').textContent = locationDescription[snapshot.location.id];
  scene?.apply(snapshot);
  if (modal === "map") renderMapResidents();
}

async function launch(resume: boolean) {
  if (starting) return;
  gameAudio.unlock(); gameAudio.start();
  starting = true; casePoller.stop();
  $('#start').setAttribute('disabled', ''); $('#continue').setAttribute('disabled', '');
  status('#launch-status', resume ? 'Reabrindo seu caderno…' : 'Preparando uma nova investigação…');
  try {
    const id = resume ? savedGame() : (await api.createGame()).id;
    if (!id) throw new Error('Não há caso salvo');
    saveGame(id);
    casePoller.stop();
    const investigation = await api.investigation(id);
    prepareJournalPortrait(investigation.journal.at(-1)?.victim_id);
    const [snapshot, places, characters, publicGame] = await Promise.all([api.world(id), api.locations(), api.manifest(), api.game(id)]);
    caseState = null; heardReports = []; pendingWorldSync = false; transitioning = false; cast = publicGame.characters;
    locations = places; manifest = characters;
    cancelNightAttack(); controller?.dispose(); game?.destroy(true); custodyGame?.destroy(true); custodyGame=null;custodyScene=null;custodyNpc=null;
    exitBoundary = new ExitBoundary();
    controller = new MovementController(snapshot, api.move, () => api.world(id), applySnapshot, error => toast(explain(error)));
    scene = new CityScene(manifest, locations, snapshot, {
      dayProgress: () => !caseState ? 0 : caseState.phase === 'day' ? gameDayProgress(caseClock.seconds()) : 1,
      blocked: () => Boolean(modal || activeAssembly() || busy || transitioning || starting || caseClock.blocked() || document.hidden || $('#investigation').hidden),
      frame: (delta, direction) => {
        const previousX = controller?.x;
        if (!caseClock.blocked() && !transitioning) controller?.update(delta, direction);
        if (direction !== 'idle' && controller?.direction !== 'idle' && previousX !== undefined && controller
          && Math.abs(controller.x - previousX) > .1) gameAudio.effect('step');
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
      loaded: () => {$('#scene-loading').hidden = true; scene?.setInputEnabled(modal === null && !caseClock.blocked() && !activeAssembly()); if (!modal) $('#game-canvas').focus({preventScroll: true});},
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
    if (resume && error instanceof ApiError && (error.status === 404 || error.status === 409)) {
      try {
        const unavailable = savedGame();
        if (unavailable) localStorage.removeItem(`memorias-licantropicas:assembly:${unavailable}`);
        localStorage.removeItem(STORAGE_KEY);
      } catch { /* O usuário ainda pode iniciar uma nova investigação sem armazenamento local. */ }
    }
    const message = error instanceof ApiError && (error.status === 404 || error.status === 409)
      ? 'Este caso não está disponível nesta edição. Inicie uma nova investigação para continuar.' : explain(error);
    status('#launch-status', message, true);
    $('#continue').hidden = !savedGame();
    gameAudio.stop();
  } finally {
    starting = false; $('#start').removeAttribute('disabled'); $('#continue').removeAttribute('disabled');
  }
}

async function openMap() {
  if (!world || !controller || busy || modal || activeAssembly() || caseClock.blocked() || transitioning) return;
  busy = true;
  await settleMovement();
  setModal('map');
  renderMap(); status('#map-status', '');
  renderMapResidents(); $('#close-map').focus();
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

function renderMapResidents() {
  const panel = $('#map-residents'); panel.replaceChildren();
  for (const npc of world?.npc_presences ?? []) {
    const row = document.createElement('div'); const img = document.createElement('img');
    img.src = portraitPath(npc.npc_id); img.alt = ''; row.append(img);
    addText(row, 'span', `${npc.name} · ${locationName(npc.location_id)}${npc.destination_id ? ` → ${locationName(npc.destination_id)}` : npc.activity === 'talking' ? ' · Conversando' : ''}`);
    panel.append(row);
  }
}

function activeAssembly() {return caseState?.assembly_session?.phase === 'debate' && !caseState.assembly;}

function assemblySelected(name: string) {
  return [...document.querySelectorAll<HTMLInputElement>(`#assembly-overlay input[name="${name}"]:checked`)].map(input => input.value);
}

function saveAssemblyDraft() {
  if (!world) return;
  try {localStorage.setItem(`memorias-licantropicas:assembly:${world.game_id}`, JSON.stringify({
    speech: $<HTMLTextAreaElement>('#assembly-opening').value,
    reply: $<HTMLTextAreaElement>('#assembly-reply').value,
    suspect: assemblySelected('assembly-suspect')[0] ?? '',
    evidence: assemblySelected('assembly-evidence'), testimony: assemblySelected('assembly-testimony'),
  }));} catch { /* Draft remains on the page if browser storage is unavailable. */ }
}

function renderAssemblyChoices() {
  if (!caseState || !world) return;
  const sameGame = assemblyDraftGame === world.game_id;
  let draft: {speech?: string; reply?: string; suspect?: string; evidence?: string[]; testimony?: string[]} = {};
  if (sameGame) draft = {speech: $<HTMLTextAreaElement>('#assembly-opening').value,
    reply: $<HTMLTextAreaElement>('#assembly-reply').value, suspect: assemblySelected('assembly-suspect')[0],
    evidence: assemblySelected('assembly-evidence'), testimony: assemblySelected('assembly-testimony')};
  else {try {draft = JSON.parse(localStorage.getItem(`memorias-licantropicas:assembly:${world.game_id}`) ?? '{}') ?? {};} catch { /* empty draft */ }}
  assemblyDraftGame = world.game_id;
  const suspects = $('#assembly-suspects'); suspects.replaceChildren();
  for (const member of cast.filter(person => person.alive && person.character.id !== caseState?.detained_npc_id
      && !caseState?.expelled_npc_ids?.includes(person.character.id))) {
    const label = document.createElement('label'); label.className = 'suspect-card';
    const radio = document.createElement('input'); radio.type = 'radio'; radio.name = 'assembly-suspect'; radio.value = member.character.id;
    radio.checked = radio.value === draft.suspect;
    const image = document.createElement('img'); image.src = portraitPath(member.character.id); image.alt = ''; image.width = 72; image.height = 80;
    label.append(radio, image); addText(label, 'strong', member.character.name); suspects.append(label);
  }
  const evidence = $('#assembly-evidence'), testimony = $('#assembly-testimonies'); evidence.replaceChildren(); testimony.replaceChildren();
  const choice = (parent: HTMLElement, name: string, id: string, text: string, checked: boolean, art?: CaseEvidence) => {
    const label = document.createElement('label'); label.className = 'proof-choice';
    const input = document.createElement('input'); input.type = 'checkbox'; input.name = name; input.value = id; input.checked = checked;
    label.append(input); if (art) label.append(itemArt(art.item_id, art.kind)); addText(label, 'span', text); parent.append(label);
  };
  for (const {item, copies} of stackEvidence(caseState.inventory)) choice(evidence, 'assembly-evidence', item.id,
    `${item.name}${copies.length > 1 ? ` ×${copies.length}` : ''}`, Array.isArray(draft.evidence) && draft.evidence.includes(item.id), item);
  for (const item of stackTestimonies(caseState.testimonies, caseState.inventory)) choice(testimony, 'assembly-testimony', item.id,
    `${item.witness_name}: ${item.text}`, Array.isArray(draft.testimony) && draft.testimony.includes(item.id));
  if (!evidence.childElementCount) addText(evidence, 'p', 'Você pode argumentar mesmo sem objetos recolhidos.', 'empty-case');
  if (!testimony.childElementCount) addText(testimony, 'p', 'Nenhum depoimento registrado.', 'empty-case');
  $<HTMLTextAreaElement>('#assembly-opening').value = typeof draft.speech === 'string' ? draft.speech.slice(0,800) : '';
  $<HTMLTextAreaElement>('#assembly-reply').value = typeof draft.reply === 'string' ? draft.reply.slice(0,500) : '';
  updateAssemblyControls();
}

function renderAssemblyPanel() {
  if (!caseState) return;
  const session = caseState.assembly_session;
  $('#assembly-preparation').hidden = Boolean(session || caseState.assembly);
  $('#assembly-debate').hidden = !session;
  $('#assembly-reply-form').hidden = !activeAssembly();
  if (session) {
    if (assemblyDraftGame !== world?.game_id) {
      renderAssemblyChoices();
      if (!$<HTMLTextAreaElement>('#assembly-reply').value && session.reply) $<HTMLTextAreaElement>('#assembly-reply').value = session.reply;
    }
    $('#assembly-subject').textContent = `Em discussão: ${npcName(session.suspect_id)}`;
    const transcript = caseState.assembly?.messages ?? session.messages;
    const signature = JSON.stringify([session.id, session.phase, transcript]);
    if (signature !== assemblyRenderedRevision) {
      assemblyRenderedRevision = signature;
      const chat = $('#assembly-chat'); chat.replaceChildren();
      for (const message of transcript) {
        const row = document.createElement('article'); row.className = `assembly-message${message.speaker_id === 'player' ? ' is-floriano' : ''}`;
        const portrait = message.speaker_id === 'player' ? document.createElement('span') : document.createElement('img');
        if (portrait instanceof HTMLImageElement) {portrait.src = portraitPath(message.speaker_id); portrait.alt = '';}
        else {portrait.className = 'assembly-player-mark'; portrait.textContent = 'F'; portrait.setAttribute('aria-hidden', 'true');}
        const body = document.createElement('div'); addText(body, 'strong', npcName(message.speaker_id)); addText(body, 'p', message.text);
        row.append(portrait, body); chat.append(row);
      }
      chat.scrollTop = 0;
    }
  }
  const result = $('#assembly-result'); result.replaceChildren();
  const record = caseState.assembly;
  if (record) {
    const expelledPlayer = record.outcome === 'player_expelled';
    const target = expelledPlayer ? 'Floriano' : npcName(record.suspect_id);
    addText(result, 'h3', record.expelled ? `${target} foi expulso da cidade.` : 'A proposta não alcançou maioria.');
    addText(result, 'p', expelledPlayer ? 'Os moradores retiraram sua confiança no detetive. Você perdeu a investigação.'
      : record.outcome === 'werewolf' ? 'A assembleia expulsou o lobisomem. A cidade venceu.'
      : record.outcome === 'innocent' ? 'A pessoa expulsa era inocente. O ressentimento entre os moradores aumentou.'
      : `Eram necessários ${record.required_votes} votos para expulsar uma pessoa.`);
    for (const vote of record.votes) {
      const votedTarget = vote.target_id === undefined ? vote.expel ? record.suspect_id : null : vote.target_id;
      addText(result, 'p', `${npcName(vote.voter_id)}: ${votedTarget ? `expulsar ${npcName(votedTarget)}` : 'abstenção'}. ${vote.reason}`);
    }
  }
  updateAssemblyControls(); renderAssemblyClock();
}

function updateAssemblyControls() {
  $('#assembly-opening-count').textContent = `${$<HTMLTextAreaElement>('#assembly-opening').value.length} / 800`;
  $('#assembly-reply-count').textContent = `${$<HTMLTextAreaElement>('#assembly-reply').value.length} / 500`;
  $('#start-assembly').toggleAttribute('disabled', busy || Boolean(caseState?.assembly_session || caseState?.assembly)
    || !assemblySelected('assembly-suspect').length || !$<HTMLTextAreaElement>('#assembly-opening').value.trim());
  $('#finish-assembly').toggleAttribute('disabled', busy || assemblyResolving || !activeAssembly());
  $('#close-assembly').toggleAttribute('disabled', busy || assemblyResolving);
}

function renderAssemblyClock() {
  const session = caseState?.assembly_session;
  if (!session) return;
  const seconds = Math.max(0, Math.ceil((Date.parse(session.deadline) - (Date.now() - assemblyClockOffset)) / 1000));
  $('#assembly-countdown').textContent = activeAssembly() ? seconds ? `${formatClock(seconds)} para votar` : 'Concluindo a votação…' : 'Votação encerrada';
  if (activeAssembly() && !seconds && modal === 'assembly' && !busy && !assemblyResolving && assemblyTimeoutAttempt !== session.id) {
    assemblyTimeoutAttempt = session.id;
    void finishAssembly();
  }
}

async function openAssemblyPanel() {
  if (!world || busy || modal || (caseClock.blocked() && !activeAssembly())) return;
  await settleMovement();
  renderAssemblyChoices(); renderAssemblyPanel(); status('#assembly-status', '');
  setModal('assembly'); $('#close-assembly').focus();
}

async function startAssembly() {
  if (!world || busy || caseState?.assembly || caseState?.assembly_session || caseClock.blocked()) return;
  const suspect = assemblySelected('assembly-suspect')[0];
  const speech = $<HTMLTextAreaElement>('#assembly-opening').value.trim();
  if (!suspect || !speech || !$<HTMLTextAreaElement>('#assembly-opening').reportValidity()) return;
  saveAssemblyDraft(); busy = true; updateAssemblyControls(); status('#assembly-status', 'Os moradores se reúnem para ouvir seu caso…');
  try {
    await applyCase(await api.openAssembly(world.game_id, suspect, assemblySelected('assembly-evidence'), assemblySelected('assembly-testimony'), speech));
    renderAssemblyPanel(); if (caseState?.status === 'active') setModal('assembly'); status('#assembly-status', 'Ouça a cidade e faça sua réplica. Você pode concluir antes do prazo.');
    if (modal === 'assembly') $('#assembly-reply').focus();
  } catch (error) {status('#assembly-status', explain(error), true);}
  finally {busy = false; updateAssemblyControls();}
}

async function finishAssembly() {
  if (!world || busy || assemblyResolving || !activeAssembly()) return;
  const gameID = world.game_id;
  const reply = $<HTMLTextAreaElement>('#assembly-reply').value.trim();
  saveAssemblyDraft(); assemblyResolving = true; busy = true; updateAssemblyControls(); status('#assembly-status', 'Os moradores votam…');
  try {
    await applyCase(await api.resolveAssembly(gameID, reply));
    renderAssemblyPanel(); status('#assembly-status', 'Votação registrada.');
  } catch (error) {
    status('#assembly-status', explain(error), true);
    try {await applyCase(await api.investigation(gameID));} catch { /* Keep the draft and error while offline. */ }
  } finally {assemblyResolving = false; busy = false; updateAssemblyControls();}
}

async function openExit(side: ExitSide) {
  if (!world || !controller || busy || modal || activeAssembly() || caseClock.blocked() || transitioning) return;
  busy = true;
  await settleMovement();
  exitSide = side;
  setModal('exit');
  $('#exit-description').textContent = `Na saída à ${side === 'left' ? 'esquerda' : 'direita'} de ${world.location.name}, estes caminhos levam a outros encontros. Use as setas para escolher e Enter para seguir.`;
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
  if (!world || !controller || busy || activeAssembly() || caseClock.blocked() || transitioning) return;
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
  } finally {
    busy = false; renderMap(); renderExits(); lastNearest = '';
    if (modal === 'exit') {
      const buttons = [...document.querySelectorAll<HTMLButtonElement>('#exit-destinations button')];
      (buttons.find(button => button.dataset.destination === target) ?? buttons[0])?.focus();
    }
  }
}

async function approach() {
  if (!world || !controller || busy || modal || activeAssembly() || caseClock.blocked() || transitioning) return;
  const npc = closestNPC(world, controller.x);
  if (!npc) {toast('Aproxime-se de um morador para conversar.'); return;}
  busy = true;
  await settleMovement();
  busy = true; dialogueUnavailable = false; dialogueNPC = npc; conversation = null; conversationMessages = []; historyReady = false;
  $<HTMLTextAreaElement>('#message-input').value = ''; renderPresentation(); status('#presentation-status', '');
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
  const item = document.createElement('article'); item.className = `message ${message.speaker}${message.useful ? ' useful-report' : ''}`;
  const label = document.createElement('p'); label.className = 'message-author';
  label.textContent = message.speaker === 'player' ? 'FLORIANO' : dialogueNPC?.name.toLocaleUpperCase('pt-BR') ?? 'DEPOIMENTO';
  const content = document.createElement('p'); content.className = 'message-content'; content.textContent = message.content;
  item.append(label, content);
  if (message.useful) addText(item,'small','✦ Relato útil · confira esta versão','useful-report-label');
  $('#messages').append(item);
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
  $('#send-message').toggleAttribute('disabled', sending || dialogueUnavailable || !conversation || !historyReady || caseClock.blocked());
  $('#message-input').toggleAttribute('disabled', sending || dialogueUnavailable || !conversation || !historyReady || caseClock.blocked());
  $('#close-dialogue').toggleAttribute('disabled', sending);
  $('#present-button').toggleAttribute('disabled', sending || dialogueUnavailable || caseClock.blocked());
}

async function sendMessage(event: Event) {
  event.preventDefault();
  if (!conversation || !world || !historyReady || dialogueUnavailable || busy || caseClock.blocked()) return;
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
    if (isCurrent()) {try {await applyCase(await api.investigation(gameID));} catch { /* The case poller will retry the committed dialogue consequences. */ }}
    if (!isCurrent()) return;
    if (result.clearDraft) input.value = '';
    if (result.outcome === 'uncertain') historyReady = false;
    if (result.blocked) dialogueUnavailable = true;
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
function npcName(id: string) {if (id === 'player') return 'Floriano'; return cast.find(member => member.character.id === id)?.character.name ?? id;}
function portraitPath(id: string) {return manifest?.characters.find(asset => asset.id === id)?.portraitPath ?? `/assets/portraits/${id}.png`;}

function prepareJournalPortrait(victimID: string | null | undefined) {
  const image = $<HTMLImageElement>('#journal-victim-image');
  if (!victimID) {image.removeAttribute('src'); return;}
  const path = portraitPath(victimID);
  if (image.getAttribute('src') === path) return;
  image.decoding = 'async';
  image.fetchPriority = 'high';
  image.src = path;
  // Fetch and decode as soon as the public edition is known, including while
  // the scene or night animation is loading. Failed art must not block reading.
  void image.decode().catch(() => {});
}
function periodLabel(day: number, period: 'night' | 'day') {return `${period === 'night' ? 'noite' : 'dia'} ${day}`;}
function itemKind(evidence: CaseEvidence) {return {unique: 'Exclusivo', singular: 'Singular', common: 'Comum'}[evidence.kind];}
function stackEvidence(inventory: CaseEvidence[]) {
  const stacks = new Map<string, {item: CaseEvidence; copies: CaseEvidence[]}>();
  for (const evidence of inventory) {
    const stack = stacks.get(evidence.item_id);
    if (stack) stack.copies.push(evidence);
    else stacks.set(evidence.item_id, {item: evidence, copies: [evidence]});
  }
  return [...stacks.values()];
}
function stackTestimonies(testimonies: CaseTestimony[], inventory: CaseEvidence[]) {
  const itemByEvidenceId = new Map(inventory.map(evidence => [evidence.id, evidence.item_id]));
  const seen = new Set<string>();
  return testimonies.filter(testimony => {
    const itemId = itemByEvidenceId.get(testimony.evidence_id) ?? testimony.evidence_id;
    const key = `${testimony.witness_id}:${itemId}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
function itemArt(itemId: string, kind: CaseEvidence['kind']) {
  const wrapper = document.createElement('span'); wrapper.className = `item-art item-art-${kind}`; wrapper.setAttribute('aria-hidden', 'true');
  if (itemId !== 'botao' && !PERSONAL_ITEM_ICONS.has(itemId)) {
    const image = document.createElement('img'); image.src = `/assets/items/detail/${itemId}.png`;
    image.alt = ''; image.width = 64; image.height = 64; image.decoding = 'async'; wrapper.append(image);
  } else {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); svg.setAttribute('viewBox', '0 0 64 64');
    const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    use.setAttribute('href', `/assets/items/item-icons.svg?v=3#${itemId}`); svg.append(use); wrapper.append(svg);
  }
  return wrapper;
}

async function applyCase(next: CasePublic, initial = false) {
  if (!world || (!initial && $('#investigation').hidden) || next.game_id !== world.game_id || (caseState && next.revision < caseState.revision)) return;
  const previous = caseState;
  const nightWitnesses = world.visible_npcs.slice();
  const nightLocation = world.location.id;
  if (previous && previous.game_id === next.game_id) {
    const oldAchievements = new Set((previous.achievements ?? []).map(item => item.id));
    const fresh = (next.achievements ?? []).filter(item => !oldAchievements.has(item.id));
    if (fresh.length) toast(`Nova descoberta: ${fresh.map(item => item.title).join(', ')}`);
  }
  const changed = !previous || previous.day !== next.day || previous.phase !== next.phase || previous.status !== next.status
    || previous.detained_npc_id !== next.detained_npc_id || pendingWorldSync;
  caseState = next; assemblyClockOffset = Date.now() - Date.parse(next.server_time); caseClock.accept(next); renderClock();
  gameAudio.setNight(next.phase === 'night');
  if (!previous || previous.revision !== next.revision) {
    scene?.setInvestigation(next); renderCase();
  }
  if (!changed) return;
  transitioning = true; pendingWorldSync = true; scene?.setInputEnabled(false);
  try {
    // The public result already confirms the transformation; scenery refresh must not delay it.
    if(next.status==='won' && next.ending?.method==='detention') {
      pendingWorldSync=false;
      void controller?.suspend();
      await showCustody(next.ending.werewolf_id,'transformed');
      if(world?.game_id===next.game_id && caseState?.revision===next.revision)showPhase();
      return;
    }
    if (!initial) {
      await controller?.suspend();
      const [snapshot, publicGame] = await Promise.all([api.world(next.game_id), api.game(next.game_id)]);
      if (caseState?.revision !== next.revision || world?.game_id !== next.game_id) return;
      controller?.accept(snapshot); cast = publicGame.characters; renderCase();
    }
    pendingWorldSync = false;
    const victim = !initial && previous ? newNightVictim(previous.journal, next.journal) : null;
    if (victim) {
      setModal(null); scene?.setInputEnabled(false);
      await playNightAttack(victim, manifest, victim.location_id === nightLocation ? nightWitnesses : []);
      if (caseState?.revision !== next.revision || world?.game_id !== next.game_id) return;
    }
    if (next.phase === 'night' && next.detained_npc_id) {
      void showCustody(next.detained_npc_id,'night',previous?.detained_npc_id!==next.detained_npc_id);
    } else if (next.phase !== 'day' || next.status !== 'active') showPhase();
    else if (initial && next.detained_npc_id) {void showCustody(next.detained_npc_id,'waiting');}
    else if (next.assembly_session?.phase === 'debate') {renderAssemblyPanel(); setModal('assembly');}
    else if (initial || previous?.day !== next.day) {
      conversation = null; dialogueNPC = null; exitBoundary = new ExitBoundary();
      if (previous?.detained_npc_id && next.journal.at(-1)?.detention_outcome === 'released') await showCustody(previous.detained_npc_id,'released');
      renderJournal(); setModal('journal'); $('#read-journal').focus();
    } else if (next.detained_npc_id) {void showCustody(next.detained_npc_id,'waiting',previous?.detained_npc_id!==next.detained_npc_id);}
    else if (modal === 'phase' || modal === 'custody') setModal(null);
  } catch {toast('A manhã chegou. Estamos atualizando os caminhos da cidade.');}
  finally {transitioning = pendingWorldSync; scene?.setInputEnabled(modal === null && !caseClock.blocked() && !activeAssembly() && !transitioning);}
}

function renderClock() {
  if (!caseState || $('#investigation').hidden) return;
  $('#case-day').textContent = `DIA ${caseState.day}`;
  const gameTime = caseState.phase === 'night' ? '18:00' : formatGameTime(caseClock.seconds());
  $('#case-clock').textContent = caseState.phase === 'finished' ? 'FIM' : gameTime;
  $('#case-clock').setAttribute('aria-label', caseState.phase === 'finished' ? 'Caso encerrado' : `Horário na cidade: ${gameTime}${activeAssembly() ? ', pausado durante a assembleia' : ''}`);
  $('#case-phase').textContent = activeAssembly() ? 'Assembleia em curso · o dia aguarda a votação' : caseState.phase === 'night' ? 'A noite não é jogável'
    : caseState.phase === 'finished' ? 'Este caso chegou ao fim'
    : caseClock.seconds() ? 'Investigue até as 18h' : 'Aguardando os acontecimentos da noite…';
  $('#open-delegate').toggleAttribute('disabled', caseClock.blocked() || Boolean(activeAssembly()));
  $('#open-assembly').toggleAttribute('disabled', caseState.status !== 'active' || (caseClock.blocked() && !activeAssembly()));
  $('#open-assembly').textContent = activeAssembly() ? 'Retomar assembleia' : caseState.assembly ? 'Resultado da assembleia' : 'Assembleia da cidade';
  $('#skip-day').toggleAttribute('disabled', busy || transitioning || Boolean(modal) || caseClock.blocked() || Boolean(activeAssembly()));
  renderAssemblyClock();
  $('#open-map').toggleAttribute('disabled', caseClock.blocked() || Boolean(activeAssembly()));
  if (!transitioning && caseState.phase === 'day' && caseState.status === 'active' && !caseClock.seconds() && modal !== 'phase' && modal !== 'custody' && !activeAssembly()) {
    scene?.setInputEnabled(false); showPhase();
  }
  if (modal === 'custody') $('#custody-clock').textContent = caseState.status === 'won' ? 'Transformação confirmada pelo delegado' : caseState.phase === 'night' ? `Amanhecer em ${formatClock(caseClock.seconds())}` : `${gameTime} · Anoitecer às 18h`;
  if (modal === 'phase') $('#phase-countdown').textContent = caseState.phase === 'finished' ? ''
    : caseState.phase === 'night' ? `A manhã se aproxima · ${formatClock(caseClock.seconds())}` : 'Aguardando confirmação da cidade…';
}

function showCustody(npcID:string,mode:CustodyMode,admit=false):Promise<void> {
  const asset=manifest.characters.find(c=>c.id===npcID);
  if(!asset)return Promise.resolve();
  const name=npcName(npcID);
  const words=personWords(cast.find(member=>member.character.id===npcID)?.character);
  $('#custody-title').textContent=mode==='transformed' ? 'A verdade por trás das grades' : mode==='released' ? 'A porta se abre ao amanhecer' : `${name} está sob custódia`;
  $('#custody-caption').textContent=mode==='transformed' ? `${name} se transformou. Floriano desvendou o caso.` : mode==='released' ? `${name} não se transformou e será ${words.release}. A investigação continua.` : 'A acusação ainda não confirma a culpa. Floriano aguarda os acontecimentos da noite.';
  $('#custody-canvas').setAttribute('aria-label',`Delegacia com a mesa do delegado à esquerda, ${name} na cela central e bancos de espera à direita`);
  $('#leave-custody').hidden=mode!=='waiting';setModal('custody');
  if(!custodyScene || custodyNpc!==npcID){
    custodyGame?.destroy(true);custodyNpc=npcID;
    custodyScene=new CustodyScene(asset,stage=>{
      if(custodyNpc!==npcID || modal!=='custody' || caseState?.detained_npc_id!==npcID)return;
      $('#custody-caption').textContent=stage==='entering' ? `${name} caminha para dentro da cela.` : stage==='closing' ? 'A grade se fecha. A noite trará a resposta.' : 'A acusação ainda não confirma a culpa. Floriano aguarda os acontecimentos da noite.';
    });
    custodyGame=makeCustodyGame($('#custody-canvas'),custodyScene);
  }
  return new Promise(resolve=>{custodyScene!.setMode(mode,resolve,admit);if(mode==='waiting'||mode==='night')resolve();});
}

function showPhase() {
  if (!caseState) return;
  const ending = caseState.ending;
  const victorious = ending?.result === 'won';
  if(victorious && victoryEditionID!==caseState.game_id){victoryEditionID=caseState.game_id;gameAudio.effect('victory');}
  const expelled = caseState.assembly?.outcome === 'player_expelled';
  $('#phase-overlay').classList.toggle('is-night-waiting', caseState.phase === 'night' && !ending);
  $('#victory-paper').hidden = !ending;
  $('#phase-overlay .phase-modal').classList.toggle('is-victory',!!ending);
  $('#victory-paper .press-picture').hidden = !victorious;
  defeatPhoto.hidden=!ending || victorious;
  if(ending && !victorious && defeatEditionID!==caseState.game_id) {
    defeatEditionID=caseState.game_id;defeatPhotoAbort?.abort();defeatPhotoAbort=new AbortController();
    delete defeatPhoto.dataset.loaded;
    void renderDefeatPhoto(defeatPhoto,caseState.journal.at(-1)?.location_id ?? world!.location.id,defeatPhotoAbort.signal);
    gameAudio.effect('howl');
  }
  $('#victory-paper .newspaper-edition span').textContent = expelled ? 'FLORIANO EXPULSO DA CIDADE' : victorious ? 'A VITÓRIA DE FLORIANO' : 'A BESTA-FERA VENCEU';
  $('#victory-paper .victory-ending').textContent = expelled ? 'A cidade afastou o detetive. A investigação está encerrada.' : victorious ? 'O caso está encerrado. A cidade volta a respirar.' : 'Floriano não chegou a tempo. A cidade está de luto.';
  if(ending) {
    const edition=caseState.journal.at(-1);
    $('#victory-day').textContent=`DIA ${caseState.day}`;
    $('#victory-headline').textContent=victorious ? (edition?.illustration === 'victory' ? edition.headline : 'Floriano vence: a cidade está livre do lobisomem') : edition?.headline ?? (expelled ? 'A cidade expulsa Floriano' : 'Floriano não chegou a tempo: a besta-fera venceu');
    $('#victory-body').textContent=edition?.body ?? ending?.message ?? '';
  }
  $('#phase-eyebrow').textContent = ending ? ending.result === 'won' ? 'A CIDADE RESPIRA ALIVIADA' : 'A CIDADE SILENCIOU' : 'A CIDADE RECOLHE-SE';
  $('#phase-title').textContent = ending ? ending.result === 'won' ? 'O lobisomem foi descoberto.' : expelled ? 'Floriano foi expulso da cidade.' : 'A investigação chegou tarde demais.'
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
  const deathCount = edition?.suspicious_death_count ?? caseState?.crimes.length ?? 0;
  $('#journal-death-toll').textContent = deathCount === 0 ? 'Nenhuma morte suspeita registrada até esta edição.'
    : `${deathCount} morte${deathCount === 1 ? '' : 's'} suspeita${deathCount === 1 ? '' : 's'} registrada${deathCount === 1 ? '' : 's'} até hoje`;
  const victim = $<HTMLElement>('#journal-victim');
  const victimImage = $<HTMLImageElement>('#journal-victim-image');
  victim.hidden = !edition?.victim_id;
  if (edition?.victim_id) {
    prepareJournalPortrait(edition.victim_id);
    victimImage.alt = `Retrato de ${edition.victim_name ?? 'a vítima'}, reproduzido em preto e branco`;
    $('#journal-victim-caption').textContent = edition.victim_name ? `A vítima · ${edition.victim_name}` : 'A vítima da noite';
  }
  $('#journal-location').textContent = edition?.location_id ? `Acontecimento registrado: ${locationName(edition.location_id)}.` : 'Nenhuma nova cena de crime foi anunciada.';
  const snapshot = $<HTMLElement>('#journal-snapshot');
  const variant = edition?.illustration ?? (edition?.victim_id ? 'crime_street' : 'quiet');
  snapshot.hidden = variant === 'quiet';
  const picture=$('#journal-image');
  picture.hidden = variant !== 'crime_street';
  let archival = snapshot.querySelector<HTMLElement>('.press-picture');
  if(!archival){archival=document.createElement('div');archival.className='press-picture';archival.setAttribute('role','img');snapshot.prepend(archival);}
  archival.hidden = variant === 'crime_street';
  archival.className=`press-picture press-${variant.replace('crime_','')}`;
  archival.setAttribute('aria-label',variant === 'victory' ? 'Ilustração da vitória de Floriano' : 'Ilustração de arquivo do local noticiado');
  $('#journal-snapshot-caption').textContent = edition?.location_id
    ? `Ilustração do Clarim · ${locationName(edition.location_id)}` : 'Ilustração de arquivo do Clarim do Rio';
}

function renderCase() {
  if (!caseState) return;
  $('#evidence-count').textContent = `${caseState.inventory.length} ${caseState.inventory.length === 1 ? 'pista' : 'pistas'}`;
  $('#case-hint-title').textContent = caseState.detained_npc_id
    ? 'Uma detenção. Uma noite de espera.' : `${caseState.inventory.length} vestígios, ${caseState.testimonies.length} depoimentos.`;
  $('#case-hint').textContent = caseState.detained_npc_id
    ? `${personWords(cast.find(member=>member.character.id===caseState?.detained_npc_id)?.character).accused} ficará na cela esta noite. O jornal trará os acontecimentos da manhã.`
    : 'Recolha vestígios nas cenas do crime. Mostre-os aos moradores e confronte versões antes de chamar o delegado.';
  renderJournal(); renderPresentation(); renderNotebook(); renderAssemblyPanel();
  if (modal !== 'delegate') renderAccusation();
}

function deadSuspectMark() {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 64 64'); svg.setAttribute('aria-hidden', 'true');
  svg.classList.add('notebook-death-mark');
  for (const d of ['M9 10 15 9 19 16 26 21 30 27 37 31 42 38 49 43 56 52 52 57 44 50 38 45 31 40 26 33 19 29 14 22 10 18Z', 'M55 10 49 9 45 16 38 21 34 27 27 31 22 38 15 43 8 52 12 57 20 50 26 45 33 40 38 33 45 29 50 22 54 18Z']) {
    const slash = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    slash.setAttribute('d', d); slash.setAttribute('fill', '#a91f1a');
    slash.setAttribute('stroke', '#611813'); slash.setAttribute('stroke-width', '1');
    svg.append(slash);
  }
  return svg;
}

function renderNotebookSuspects() {
  const list = $('#notebook-suspects'); list.replaceChildren();
  for (const member of cast) {
    const deceased = !member.alive;
    const card = document.createElement('article');
    card.className = `notebook-suspect${deceased ? ' is-deceased' : ''}`;
    card.setAttribute('aria-label', `${member.character.name} · ${deceased ? 'falecido' : 'sob suspeita'}`);
    const imageFrame = document.createElement('div'); imageFrame.className = 'notebook-suspect-portrait';
    const portrait = document.createElement('img'); portrait.src = portraitPath(member.character.id);
    portrait.alt = ''; portrait.loading = 'lazy'; portrait.decoding = 'async';
    imageFrame.append(portrait);
    if (deceased) imageFrame.append(deadSuspectMark());
    const name = document.createElement('strong'); name.textContent = member.character.name;
    const state = document.createElement('small'); state.textContent = deceased ? 'Falecido · riscado' : 'Sob suspeita';
    card.append(imageFrame, name, state); list.append(card);
  }
  if (!cast.length) addText(list, 'p', 'Os nomes dos moradores aparecerão quando o caso começar.', 'empty-case');
}

function selectNotebookTab(tab: 'clues' | 'reports', focus = false) {
  notebookTab = tab;
  const clues = tab === 'clues';
  const cluesButton = $<HTMLButtonElement>('#notebook-tab-clues');
  const reportsButton = $<HTMLButtonElement>('#notebook-tab-reports');
  cluesButton.setAttribute('aria-selected', String(clues)); cluesButton.tabIndex = clues ? 0 : -1;
  reportsButton.setAttribute('aria-selected', String(!clues)); reportsButton.tabIndex = clues ? -1 : 0;
  $('#notebook-clues').hidden = !clues; $('#notebook-reports').hidden = clues;
  if (focus) (clues ? cluesButton : reportsButton).focus();
}

function renderNotebook() {
  if (!caseState) return;
  renderNotebookSuspects();
  const inventory = $('#evidence-list'); inventory.replaceChildren();
  for (const {item: evidence, copies} of stackEvidence(caseState.inventory)) {
    const item = document.createElement('article'); item.className = 'evidence-card'; item.dataset.itemId = evidence.item_id;
    const art = itemArt(evidence.item_id, evidence.kind);
    if (copies.length > 1) addText(art, 'span', `×${copies.length}`, 'item-stack-count');
    item.append(art);
    const details = document.createElement('div'); details.className = 'evidence-details';
    addText(details, 'span', itemKind(evidence), 'evidence-kind'); addText(details, 'h4', evidence.name);
    if (PERSONAL_ITEM_ICONS.has(evidence.item_id)) addText(details, 'span', '✦ Rastro pessoal', 'evidence-kind personal-trace-stamp');
    addText(details, 'p', copies.length > 1 ? `Você recolheu ${copies.length} exemplares deste objeto.` : evidence.description);
    const inspected = copies.find(copy => copy.examined) ?? evidence;
    const inspect = document.createElement('button'); inspect.type = 'button'; inspect.className = 'button small evidence-inspect';
    inspect.textContent = inspected.examined ? 'Examinado' : 'Examinar'; inspect.disabled = Boolean(inspected.examined) || inspectingEvidence.has(inspected.id);
    inspect.setAttribute('aria-label', `${inspected.examined ? 'Objeto examinado' : 'Examinar'}: ${evidence.name}`);
    inspect.addEventListener('click', () => {inspect.disabled = true; inspect.textContent = 'Examinando…'; void inspectEvidence(inspected.id);}); details.append(inspect);
    if (inspected.examined && inspected.inspection_text) addText(details, 'p', inspected.inspection_text, 'inspection-result');
    if (copies.length > 1) {
      const sources = document.createElement('details'); sources.className = 'evidence-stack-sources';
      addText(sources, 'summary', `Procedência dos ${copies.length} vestígios`);
      const list = document.createElement('ul');
      for (const copy of copies) {
        const crime = caseState.crimes.find(record => record.id === copy.crime_id);
        const source = crime ? `Dia ${crime.day + 1} · ${locationName(crime.location_id)}` : 'Cena do crime';
        addText(list, 'li', `${source}: ${copy.description}`);
      }
      sources.append(list); details.append(sources);
    }
    item.append(details); inventory.append(item);
  }
  if (!caseState.inventory.length) addText(inventory, 'p', 'Nenhum vestígio recolhido. Procure as marcas de cena do crime no cenário.', 'empty-case');
  renderAchievements();
  const testimonyList = $('#testimony-list'); testimonyList.replaceChildren();
  for (const testimony of stackTestimonies(caseState.testimonies, caseState.inventory)) {
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
  for (const record of caseState.case_reports?.filter(report => report.kind === 'alibi') ?? []) {
    const card = document.createElement('article'); card.className = 'testimony-card useful-report table-report';
    card.dataset.reportId = record.id; card.dataset.confirmation = record.confirmation_status;
    addText(card, 'h4', `${record.npc_name} · ${periodLabel(record.day, record.period ?? 'night')}`);
    addText(card, 'small', caseReportStatus(record), 'table-report-status');
    addText(card, 'p', record.text);
    if (record.companion_ids.length) addText(card, 'small', `Companhia: ${record.companion_ids.map(npcName).join(', ')}`);
    alibis.append(card);
  }
  for (const record of (caseState.interrogations ?? []).filter(record => record.period === 'day')) {
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
  selectNotebookTab(notebookTab);
}

function renderAchievements() {
  const section = $('#achievements-section');
  const achievements = caseState?.achievements ?? [];
  const total = caseState?.achievement_total;
  section.hidden = typeof total !== 'number';
  if (typeof total !== 'number') return;
  $('#achievement-progress').textContent = `${achievements.length} / ${total} descobertas`;
  const list = $('#achievement-list'); list.replaceChildren();
  for (const achievement of achievements) {
    const seal = document.createElement('article'); seal.className = 'achievement-seal';
    seal.dataset.achievementId = achievement.id;
    addText(seal, 'span', '✦', 'achievement-mark'); addText(seal, 'h5', achievement.title); addText(seal, 'p', achievement.description);
    list.append(seal);
  }
  if (!achievements.length) addText(list, 'p', 'As descobertas desta partida aparecerão aqui.', 'empty-case');
}

async function inspectEvidence(evidenceID: string) {
  if (!caseState || inspectingEvidence.has(evidenceID)) return;
  inspectingEvidence.add(evidenceID);
  try {
    const next = await api.inspectEvidence(caseState.game_id, evidenceID);
    await applyCase(next);
  } catch (error) { toast(explain(error)); }
  finally {
    inspectingEvidence.delete(evidenceID);
    if (modal === 'notebook') renderNotebook();
  }
}

function renderReports() {
  const reports = $('#heard-report-list'); reports.replaceChildren();
  const canonical = caseState?.case_reports?.filter(report => report.kind !== 'alibi') ?? [];
  for (const report of canonical) {
    const card = document.createElement('article'); card.className = 'testimony-card useful-report table-report';
    card.dataset.reportId = report.id;
    addText(card, 'h4', `${report.npc_name} · ${caseReportKind(report)}`);
    addText(card, 'small', `${periodLabel(report.day, report.period ?? 'day')} · ${caseReportStatus(report)}`, 'table-report-status');
    if (report.subject_id) addText(card, 'small', `Sobre ${npcName(report.subject_id)}`);
    addText(card, 'p', report.text); reports.append(card);
  }
  const knownTexts = new Set(caseState?.case_reports?.map(report => report.text) ?? []);
  for (const report of heardReports) {
    if (knownTexts.has(report.content)) continue;
    const item = document.createElement('article'); item.className = `testimony-card${report.useful ? ' useful-report' : ''}`;
    if (report.useful) addText(item,'small','✦ Relato útil','useful-report-label');
    addText(item, 'h4', report.speaker_name);
    addText(item, 'small', report.source_name ? `Fonte atribuída: ${report.source_name}` : 'Versão ouvida em conversa');
    addText(item, 'p', report.content); reports.append(item);
  }
  if (!reports.childElementCount) addText(reports, 'p', 'As versões que os moradores contarem a Floriano ficarão registradas aqui.', 'empty-case');
}

function renderPresentation() {
  const panel = $('#evidence-presenter'); const select = $<HTMLSelectElement>('#present-evidence');
  let preview = $('#presented-evidence-art');
  if (!preview) {preview = document.createElement('span'); preview.id = 'presented-evidence-art'; preview.className = 'item-art-preview'; select.before(preview);}
  const selected = select.value; select.replaceChildren();
  for (const {item, copies} of stackEvidence(caseState?.inventory ?? [])) {
    const option = document.createElement('option'); option.value = item.id;
    option.textContent = `${item.name}${copies.length > 1 ? ` ×${copies.length}` : ''}`;
    select.append(option);
  }
  if ([...select.options].some(option => option.value === selected)) select.value = selected;
  const selectedEvidence = caseState?.inventory.find(item => item.id === select.value);
  preview.replaceChildren();
  if (selectedEvidence) preview.append(itemArt(selectedEvidence.item_id, selectedEvidence.kind));
  panel.hidden = !caseState?.inventory.length;
  $('#present-button').toggleAttribute('disabled', busy || dialogueUnavailable || caseClock.blocked());
}

function renderAccusation() {
  const previousEvidence = new Set([...document.querySelectorAll<HTMLInputElement>('#accusation-evidence input:checked')].map(input=>input.value));
  const previousTestimony = new Set([...document.querySelectorAll<HTMLInputElement>('#accusation-testimonies input:checked')].map(input=>input.value));
  const previousReports = new Set([...document.querySelectorAll<HTMLInputElement>('#accusation-testimonies input[name="report"]:checked')].map(input=>input.value));
  if (!caseState) return;
  const gallery = $('#accused-npc');
  const selected = gallery.querySelector<HTMLInputElement>('input:checked')?.value;
  gallery.replaceChildren();
  for (const member of cast) {
    const detained = member.character.id === caseState.detained_npc_id;
    const expelled = caseState.expelled_npc_ids?.includes(member.character.id);
    const label = document.createElement('label'); label.className = 'suspect-card';
    const input = document.createElement('input'); input.type = 'radio'; input.name = 'accused-npc';
    input.value = member.character.id; input.required = true; input.disabled = !member.alive || detained || Boolean(expelled);
    input.checked = !input.disabled && input.value === selected;
    const portrait = document.createElement('img'); portrait.src = portraitPath(member.character.id);
    portrait.alt = ''; portrait.width = 88; portrait.height = 96;
    const name = document.createElement('strong'); name.textContent = member.character.name;
    const words=personWords(member.character);
    const availability = document.createElement('small'); availability.textContent = !member.alive ? words.deceased : expelled ? words.expelled : detained ? 'Sob custódia' : 'Selecionar';
    label.append(input, portrait, name, availability); gallery.append(label);
  }
  const renderChoice = (container: HTMLElement, name: string, id: string, text: string, item?: CaseEvidence, witnessID?: string) => {
    const label = document.createElement('label'); label.className = 'proof-choice';
    const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.name = name; checkbox.value = id; checkbox.checked = previousTestimony.has(id);
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
  for (const {item, copies} of stackEvidence(caseState.inventory)) {
    const label = document.createElement('label'); label.className = 'proof-choice';
    const checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.name = 'evidence'; checkbox.value = item.id; checkbox.checked = previousEvidence.has(item.id);
    const caption = document.createElement('span'); caption.textContent = `${item.name} · ${itemKind(item)}${copies.length > 1 ? ` ×${copies.length}` : ''}`;
    label.append(checkbox, itemArt(item.item_id, item.kind), caption); evidence.append(label);
  }
  if (!caseState.inventory.length) addText(evidence, 'p', 'Você ainda não recolheu vestígios.', 'empty-case');
  const testimonies = $('#accusation-testimonies'); testimonies.replaceChildren();
  const inventorySnapshot = caseState.inventory;
  stackTestimonies(caseState.testimonies, inventorySnapshot).forEach(item => renderChoice(testimonies, 'testimony', item.id, `${item.witness_name}: ${item.text}`, inventorySnapshot.find(evidence => evidence.id === item.evidence_id), item.witness_id));
  for (const report of caseState.case_reports ?? []) {
    const label = document.createElement('label'); label.className = 'proof-choice useful-report';
    const input = document.createElement('input'); input.type = 'checkbox'; input.name = 'report'; input.value = report.id;
    input.disabled = !canSubmitCaseReport(report); input.checked = !input.disabled && previousReports.has(report.id);
    const text = document.createElement('span'); text.textContent = `${report.npc_name} · ${caseReportKind(report)}: ${report.text}`;
    addText(text, 'small', caseReportStatus(report), 'table-report-status');
    label.append(input, text); testimonies.append(label);
  }
  if (!caseState.testimonies.length) addText(testimonies, 'p', 'Nenhum depoimento sobre objetos registrado.', 'empty-case');
  const attempted = caseState.accusations.some(accusation => accusation.day === caseState?.day && accusation.accepted);
  updateAccusationSelection();
  if (attempted) status('#accusation-status', 'Já há uma prisão autorizada para esta noite.');
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
  const attempted = caseState?.accusations.some(accusation => accusation.day === caseState?.day && accusation.accepted);
  $('#submit-accusation').toggleAttribute('disabled', !selected || busy || caseClock.blocked() || Boolean(attempted));
  $('#review-accusation').toggleAttribute('disabled', !selected || busy || caseClock.blocked());
}

async function openCasePanel(panel: 'journal' | 'notebook' | 'delegate') {
  if (!world || busy || modal || caseClock.blocked()) return;
  if (panel === 'journal') {
    setModal(panel); $('#close-journal').focus();
    // The newspaper is already public: display it immediately while confirming
    // the stop. busy keeps movement/actions blocked even if it is closed early.
    await settleMovement();
    return;
  }
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

async function skipDay() {
  if (!world || !caseState || busy || transitioning || modal || caseClock.blocked() || activeAssembly()) return;
  const gameID = world.game_id, day = caseState.day;
  busy = true; scene?.setInputEnabled(false); renderClock();
  $('#skip-day').textContent = 'Avançando até a manhã…';
  try {
    await controller?.stop();
    await applyCase(await api.skipDay(gameID, day));
  } catch (error) {
    toast(explain(error));
    try {await applyCase(await api.investigation(gameID));} catch { /* O sincronizador tentará novamente. */ }
  } finally {
    busy = false; $('#skip-day').innerHTML = 'Pular o dia <span aria-hidden="true">↠</span>';
    renderClock(); scene?.setInputEnabled(modal === null && !caseClock.blocked() && !activeAssembly() && !transitioning);
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
    if (found) gameAudio.effect('clue');
    const stackCount = found ? result.inventory.filter(item => item.item_id === found.item_id).length : 0;
    toast(found ? `${found.name} recolhido · ${stackCount} ${stackCount === 1 ? 'unidade' : 'unidades'} no caderno.` : 'A busca nesta cena foi concluída.');
  } catch (error) {toast(explain(error));}
  finally {busy = false;}
}

async function presentEvidence() {
  if (!world || !dialogueNPC || dialogueUnavailable || busy || modal !== 'dialogue' || caseClock.blocked()) return;
  const evidenceID = $<HTMLSelectElement>('#present-evidence').value; if (!evidenceID) return;
  busy = true; setSending(true); status('#presentation-status', 'O morador examina o objeto…');
  try {
    const result = await api.present(world.game_id, evidenceID, dialogueNPC.npc_id);
    await applyCase(result);
    await refreshHistory();
    const presentedItemID = result.inventory.find(item => item.id === evidenceID)?.item_id;
    const testimony = result.testimonies.find(item => item.witness_id === dialogueNPC?.npc_id
      && result.inventory.find(evidence => evidence.id === item.evidence_id)?.item_id === presentedItemID);
    status('#presentation-status', 'Objeto apresentado. Continue a conversa a partir da resposta registrada.');
    if (!testimony) status('#presentation-status', 'Objeto apresentado. A resposta está na conversa.');
  } catch (error) {status('#presentation-status', explain(error), true);}
  finally {busy = false; setSending(false);}
}

function selectedDossierEvidence(testimonyIDs: string[]) {
  const inputs = [...document.querySelectorAll<HTMLInputElement>('#accusation-evidence input')];
  const selected = inputs.filter(input => input.checked).map(input => input.value);
  if (!caseState) return selected;
  const complete = dossierEvidence(caseState.inventory, caseState.testimonies, selected, testimonyIDs);
  for (const input of inputs) input.checked = complete.includes(input.value);
  return complete;
}

async function reviewSelectedAccusation() {
  if (!world || busy || caseClock.blocked() || modal !== 'delegate') return;
  const suspect = $('#accused-npc').querySelector<HTMLInputElement>('input:checked:not(:disabled)')?.value;
  if (!suspect) return;
  const testimony = [...document.querySelectorAll<HTMLInputElement>('#accusation-testimonies input[name="testimony"]:checked')].map(input=>input.value);
  const evidence = selectedDossierEvidence(testimony);
  const reports = [...document.querySelectorAll<HTMLInputElement>('#accusation-testimonies input[name="report"]:checked')].map(input=>input.value);
  busy=true; updateAccusationSelection(); status('#accusation-review','O delegado confere seu dossiê…');
  try {
    const review=await api.reviewAccusation(world.game_id,suspect,evidence,testimony,reports);
    $('#accusation-review').dataset.ready=String(review.ready);
    status('#accusation-review',review.reason);
  } catch(error) {status('#accusation-review',explain(error),true);}
  finally {busy=false;updateAccusationSelection();}
}

async function submitAccusation(event: Event) {
  event.preventDefault(); if (!world || busy || modal !== 'delegate' || caseClock.blocked()) return;
  const suspectID = $('#accused-npc').querySelector<HTMLInputElement>('input:checked:not(:disabled)')?.value;
  if (!suspectID) {status('#accusation-status', 'Selecione um suspeito antes de apresentar a acusação.', true); return;}
  const testimony = [...document.querySelectorAll<HTMLInputElement>('#accusation-testimonies input[name="testimony"]:checked')].map(input => input.value);
  const evidence = selectedDossierEvidence(testimony);
  const reports = [...document.querySelectorAll<HTMLInputElement>('#accusation-testimonies input[name="report"]:checked')].map(input => input.value);
  busy = true; $('#submit-accusation').setAttribute('disabled', ''); status('#accusation-status', 'O delegado examina os elementos apresentados…');
  try {
    const result = await api.accuse(world.game_id, suspectID, evidence, testimony, reports);
    await applyCase(result); renderAccusation();
    const decision = result.accusations.at(-1);
    status('#accusation-status', decision?.reason ?? 'Pedido registrado.');
  } catch (error) {status('#accusation-status', explain(error), true);}
  finally {busy = false; updateAccusationSelection();}
}

setInterval(renderClock, 250);
setInterval(async () => {
  if (modal !== 'dialogue' || !world || !conversation || !dialogueNPC || busy || renewingDialogue || dialogueUnavailable || caseClock.blocked()) return;
  const gameID = world.game_id, conversationID = conversation.id, npcID = dialogueNPC.npc_id;
  renewingDialogue = true;
  try {await api.approach(gameID, npcID);}
  catch (error) {
    if (world?.game_id === gameID && conversation?.id === conversationID && modal === 'dialogue'
        && error instanceof ApiError && (error.status === 403 || error.status === 404)) {
      dialogueUnavailable = true; setSending(false);
      status('#dialogue-status', `${explain(error)} Seu rascunho será preservado ao fechar a conversa.`, true);
    }
  } finally {renewingDialogue = false;}
}, 15000);
$('#skip-day').addEventListener('click', () => {void skipDay();});
$('#inspect-crime').addEventListener('click', () => {void searchCrime();});
$('#present-button').addEventListener('click', () => {void presentEvidence();});
$('#present-evidence').addEventListener('change', () => renderPresentation());
$('#accusation-form').addEventListener('submit', event => {void submitAccusation(event);});
$('#review-accusation').addEventListener('click',()=>{void reviewSelectedAccusation();});
for (const id of ['accused-npc','accusation-evidence','accusation-testimonies']) $( `#${id}`).addEventListener('change',event=>{
  const target = event.target as HTMLInputElement;
  if (caseState && id === 'accusation-evidence' && !target.checked) {
    const itemType = caseState.inventory.find(item => item.id === target.value)?.item_id;
    for (const input of document.querySelectorAll<HTMLInputElement>('#accusation-testimonies input[name="testimony"]:checked')) {
      const record = caseState.testimonies.find(item => item.id === input.value);
      if (record && caseState.inventory.find(item => item.id === record.evidence_id)?.item_id === itemType) input.checked = false;
    }
  }
  const testimonyIDs = [...document.querySelectorAll<HTMLInputElement>('#accusation-testimonies input[name="testimony"]:checked')].map(input => input.value);
  selectedDossierEvidence(testimonyIDs);
  updateAccusationSelection(); $('#accusation-review').removeAttribute('data-ready');
  status('#accusation-review','Seleção alterada. Confira o dossiê antes de pedir a prisão.');
});
$('#open-assembly').addEventListener('click', () => {void openAssemblyPanel();});
$('#close-assembly').addEventListener('click', () => {if (!busy) setModal(null);});
$('#assembly-opening-form').addEventListener('submit', event => {event.preventDefault(); void startAssembly();});
$('#assembly-reply-form').addEventListener('submit', event => {event.preventDefault(); void finishAssembly();});
for (const id of ['assembly-opening', 'assembly-reply']) $(`#${id}`).addEventListener('input', () => {updateAssemblyControls(); saveAssemblyDraft();});
$('#assembly-suspects').addEventListener('change', () => {updateAssemblyControls(); saveAssemblyDraft();});
for (const id of ['assembly-evidence', 'assembly-testimonies']) $(`#${id}`).addEventListener('change', saveAssemblyDraft);
for (const panel of ['journal', 'notebook', 'delegate'] as const) {
  $(`#open-${panel}`).addEventListener('click', () => {void openCasePanel(panel);});
  $(`#close-${panel}`).addEventListener('click', () => {if (panel === 'journal' || !busy) setModal(null);});
}
$('#notebook-tab-clues').addEventListener('click', () => selectNotebookTab('clues'));
$('#notebook-tab-reports').addEventListener('click', () => selectNotebookTab('reports'));
$('.notebook-tabs').addEventListener('keydown', event => {
  if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
    event.preventDefault(); selectNotebookTab(notebookTab === 'clues' ? 'reports' : 'clues', true);
  }
});
$('#read-journal').addEventListener('click', () => {setModal(null);});
$('#leave-custody').addEventListener('click',()=>{if(caseState?.phase==='day' && caseState.status==='active')setModal(null);});
$('#ending-new-case').addEventListener('click', () => {setModal(null); void launch(false);});

$('#start').addEventListener('click', () => {void launch(false);});
$('#continue').hidden = !savedGame();
$('#continue').addEventListener('click', () => {void launch(true);});
$('#new-case').addEventListener('click', async () => {
  if (busy) return;
  gameAudio.stop();
  casePoller.stop(); await settleMovement(); setModal(null); $('#investigation').hidden = true; $('#introduction').hidden = false;
  $('#continue').hidden = !savedGame(); document.body.classList.remove('case-active');
});
$('#open-map').addEventListener('click', () => {void openMap();});
$('#close-map').addEventListener('click', () => {if (!busy) setModal(null);});
$('#close-exit').addEventListener('click', () => {if (!busy) setModal(null);});
$('#stay-here').addEventListener('click', () => {if (!busy) setModal(null);});
$('#exit-overlay').addEventListener('keydown', event => {
  if (event.altKey || event.ctrlKey || event.metaKey) return;
  const step = event.key === 'ArrowDown' || event.key === 'ArrowRight' ? 1
    : event.key === 'ArrowUp' || event.key === 'ArrowLeft' ? -1 : 0;
  if (step) {
    event.preventDefault();
    // A walking key held when the menu opens must not cycle the destinations.
    if (busy || event.repeat) return;
    const buttons = [...document.querySelectorAll<HTMLButtonElement>('#exit-destinations button:not(:disabled), #stay-here:not(:disabled)')];
    if (!buttons.length) return;
    const index = buttons.findIndex(button => button === document.activeElement);
    buttons[index < 0 ? 0 : (index + step + buttons.length) % buttons.length].focus();
  } else if (event.key === 'Enter' && (busy || event.repeat)) {
    event.preventDefault();
  }
  // Enter on the focused native button activates the same action as a click.
});
$('#approach').addEventListener('click', () => {void approach();});
for (const [id, direction] of [['walk-left', 'left'], ['walk-right', 'right']] as const) {
  const button = $(`#${id}`);
  button.addEventListener('pointerdown', event => {
    if (modal || busy || activeAssembly() || caseClock.blocked()) return;
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
  const target = event.target;
  const typing = target instanceof HTMLElement
    && (target.isContentEditable || target.matches('input, textarea, select'));
  if (!typing && !event.altKey && !event.ctrlKey && !event.metaKey && !event.repeat) {
    if (modal === 'notebook' && (event.key === '1' || event.key === '2')) {
      event.preventDefault(); selectNotebookTab(event.key === '1' ? 'clues' : 'reports', true); return;
    }
    if (event.key.toLowerCase() === 'c' && !busy && !caseClock.blocked()) {
      if (modal === 'notebook') {event.preventDefault(); setModal(null); return;}
      if (modal === null && caseState && !$('#investigation').hidden) {
        event.preventDefault(); void openCasePanel('notebook'); return;
      }
    }
  }
  if (event.key === 'Escape' && modal && modal !== 'phase' && !(modal === 'custody' && (caseClock.blocked() || transitioning)) && !busy) {event.preventDefault(); setModal(null);}
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
window.addEventListener('pagehide', () => {gameAudio.stop(); casePoller.stop(); controller?.dispose();});

const audioControls = document.createElement('div');
audioControls.className = 'audio-controls';
audioControls.innerHTML = '<button id="audio-mute" class="button secondary small" type="button" aria-label="Silenciar áudio">Som ligado</button><label for="audio-volume">Volume <input id="audio-volume" type="range" min="0" max="100" step="5" aria-label="Volume do jogo"/></label>';
document.querySelector('.masthead')!.append(audioControls);
const audioMute = document.querySelector<HTMLButtonElement>('#audio-mute')!;
const audioVolume = document.querySelector<HTMLInputElement>('#audio-volume')!;
function renderAudioControls() {
  audioMute.textContent = gameAudio.muted ? 'Som desligado' : 'Som ligado';
  audioMute.setAttribute('aria-pressed', String(gameAudio.muted));
  audioMute.setAttribute('aria-label', gameAudio.muted ? 'Ativar áudio' : 'Silenciar áudio');
  audioVolume.value = String(gameAudio.volume * 100);
}
audioMute.addEventListener('click', () => {gameAudio.unlock(); gameAudio.setMuted(!gameAudio.muted); renderAudioControls();});
audioVolume.addEventListener('input', () => {gameAudio.unlock(); gameAudio.setVolume(Number(audioVolume.value) / 100); renderAudioControls();});
renderAudioControls();
