export type Direction = 'left' | 'right' | 'idle';
export type LocationID = 'praca_verde' | 'cabana_capitu' | 'casa_verde' | 'cafe_largo' | 'cais_lanternas';
export type ExitSide = 'left' | 'right';
export interface LocationExit {side: ExitSide; target_location_id: LocationID; arrival_side: ExitSide}

export interface Location {
  id: LocationID; name: string; width: number; height: number; ground_y: number; background: string; exits: LocationExit[];
}
export interface WorldSnapshot {
  game_id: string; world_version: string; revision: number; location: Location;
  player: {location_id: LocationID; x: number; facing: 'left' | 'right'; movement_seq: number};
  visible_npcs: Array<{npc_id: string; name: string; x: number; sprite_id: string; can_approach: boolean;
    activity?: 'idle' | 'talking' | 'travelling'; social_partner_id?: string | null; speech?: string | null}>;
  npc_presences?: Array<{npc_id: string; name: string; location_id: LocationID; activity: string; destination_id: LocationID | null}>;
  travel_targets: LocationID[];
}
export interface Conversation {id: string; game_id: string; npc_id: string; created_at: string}
export interface Message {useful?: boolean; id: string; speaker: 'player' | 'npc'; content: string; created_at: string}
export interface HeardReport {useful?: boolean; id: string; speaker_id: string; speaker_name: string; content: string; created_at: string; source_name: string | null}
export interface CharacterAsset {
  id: string; type: 'atlas' | 'spritesheet' | 'image'; path: string; atlasPath?: string;
  frameWidth: number; frameHeight: number; frames: number; frameNames?: string[];
  idleFrames: Array<string | number>; walkFrames: Array<string | number>;
  displayWidth: number; displayHeight: number; origin: {x: number; y: number}; portraitPath?: string;
}
export interface CharacterManifest {version: string; characters: CharacterAsset[]}
export type GrammaticalGender = 'masculine' | 'feminine';
export interface PublicCharacter {id: string; name: string; grammatical_gender?: GrammaticalGender}
export interface GamePublic {id: string; status: 'active' | 'won' | 'lost'; characters: Array<{character: PublicCharacter; alive: boolean}>}
export interface CaseCrime {id: string; day: number; victim_id: string; victim_name: string; location_id: LocationID; x: number; remaining_clues: number}
export interface CaseEvidence {id: string; crime_id: string; item_id: string; name: string; kind: 'unique' | 'singular' | 'common'; description: string; examined?: boolean; inspection_text?: string | null}
export interface CaseAchievement {id: string; title: string; description: string; unlocked_at: string; source_message_id?: string | null; source_npc_id?: string | null}
export interface CaseTestimony {id: string; day: number; evidence_id: string; witness_id: string; witness_name: string; recognition: 'recognizes' | 'denies' | 'unknown'; claimed_owner_id: string | null; text: string}
export interface AccusationReview {ready: boolean; route: 'examined_trace' | 'corroborated_personal_marks' | 'witness_reports' | null; missing: string[]; reason: string}
export interface CaseAccusation {id: string; day: number; suspect_id: string; suspect_name: string; evidence_ids: string[]; testimony_ids: string[]; accepted: boolean; reason: string}
export interface CaseInterrogation {
  id: string; npc_id: string; npc_name: string; day: number; period: 'night' | 'day';
  location_id: LocationID | null; companion_ids: string[]; activity: string; text: string;
  observations: Array<{npc_id: string; location_id: LocationID | null; companion_ids: string[]; activity: string; source: 'observed' | 'heard'}>;
}
export interface CaseConfrontation {id: string; npc_id: string; day: number; evidence_ids: string[]; testimony_ids: string[]; interrogation_ids: string[]; confessed: boolean; text: string}
export interface JournalEdition {illustration?: string; day: number; title: string; headline: string; body: string; victim_id: string | null; victim_name: string | null; suspicious_death_count?: number; location_id: LocationID | null; detention_outcome: 'none' | 'released' | 'transformed'}
export interface AssemblySession {
  id: string; suspect_id: string; phase: 'debate' | 'resolved'; deadline: string;
  opening_speech: string; reply?: string | null; evidence_ids: string[]; testimony_ids: string[];
  messages: Array<{speaker_id: string; text: string}>;
}
export interface CasePublic {
  game_id: string; revision: number; day: number; phase: 'day' | 'night' | 'finished'; status: 'active' | 'won' | 'lost';
  server_time: string; phase_ends_at: string; seconds_remaining: number;
  journal: JournalEdition[]; crimes: CaseCrime[]; inventory: CaseEvidence[]; testimonies: CaseTestimony[];
  achievements?: CaseAchievement[]; achievement_total?: number;
  accusations: CaseAccusation[]; detained_npc_id: string | null;
  assembly?: {suspect_id: string; nominated_id?: string | null; messages?: Array<{speaker_id: string; text: string}>; day: number; required_votes: number; expelled: boolean; outcome: 'werewolf' | 'innocent' | 'no_majority' | 'player_expelled'; votes: Array<{voter_id: string; target_id?: string | null; expel: boolean; reason: string}>} | null;
  assembly_session?: AssemblySession | null;
  expelled_npc_ids?: string[];
  interrogations?: CaseInterrogation[]; confrontations?: CaseConfrontation[];
  case_reports?: Array<{id: string; npc_id: string; npc_name: string; day: number; kind: string; text: string}>;
  ending: {result: 'won' | 'lost'; message: string; werewolf_id: string; method?: 'detention' | 'confession' | 'survival' | 'assembly' | 'player_expelled'} | null;
}

