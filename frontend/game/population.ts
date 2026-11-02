import type {LocationID} from '../shared/api';

export const CITIZEN_TYPES = ['quitandeira', 'estivador', 'costureira', 'jornaleiro', 'caixeiro', 'cocheiro'] as const;
export interface CitizenPlacement {
  id: string; name: string; occupation: typeof CITIZEN_TYPES[number]; x: number;
}

// Everyday residents are scenic inhabitants. Suspects and testimony remain server-owned.
export const POPULATION: Record<LocationID, CitizenPlacement[]> = {
  praca_verde: [
    {id:'rita',name:'Rita',occupation:'quitandeira',x:340},
    {id:'joaquim',name:'Joaquim',occupation:'jornaleiro',x:640},
    {id:'antonio',name:'Antônio',occupation:'cocheiro',x:765},
  ],
  cabana_capitu: [
    {id:'elisa',name:'Elisa',occupation:'costureira',x:290},
    {id:'rosaria',name:'Rosária',occupation:'quitandeira',x:640},
    {id:'manoel',name:'Manoel',occupation:'cocheiro',x:850},
  ],
  casa_verde: [
    {id:'amelia',name:'Amélia',occupation:'costureira',x:285},
    {id:'augusto',name:'Augusto',occupation:'caixeiro',x:645},
    {id:'julio',name:'Júlio',occupation:'jornaleiro',x:750},
  ],
  cafe_largo: [
    {id:'alberto',name:'Alberto',occupation:'caixeiro',x:300},
    {id:'leonor',name:'Leonor',occupation:'costureira',x:645},
    {id:'sebastiao',name:'Sebastião',occupation:'cocheiro',x:805},
  ],
  cais_lanternas: [
    {id:'pedro',name:'Pedro',occupation:'estivador',x:225},
    {id:'benedita',name:'Benedita',occupation:'quitandeira',x:390},
    {id:'vicente',name:'Vicente',occupation:'jornaleiro',x:885},
  ],
};
