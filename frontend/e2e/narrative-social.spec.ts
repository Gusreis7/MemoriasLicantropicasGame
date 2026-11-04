import {test, expect, type Page} from '@playwright/test';
import type {CasePublic, GamePublic, Location, Message, WorldSnapshot} from '../shared/api';

async function fixture(page: Page, expelPlayer = true) {
  const names = {capitu:'Capitu', bentinho:'Bentinho', escobar:'Escobar', rubiao:'Rubião'};
  const cast: GamePublic = {id:'narrative-ui', status:'active', characters:Object.entries(names).map(([id,name])=>({character:{id,name},alive:true}))};
  const location: Location = {id:'praca_verde',name:'Praça Verde',width:960,height:360,ground_y:300,background:'/assets/locations/praca_verde.png',exits:[]};
  const world: WorldSnapshot = {game_id:cast.id,world_version:'1',revision:0,location,player:{location_id:location.id,x:430,facing:'right',movement_seq:0},visible_npcs:[{npc_id:'capitu',name:'Capitu',x:440,sprite_id:'capitu',can_approach:true}],travel_targets:[]};
  const state: CasePublic = {game_id:cast.id,revision:0,day:1,phase:'day',status:'active',server_time:new Date().toISOString(),phase_ends_at:new Date(Date.now()+300000).toISOString(),seconds_remaining:300,
    journal:[{day:1,title:'O Clarim do Rio',headline:'A cidade investiga',body:'Um caso para Floriano.',victim_id:null,victim_name:null,location_id:null,detention_outcome:'none'}],
    crimes:[],inventory:[{id:'evidence',crime_id:'crime',item_id:'lenco',name:'Lenço de linho',kind:'common',description:'Um tecido recolhido no cais.'}],testimonies:[],accusations:[],detained_npc_id:null,ending:null};
  const messages: Message[] = [];
  const requests: Array<{path:string;body:Record<string,unknown>}> = [];
  const addMessage=(speaker:Message['speaker'],content:string)=>messages.push({id:`message-${messages.length}`,speaker,content,useful:speaker==='npc',created_at:new Date().toISOString()});
  await page.route('**/api/v1/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    const body=route.request().method()==='POST' ? route.request().postDataJSON() : {};
    requests.push({path,body});
    const json=(data:unknown)=>route.fulfill({json:data});
    if(path==='/api/v1/games')return json({id:cast.id});
    if(path==='/api/v1/world/locations')return json([location]);
    if(path===`/api/v1/games/${cast.id}`)return json(cast);
    if(path.endsWith('/world'))return json(world);
    if(path.endsWith('/investigation')){state.server_time=new Date().toISOString();return json(state);}
    if(path.endsWith('/movement')){world.player.movement_seq=body.seq;return json(world);}
    if(path.endsWith('/approaches'))return json({id:'conversation',game_id:cast.id,npc_id:'capitu',created_at:new Date().toISOString()});
    if(path.endsWith('/close'))return route.fulfill({status:204});
    if(path.endsWith('/social/reports'))return json({reports:messages.filter(m=>m.speaker==='npc').map(m=>({...m,speaker_id:'capitu',speaker_name:'Capitu',source_name:null}))});
    if(path.endsWith('/messages')){
      if(route.request().method()==='POST') {addMessage('player',body.content);addMessage('npc','O lenço era de uma cliente; já lhe disse que reconheço o bordado.');return json({conversation_id:'conversation',message:messages.at(-1)});}
      return json({conversation_id:'conversation',messages});
    }
    if(path.endsWith('/present')) {
      addMessage('player','Mostro o lenço de linho a Capitu.');addMessage('npc','Reconheço este bordado; pertence a uma cliente.');
      state.testimonies=[{id:'testimony',day:1,evidence_id:'evidence',witness_id:'capitu',witness_name:'Capitu',recognition:'recognizes',claimed_owner_id:null,text:'Reconheço este bordado; pertence a uma cliente.'}];state.revision++;return json(state);
    }
    if(path.endsWith('/assembly/open')){
      state.assembly_session={id:'session',suspect_id:body.suspect_id,phase:'debate',deadline:new Date(Date.now()+60000).toISOString(),opening_speech:body.speech,evidence_ids:body.evidence_ids,testimony_ids:body.testimony_ids,messages:[{speaker_id:'player',text:body.speech},{speaker_id:'bentinho',text:'E quem nos garante que o detetive não nos engana?'},{speaker_id:'capitu',text:'Deixe-me explicar o que sei sobre esse lenço.'}]};state.revision++;return json(state);
    }
    if(path.endsWith('/assembly/resolve')){
      state.assembly_session={...state.assembly_session!,phase:'resolved',reply:body.reply};
      state.assembly={suspect_id:'capitu',messages:[...state.assembly_session.messages,{speaker_id:'player',text:body.reply}],day:1,required_votes:3,expelled:true,outcome:'player_expelled',votes:[{voter_id:'player',target_id:'capitu',expel:false,reason:'Mantém sua acusação.'},...Object.keys(names).map(voter_id=>({voter_id,target_id:'player',expel:true,reason:'Retira sua confiança no detetive.'}))]};
      state.status='lost';state.phase='finished';cast.status='lost';state.ending={result:'lost',werewolf_id:'escobar',method:'assembly',message:'Floriano foi expulso da cidade.'};state.journal.push({day:1,title:'O Clarim do Rio',headline:'A cidade expulsa Floriano',body:'A assembleia retirou sua confiança no detetive.',victim_id:null,victim_name:null,location_id:null,detention_outcome:'none'});if(!expelPlayer){state.assembly.expelled=false;state.assembly.outcome='no_majority';state.assembly.votes=state.assembly.votes.map(v=>({...v,target_id:null,expel:false}));state.status='active';state.phase='day';cast.status='active';state.ending=null;state.journal.pop();}
      state.revision++;return json(state);
    }
    return route.fulfill({status:404,json:{detail:'Rota não prevista.'}});
  });
  return {state,requests};
}

