import {describe,it,expect} from 'vitest';
import {notebookResidents} from './notebook-residents';
import type {GamePublic,JournalEdition} from '../shared/api';
describe('memorial do caderno',()=>{
  it('inclui a primeira vítima como falecida sem alterar os suspeitos',()=>{
    const cast:GamePublic['characters']=[{character:{id:'capitu',name:'Capitu'},alive:true}];
    const journal:JournalEdition[]=[{day:1,title:'Clarim',headline:'Notícia',body:'Relato',victim_id:'bras_cubas',victim_name:'Brás Cubas',location_id:'praca_verde',detention_outcome:'none'}];
    expect(notebookResidents(cast,[])).toEqual(cast);
    const residents=notebookResidents(cast,journal);
    expect(residents[0]).toMatchObject({character:{id:'bras_cubas'},alive:false});
    expect(cast).toHaveLength(1);
    expect(notebookResidents(residents,journal)).toHaveLength(2);
  });
});
