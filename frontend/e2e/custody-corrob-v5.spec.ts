import {test,expect,type Page} from '@playwright/test';
import type {CasePublic,WorldSnapshot,GamePublic} from '../shared/api';

async function city(page:Page,rejected=false){
 const cast:GamePublic={id:'custody-v5',status:'active',characters:['bentinho','florenca','bacamarte'].map(id=>({character:{id,name:id==='bentinho'?'Bentinho':id==='florenca'?'Florença':'Dr. Bacamarte'},alive:true}))};
 const place={id:'praca_verde' as const,name:'Praça Verde',width:960,height:360,ground_y:300,background:'/assets/locations/praca_verde.png',exits:[]};
 const world:WorldSnapshot={game_id:cast.id,world_version:'1',revision:0,location:place,player:{location_id:place.id,x:160,facing:'right',movement_seq:0},visible_npcs:[],travel_targets:[]};
 const state:CasePublic={game_id:cast.id,revision:0,day:3,phase:'day',status:'active',server_time:new Date().toISOString(),phase_ends_at:new Date(Date.now()+300000).toISOString(),seconds_remaining:300,
  journal:[{day:3,title:'O Clarim do Rio',headline:'A cidade exige respostas',body:'Floriano compara os relatos.',victim_id:null,victim_name:null,location_id:null,detention_outcome:'none'}],
  crimes:[],inventory:[],testimonies:[],accusations:[],detained_npc_id:null,ending:null};
 for(const [item_id,name] of [['rosario_seminario','Rosário de contas irregulares'],['carta_santiago','Papel de carta com selo Santiago']]){
  for(const copy of [1,2])state.inventory.push({id:`${item_id}-${copy}`,crime_id:`crime-${copy}`,item_id,name,kind:'unique',description:'Marca individual reconhecida.',examined:false});
  for(const [id,witness_name] of [['florenca','Florença'],['bacamarte','Dr. Bacamarte']])state.testimonies.push({id:`${item_id}:${id}`,day:3,evidence_id:`${item_id}-2`,witness_id:id,witness_name,recognition:'recognizes',claimed_owner_id:'bentinho',text:`Reconheço a marca pessoal de ${name}: pertence a Bentinho.`});
 }
 if(rejected)state.accusations.push({id:'old',day:3,suspect_id:'bentinho',suspect_name:'Bentinho',evidence_ids:[],testimony_ids:[],accepted:false,reason:'Ainda falta examinar uma peça pessoal.'});
 const requests:Array<{path:string,body:any}>=[];
 await page.route('**/api/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;const body=route.request().method()==='POST'?route.request().postDataJSON():null;
  requests.push({path,body});const reply=(json:unknown)=>route.fulfill({json});
  if(path==='/api/v1/games')return reply({id:cast.id});
  if(path==='/api/v1/world/locations')return reply([place]);
  if(path===`/api/v1/games/${cast.id}`)return reply(cast);
  if(path.endsWith('/world'))return reply(world);
  if(path.endsWith('/investigation')){state.server_time=new Date().toISOString();return reply(state);}
  if(path.endsWith('/social/reports'))return reply({reports:[]});
  const ready=body?.evidence_ids?.length===2&&body?.testimony_ids?.length===4;
  if(path.endsWith('/accusations/review'))return reply({ready,route:ready?'corroborated_personal_marks':null,missing:ready?[]:['Relacione duas marcas com fontes externas.'],reason:ready?'Duas peças pessoais diferentes reconhecidas por duas testemunhas cada justificam a custódia.':'Complete o dossiê; pode reapresentá-lo hoje.'});
  if(path.endsWith('/accusations')){
   state.accusations.push({id:`attempt-${state.accusations.length}`,day:3,suspect_id:'bentinho',suspect_name:'Bentinho',evidence_ids:body.evidence_ids,testimony_ids:body.testimony_ids,accepted:ready,reason:ready?'Custódia autorizada.':'Complete o dossiê e tente novamente hoje.'});
   state.revision++;
   if(ready){state.detained_npc_id='bentinho';state.phase='night';}
   return reply(state);
  }
  return route.fulfill({status:404,json:{detail:'Rota não prevista.'}});
 });
 await page.goto('/');await page.locator('#start').click();await expect(page.locator('#scene-loading')).toBeHidden({timeout:30000});await page.locator('#read-journal').click();await page.locator('#open-delegate').click();await page.locator('#accused-npc input[value="bentinho"]').check();
 return {state,requests};
}

async function fullDossier(page:Page){
 for(const input of await page.locator('#accusation-evidence input').all())await input.check();
 for(const input of await page.locator('#accusation-testimonies input').all())await input.check();
}

test('dossiê agrupado de Bentinho é aprovado pelas duas marcas, sem exigir exame',async({page})=>{
 const cityState=await city(page);await fullDossier(page);
 await expect(page.locator('#accusation-evidence input')).toHaveCount(2);
 await page.locator('#review-accusation').click();
 await expect(page.locator('#accusation-review')).toHaveAttribute('data-ready','true');
 await expect(page.locator('#accusation-review')).toContainText('justificam a custódia');
 expect(cityState.state.accusations).toHaveLength(0);
 expect(cityState.requests.some(r=>r.path.endsWith('/inspect'))).toBe(false);
 await page.locator('#submit-accusation').click();
 await expect.poll(()=>cityState.state.detained_npc_id).toBe('bentinho');
 const payload=cityState.requests.find(r=>r.path.endsWith('/accusations'))!.body;
 expect(payload.evidence_ids).toHaveLength(2);expect(payload.testimony_ids).toHaveLength(4);
});

test('recusa anterior não bloqueia completar o dossiê nem pedir prisão no mesmo dia',async({page})=>{
 const cityState=await city(page,true);
 await expect(page.locator('#submit-accusation')).toBeEnabled();
 await page.locator('#review-accusation').click();
 await expect(page.locator('#accusation-review')).toHaveAttribute('data-ready','false');
 expect(cityState.state.accusations).toHaveLength(1);
 await fullDossier(page);await page.locator('#submit-accusation').click();
 await expect.poll(()=>cityState.state.detained_npc_id).toBe('bentinho');
 expect(cityState.state.accusations.at(-1)?.day).toBe(3);
});
