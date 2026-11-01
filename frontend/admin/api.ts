export interface Page<T> { items: T[]; total: number }
export interface GameSummary { id: string; created_at: string; status: string }
export interface CharacterState { character_id: string; name: string; role: string; alive: boolean; location_id?: string | null; x?: number | null }
export interface KnownDeath { victim_id: string; victim_name?: string; killer_id: string | null; killer_name?: string | null; attribution: string; source: string }
export interface GameState {
  game_id: string; created_at: string; content_version: string; status: string;
  werewolf_id: string; characters: CharacterState[]; player?: { location_id?: string; x?: number } | null;
  known_deaths: KnownDeath[]; world_version?: string | null;
}
export interface EventRecord { id: string; type: string; occurred_at: string; source: string; data: Record<string, unknown> }
export interface Conversation { id: string; game_id: string; participant_ids: string[]; created_at: string }
export interface Message { id: string; sender_id: string; content: string; created_at: string }
export interface GraphNode { id: string; name: string }
export interface GraphEdge { source: string; target: string; message_count: number; last_at?: string | null; conversation_id: string }
export interface Interactions { nodes: GraphNode[]; edges: GraphEdge[] }

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
  return parts.join(' · ') || 'Acontecimento efetivado no registro da partida.';
}
