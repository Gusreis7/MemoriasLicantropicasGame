import {describe,expect,it} from 'vitest';
import {ambientResourceIDs,criticalCharacterIDs,lightingPeriod} from './scene-resources';
import type {WorldSnapshot} from '../shared/api';

describe('recursos necessários à cena',()=>{
  it('inicia apenas jogador e pessoas visíveis, sem antecipar o elenco inteiro',()=>{
    const world={visible_npcs:[{sprite_id:'rubiao'}]} as WorldSnapshot;
    expect([...criticalCharacterIDs(world)]).toEqual(['player','rubiao']);
    expect(ambientResourceIDs('praca_verde')).toContain('clarim');
    expect(ambientResourceIDs('praca_verde')).not.toContain('capoeira');
    expect(ambientResourceIDs('cais_lanternas')).toContain('capoeira');
  });
  it('mantém noite fora do carregamento de uma manhã',()=>{
    expect(lightingPeriod('day',0)).toBe('morning');
    expect(lightingPeriod('day',.7)).toBe('sunset');
    expect(lightingPeriod('night',1)).toBe('midnight');
  });
});
