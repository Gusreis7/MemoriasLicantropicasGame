import {describe, expect, it} from 'vitest';
import {personWords} from '../shared/language';

describe('concordância nas mensagens da delegacia',()=>{
  it('usa a identidade pública feminina e masculina',()=>{
    expect(personWords({id:'capitu',name:'Capitu',grammatical_gender:'feminine'})).toEqual({accused:'A acusada',release:'solta',expelled:'Expulsa',deceased:'Falecida',alive:'Viva'});
    expect(personWords({id:'bentinho',name:'Bentinho',grammatical_gender:'masculine'})).toEqual({accused:'O acusado',release:'solto',expelled:'Expulso',deceased:'Falecido',alive:'Vivo'});
  });
  it('usa texto neutro para catálogos anteriores sem deduzir pelo nome',()=>{
    expect(personWords({id:'capitu',name:'Capitu'}).release).toBe('posta em liberdade');
  });
});
