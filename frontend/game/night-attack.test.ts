import {describe,it,expect} from 'vitest';
import {newNightVictim,strikeVariant,STRIKES} from './night-attack';
import type {JournalEdition} from '../shared/api';
const edition=(day:number,victim_id:string|null='rubiao'):JournalEdition=>({day,victim_id,victim_name:'Rubião',location_id:'praca_verde',title:'Clarim',headline:'Notícia',body:'Relato',detention_outcome:'none'});
describe('ataque noturno público',()=>{
  it('usa quatro golpes antes de repetir',()=>{expect([2,3,4,5].map(strikeVariant)).toEqual([0,1,2,3]);expect(strikeVariant(6)).toBe(0);expect(new Set(STRIKES).size).toBe(4);});
  it('só encena morte nova confirmada, nunca primeira vítima ou noite sem morte',()=>{
    expect(newNightVictim([], [edition(1)])).toBeNull();expect(newNightVictim([edition(1)], [edition(1),edition(2,null)])).toBeNull();
    expect(newNightVictim([edition(1)], [edition(1),edition(2)])?.day).toBe(2);expect(newNightVictim([edition(2)], [edition(2)])).toBeNull();
  });
});
