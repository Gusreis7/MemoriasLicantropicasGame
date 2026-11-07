import type {LocationID, WorldSnapshot} from '../shared/api';

export function criticalCharacterIDs(world: WorldSnapshot): Set<string> {
  return new Set(['player', ...world.visible_npcs.map(npc => npc.sprite_id)]);
}

export function ambientResourceIDs(location: LocationID): string[] {
  return ['scene-life', 'citizens', 'animals-walk',
    ...(location === 'praca_verde' ? ['clarim'] : []),
    ...(location === 'cais_lanternas' ? ['capoeira'] : [])];
}

export function lightingPeriod(phase: string | undefined, progress: number): 'morning' | 'sunset' | 'midnight' {
  return phase === 'night' ? 'midnight' : progress > 2 / 3 ? 'sunset' : 'morning';
}
