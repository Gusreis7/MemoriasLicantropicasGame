export type Direction = 'left' | 'right' | 'idle';
export type LocationID = 'praca_verde' | 'cabana_capitu' | 'casa_verde' | 'cafe_largo' | 'cais_lanternas';

export interface Location {
  id: LocationID; name: string; width: number; height: number; ground_y: number; background: string;
}
export interface WorldSnapshot {
  game_id: string; world_version: string; revision: number; location: Location;
  player: {location_id: LocationID; x: number; facing: 'left' | 'right'; movement_seq: number};
  visible_npcs: Array<{npc_id: string; name: string; x: number; sprite_id: string; can_approach: boolean}>;
  travel_targets: LocationID[];
}
export interface Conversation {id: string; game_id: string; npc_id: string; created_at: string}
export interface Message {id: string; speaker: 'player' | 'npc'; content: string; created_at: string}
export interface CharacterAsset {
  id: string; type: 'atlas' | 'spritesheet' | 'image'; path: string; atlasPath?: string;
  frameWidth: number; frameHeight: number; frames: number; frameNames?: string[];
  idleFrames: Array<string | number>; walkFrames: Array<string | number>;
  displayWidth: number; displayHeight: number; origin: {x: number; y: number}; portraitPath?: string;
}
export interface CharacterManifest {version: string; characters: CharacterAsset[]}

export class ApiError extends Error {
  constructor(public status: number, message: string) {super(message); this.name = 'ApiError';}
}

export async function request<T>(path: string, body?: unknown, method?: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      method: method ?? (body === undefined ? 'GET' : 'POST'),
      credentials: 'same-origin',
      headers: body === undefined ? undefined : {'Content-Type': 'application/json'},
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, 'Não foi possível alcançar a cidade. Confira sua conexão e tente novamente.');
  }
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    const detail = typeof error?.detail === 'string' ? error.detail : 'Confira os dados e tente novamente.';
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

const base = (gameID: string) => `/api/v1/games/${encodeURIComponent(gameID)}`;
export const api = {
  createGame: () => request<{id: string}>('/api/v1/games', {}),
  world: (id: string) => request<WorldSnapshot>(`${base(id)}/world`),
  locations: () => request<Location[]>('/api/v1/world/locations'),
  manifest: () => request<CharacterManifest>('/assets/characters/manifest.json'),
  move: (world: WorldSnapshot, direction: Direction) => request<WorldSnapshot>(`${base(world.game_id)}/movement`, {
    direction, seq: world.player.movement_seq + 1, location_id: world.player.location_id, revision: world.revision,
  }),
  travel: (world: WorldSnapshot, target: LocationID) => request<WorldSnapshot>(`${base(world.game_id)}/travel`, {
    target_location_id: target, revision: world.revision,
  }),
  approach: (id: string, npcID: string) => request<Conversation>(`${base(id)}/approaches`, {npc_id: npcID}),
  history: (id: string, conversationID: string) => request<{conversation_id: string; messages: Message[]}>(
    `${base(id)}/conversations/${encodeURIComponent(conversationID)}/messages?limit=200`,
  ),
  send: (id: string, conversationID: string, content: string) => request<{conversation_id: string; message: Message}>(
    `${base(id)}/conversations/${encodeURIComponent(conversationID)}/messages`, {content},
  ),
};