async function begin(page:Page){await page.goto('/');await page.locator('#start').click();await expect(page.locator('#scene-loading')).toBeHidden({timeout:30000});await page.locator('#read-journal').click();}

test('pista integra a cronologia e a pergunta seguinte continua a conversa natural',async({page})=>{
  const city=await fixture(page);await begin(page);await expect(page.locator('#approach')).toBeVisible();await page.locator('#approach').click();await expect(page.locator('#message-input')).toBeEnabled();
  await expect(page.locator('#interrogation-panel')).toHaveCount(0);
  await page.locator('#message-input').fill('Quero continuar daqui.');await page.locator('#present-button').click();
  await expect(page.locator('#messages')).toContainText('Mostro o lenço');await expect(page.locator('#messages')).toContainText('Reconheço este bordado');
  await expect(page.locator('#message-input')).toHaveValue('Quero continuar daqui.');
  await page.locator('#message-input').fill('Quem era a cliente?');await page.locator('#send-message').click();await expect(page.locator('#messages')).toContainText('O lenço era de uma cliente');
  expect(city.requests.some(r=>r.path.endsWith('/interrogations')||r.path.endsWith('/confrontations'))).toBe(false);
});

test('assembleia tem abertura, réplica curta e derrota quando a cidade expulsa Floriano',async({page})=>{
  const city=await fixture(page);await begin(page);await page.locator('#open-assembly').click();
  await expect(page.locator('#assembly-overlay')).toBeVisible();await page.locator('#assembly-suspects input[value="capitu"]').check();
  await page.locator('#assembly-evidence input').check();await page.locator('#assembly-opening').fill('Reconheçam esta pista e ouçam o que Capitu tem a dizer.');await page.locator('#start-assembly').click();
  await expect(page.locator('#assembly-chat')).toContainText('o detetive não nos engana');await expect(page.locator('#assembly-countdown')).toContainText('para votar');
  await page.locator('#close-assembly').click();await page.locator('#open-assembly').click();await expect(page.locator('#assembly-chat')).toContainText('Deixe-me explicar');
  await page.locator('#assembly-reply').fill('Peço que avaliem o lenço antes de me acusar.');await page.locator('#finish-assembly').click();
  await expect(page.locator('#phase-title')).toHaveText('Floriano foi expulso da cidade.');await expect(page.locator('#victory-paper')).toBeVisible();await expect(page.locator('#victory-headline')).toHaveText('A cidade expulsa Floriano');
  const request=city.requests.find(r=>r.path.endsWith('/assembly/open'))!;expect(request.body.evidence_ids).toEqual(['evidence']);expect(request.body).not.toHaveProperty('votes');
  expect(city.requests.find(r=>r.path.endsWith('/assembly/resolve'))?.body).toEqual({reply:'Peço que avaliem o lenço antes de me acusar.'});
});


test('transcrição final conserva a réplica do jogador mesmo sem maioria',async({page})=>{
  await fixture(page,false);await begin(page);await page.locator('#open-assembly').click();
  await page.locator('#assembly-suspects input[value="capitu"]').check();await page.locator('#assembly-opening').fill('Ouçam antes de decidir sobre esta pista.');await page.locator('#start-assembly').click();
  await expect(page.locator('#assembly-reply')).toBeVisible();await page.locator('#assembly-reply').fill('Registramos as divergências; procuremos outra fonte.');await page.locator('#finish-assembly').click();
  await expect(page.locator('#assembly-result')).toContainText('não alcançou maioria');
  await expect(page.locator('#assembly-chat')).toContainText('Registramos as divergências; procuremos outra fonte.');
});


test('relato útil fica dourado no chat, no histórico reaberto e no caderno',async({page})=>{
  await fixture(page);await begin(page);await page.locator('#approach').click();
  await expect(page.locator('#message-input')).toBeEnabled();
  await page.locator('#message-input').fill('O que reconhece neste objeto?');await page.locator('#send-message').click();
  await expect(page.locator('#messages .message.npc.useful-report')).toHaveCount(1);
  await expect(page.locator('#messages .message.player.useful-report')).toHaveCount(0);
  await expect(page.locator('#messages .useful-report-label')).toContainText('Relato útil');
  await page.locator('#close-dialogue').click();await page.locator('#approach').click();
  await expect(page.locator('#messages .message.npc.useful-report')).toHaveCount(1);
  await page.locator('#close-dialogue').click();await page.locator('#open-notebook').click();
  await page.locator('#notebook-tab-reports').click();
  await expect(page.locator('#heard-report-list .testimony-card.useful-report')).toHaveCount(1);
  await expect(page.locator('#heard-report-list')).toContainText('O lenço era');
});
