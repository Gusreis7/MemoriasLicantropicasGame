export interface Page<T> { items: T[]; total: number }
export interface GameSummary { id: string; created_at: string; status: string }
export interface CharacterState { character_id: string; name: string; grammatical_gender?: 'masculine' | 'feminine'; role: string; alive: boolean; location_id?: string | null; x?: number | null }
export interface KnownDeath { victim_id: string; victim_name?: string; killer_id: string | null; killer_name?: string | null; attribution: string; source: string }
export interface GameState {
  game_id: string; created_at: string; content_version: string; status: string;
  werewolf_id: string; characters: CharacterState[]; player?: { location_id?: string; x?: number } | null;
  known_deaths: KnownDeath[]; world_version?: string | null;
  investigation?: {day: number; phase: string; status: string; phase_ends_at: string; detained_npc_id: string | null; [key: string]: unknown} | null;
}
export interface EventRecord { id: string; type: string; occurred_at: string; source: string; data: Record<string, unknown> }
export interface Conversation { id: string; game_id: string; participant_ids: string[]; created_at: string }
export interface Message { id: string; sender_id: string; content: string; created_at: string }
export interface GraphNode { id: string; name: string }
export interface GraphEdge { source: string; target: string; message_count: number; last_at?: string | null; conversation_id: string }
export interface Interactions { nodes: GraphNode[]; edges: GraphEdge[] }
export interface SocialKnowledge {
  id: string; owner_id: string; root_id: string; source_message_id: string; speaker_id: string;
  claimed_source_id: string | null; source_span: string; proposition: string; subject_ids: string[];
  parent_ids: string[]; kind: string; confidence: string; stance: string; day: number | null; created_at: string;
}
export interface SocialEncounter {
  id: string; day: number; slot: number; participant_ids: string[]; phase: string; location_id: string;
  reason: string | null; messages: Array<{id: string; sender_id: string; content: string; created_at: string; intent: string; claim_ids: string[]}>;
}
export interface SocialState {
  game_id: string; revision: number; knowledge: SocialKnowledge[]; encounters: SocialEncounter[];
  relationships: Array<{actor_id: string; target_id: string; affinity: number; trust: number; resentment: number; causes: string[]}>;
  days: Array<{day: number; slots: number[]; speech_calls: number; extraction_calls: number}>;
}

export interface UsageTotals {
  calls: number; completed_calls: number; failed_calls: number; cancelled_calls: number;
  known_input_tokens: number; known_output_tokens: number; calls_with_missing_tokens: number;
  unpriced_calls: number; known_estimated_cost_usd: string; cost_complete: boolean; duration_ms: number;
}
export interface UsageSummary {
  game_id: string; coverage: 'recorded_calls_only' | 'not_recorded';
  first_recorded_at: string | null; last_recorded_at: string | null; totals: UsageTotals;
  by_purpose: Array<UsageTotals & {key: string}>; by_model: Array<UsageTotals & {key: string}>;
  pricing_snapshots: Array<{model: string; input_usd_per_million: string | null; output_usd_per_million: string | null;
    currency: string; source: string; checked_at: string | null}>;
  currency: string; note: string;
}

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) { super(message); this.name = 'ApiError'; }
}

export function errorMessage(status: number): string {
  if (status === 401) return 'Sessão encerrada ou credenciais inválidas. Entre novamente.';
  if (status === 403) return 'Este acesso não foi autorizado pelo servidor.';
  if (status === 404) return 'O registro solicitado não foi encontrado.';
  if (status === 429) return 'Muitas tentativas de acesso. Aguarde alguns minutos e tente novamente.';
  if (status === 503) return 'O serviço está temporariamente indisponível. Tente atualizar em instantes.';
  return 'Não foi possível consultar o arquivo. Tente novamente.';
}

export async function request<T>(path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/admin/api/v1${path}`, {
      method: body === undefined ? 'GET' : 'POST',
      credentials: 'same-origin', cache: 'no-store',
      signal: AbortSignal.timeout(10000),
      ...(body === undefined ? {} : {headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}),
    });
  } catch { throw new ApiError(0, 'Não foi possível alcançar o servidor. Confira sua conexão.'); }
  if (!response.ok) throw new ApiError(response.status, errorMessage(response.status));
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const locationNames: Record<string, string> = {
  praca_verde: 'Praça Verde', cabana_capitu: 'Cabana da Capitu', casa_verde: 'Casa Verde',
  cafe_largo: 'Café do Largo', cais_lanternas: 'Cais das Lanternas',
};

export const characterNames: Record<string, string> = {
  player: 'Detetive Floriano', bentinho: 'Bentinho', capitu: 'Capitu', escobar: 'Escobar',
  rubiao: 'Rubião', virgilia: 'Virgília Neves', florenca: 'Florença', bacamarte: 'Dr. Bacamarte', bras_cubas: 'Brás Cubas',
};

export function nameOf(id: string): string { return characterNames[id] ?? id; }
export function deathAuthor(death: KnownDeath): string {
  return death.killer_id && death.attribution !== 'unknown' ? (death.killer_name || nameOf(death.killer_id)) : 'Autoria não registrada';
}

export function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Data não registrada' : new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'short', timeStyle: 'short',
  }).format(date);
}

export const eventLabels: Record<string, string> = {
  'game.created': 'Partida criada', 'world.initialized': 'Mundo preparado', 'player.travelled': 'O detetive viajou',
  'conversation.created': 'Conversa iniciada', 'conversation.exchange_committed': 'Diálogo registrado',
  'story.initial_death': 'Morte inicial conhecida', 'character.killed': 'Morte registrada',
  'night.started': 'Anoiteceu', 'night.resolved': 'Noite resolvida',
  'journal.published': 'Jornal publicado', 'evidence.collected': 'Vestígio recolhido',
  'evidence.presented': 'Vestígio apresentado', 'accusation.decided': 'Acusação avaliada',
  'game.won': 'Investigação vencida', 'game.lost': 'Investigação encerrada',
  'werewolf.confessed': 'Lobisomem confessou e entregou-se', 'werewolf.expelled': 'Lobisomem expulso após transformação',
  'social.encounter_started': 'Encontro entre moradores', 'social.message_committed': 'Fala entre moradores',
  'social.encounter_interrupted': 'Encontro interrompido', 'social.knowledge_extracted': 'Relato incorporado à memória',
};

export function eventDetails(event: EventRecord): string {
  const data = event.data ?? {};
  const parts: string[] = [];
  if (typeof data.victim_id === 'string') parts.push(`Vítima: ${nameOf(data.victim_id)}`);
  if (typeof data.killer_id === 'string' && data.attribution !== 'unknown') parts.push(`Autoria registrada: ${nameOf(data.killer_id)}`);
  else if ('victim_id' in data) parts.push('Autoria não registrada');
  if (typeof data.target_location_id === 'string') parts.push(`Destino: ${locationNames[data.target_location_id] ?? data.target_location_id}`);
  if (typeof data.location_id === 'string') parts.push(`Local: ${locationNames[data.location_id] ?? data.location_id}`);
  if (Array.isArray(data.participant_ids)) parts.push(data.participant_ids.filter((id): id is string => typeof id === 'string').map(nameOf).join(' ↔ '));
  if (typeof data.conversation_id === 'string') parts.push(`Encontro ${data.conversation_id.slice(0, 8)}`);
  if (typeof data.message_count === 'number') parts.push(`${data.message_count} mensagens`);
  if (data.method === 'confession') parts.push('Confissão registrada e custódia voluntária');
  return parts.join(' · ') || 'Acontecimento efetivado no registro da partida.';
}