export class ApiError extends Error {
  constructor(public status: number, message: string, public code?: string) {super(message); this.name = 'ApiError';}
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
    throw new ApiError(response.status, detail, typeof error?.code === 'string' ? error.code : undefined);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

const base = (gameID: string) => `/api/v1/games/${encodeURIComponent(gameID)}`;
export const api = {
  createGame: () => request<{id: string}>('/api/v1/games', {}),
  game: (id: string) => request<GamePublic>(base(id)),
  investigation: (id: string) => request<CasePublic>(`${base(id)}/investigation`),
  skipDay: (id: string, day: number) => request<CasePublic>(`${base(id)}/investigation/skip-day`, {day}),
  reports: (id: string) => request<{reports: HeardReport[]}>(`${base(id)}/social/reports`),
  search: (id: string, crimeID: string) => request<CasePublic>(`${base(id)}/crime-scenes/${encodeURIComponent(crimeID)}/search`, {}),
  present: (id: string, evidenceID: string, npcID: string) => request<CasePublic>(`${base(id)}/evidence/${encodeURIComponent(evidenceID)}/present`, {npc_id: npcID}),
  inspectEvidence: (id: string, evidenceID: string) => request<CasePublic>(`${base(id)}/evidence/${encodeURIComponent(evidenceID)}/inspect`, {}),
  reviewAccusation: (id: string, suspectID: string, evidenceIDs: string[], testimonyIDs: string[], reportIDs: string[] = []) => request<AccusationReview>(`${base(id)}/accusations/review`, {
    suspect_id: suspectID, evidence_ids: evidenceIDs, testimony_ids: testimonyIDs, ...(reportIDs.length ? {report_ids: reportIDs} : {}),
  }),
  accuse: (id: string, suspectID: string, evidenceIDs: string[], testimonyIDs: string[], reportIDs: string[] = []) => request<CasePublic>(`${base(id)}/accusations`, {
    suspect_id: suspectID, evidence_ids: evidenceIDs, testimony_ids: testimonyIDs, ...(reportIDs.length ? {report_ids: reportIDs} : {}),
  }),
  // Kept for older clients; the game UI now asks and confronts in the dialogue.
  interrogate: (id: string, npcID: string, day: number, period: 'night' | 'day') => request<CasePublic>(`${base(id)}/interrogations`, {npc_id: npcID, day, period}),
  confront: (id: string, npcID: string, evidenceIDs: string[], testimonyIDs: string[], interrogationIDs: string[]) => request<CasePublic>(`${base(id)}/confrontations`, {
    npc_id: npcID, evidence_ids: evidenceIDs, testimony_ids: testimonyIDs, interrogation_ids: interrogationIDs,
  }),
  openAssembly: (id: string, suspectID: string, evidenceIDs: string[], testimonyIDs: string[], speech: string) => request<CasePublic>(`${base(id)}/assembly/open`, {
    suspect_id: suspectID, evidence_ids: evidenceIDs, testimony_ids: testimonyIDs, speech,
  }),
  resolveAssembly: (id: string, reply: string) => request<CasePublic>(`${base(id)}/assembly/resolve`, {reply}),
  world: (id: string) => request<WorldSnapshot>(`${base(id)}/world`),
  locations: () => request<Location[]>('/api/v1/world/locations'),
  manifest: () => request<CharacterManifest>('/assets/characters/manifest.json'),
  move: (world: WorldSnapshot, direction: Direction) => request<WorldSnapshot>(`${base(world.game_id)}/movement`, {
    direction, seq: world.player.movement_seq + 1, location_id: world.player.location_id, revision: world.revision,
  }),
  travel: (world: WorldSnapshot, target: LocationID, exitSide?: ExitSide) => request<WorldSnapshot>(`${base(world.game_id)}/travel`, {
    target_location_id: target, revision: world.revision, ...(exitSide ? {exit_side: exitSide} : {}),
  }),
  approach: (id: string, npcID: string) => request<Conversation>(`${base(id)}/approaches`, {npc_id: npcID}),
  closeConversation: (id: string, conversationID: string) => request<void>(`${base(id)}/conversations/${encodeURIComponent(conversationID)}/close`, {}),
  history: (id: string, conversationID: string) => request<{conversation_id: string; messages: Message[]}>(
    `${base(id)}/conversations/${encodeURIComponent(conversationID)}/messages?limit=200`,
  ),
  send: (id: string, conversationID: string, content: string) => request<{conversation_id: string; message: Message}>(
    `${base(id)}/conversations/${encodeURIComponent(conversationID)}/messages`, {content},
  ),
};
