import type {LocationID} from '../shared/api';

export const CITIZEN_TYPES = ['quitandeira', 'estivador', 'costureira', 'jornaleiro', 'caixeiro', 'cocheiro'] as const;
export interface CitizenPlacement {
  id: string; name: string; occupation: typeof CITIZEN_TYPES[number]; x: number; range: number; speed: number;
}

// Everyday residents are scenic inhabitants. Suspects and testimony remain server-owned.
export const POPULATION: Record<LocationID, CitizenPlacement[]> = {
  praca_verde: [
    {id:'rita',name:'Rita',occupation:'quitandeira',x:340,range:28,speed:7},
    {id:'joaquim',name:'Joaquim',occupation:'jornaleiro',x:640,range:80,speed:13},
    {id:'antonio',name:'Antônio',occupation:'cocheiro',x:765,range:58,speed:10},
  ],
  cabana_capitu: [
    {id:'elisa',name:'Elisa',occupation:'costureira',x:290,range:70,speed:9},
    {id:'rosaria',name:'Rosária',occupation:'quitandeira',x:640,range:36,speed:7},
    {id:'manoel',name:'Manoel',occupation:'cocheiro',x:850,range:56,speed:10},
  ],
  casa_verde: [
    {id:'amelia',name:'Amélia',occupation:'costureira',x:285,range:60,speed:9},
    {id:'augusto',name:'Augusto',occupation:'caixeiro',x:645,range:54,speed:11},
    {id:'julio',name:'Júlio',occupation:'jornaleiro',x:750,range:80,speed:13},
  ],
  cafe_largo: [
    {id:'alberto',name:'Alberto',occupation:'caixeiro',x:300,range:44,speed:10},
    {id:'leonor',name:'Leonor',occupation:'costureira',x:645,range:52,speed:9},
    {id:'sebastiao',name:'Sebastião',occupation:'cocheiro',x:805,range:50,speed:10},
  ],
  cais_lanternas: [
    {id:'pedro',name:'Pedro',occupation:'estivador',x:225,range:90,speed:12},
    {id:'benedita',name:'Benedita',occupation:'quitandeira',x:390,range:28,speed:7},
    {id:'vicente',name:'Vicente',occupation:'jornaleiro',x:885,range:48,speed:13},
  ],
};
