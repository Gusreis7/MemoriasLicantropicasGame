import {test,expect} from '@playwright/test';

test('texto hostil do jogador e do NPC permanece texto, inclusive no histórico',async({page})=>{
 const payload='<img src=x onerror="window.injected=true"><script>window.injected=true</script>';
 const game={id:'security-ui',status:'active',characters:[{character:{id:'capitu',name:'Capitu'},alive:true}]};
 const location={id:'praca_verde',name:'Praça Verde',width:960,height:360,ground_y:300,background:'/assets/locations/praca_verde.png',exits:[]};
 const world={game_id:game.id,world_version:'1',revision:0,location,player:{location_id:location.id,x:160,facing:'right',movement_seq:0},visible_npcs:[{npc_id:'capitu',name:'Capitu',x:170,sprite_id:'capitu',can_approach:true}],travel_targets:[]};
 const state={game_id:game.id,revision:0,day:1,phase:'day',status:'active',server_time:new Date().toISOString(),phase_ends_at:new Date(Date.now()+300000).toISOString(),seconds_remaining:300,journal:[{day:1,title:'O Clarim do Rio',headline:'Caso aberto',body:'Floriano investiga.',victim_id:null,victim_name:null,location_id:null,detention_outcome:'none'}],crimes:[],inventory:[],testimonies:[],accusations:[],detained_npc_id:null,ending:null};
 const messages:any[]=[];
 await page.route('**/api/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;const reply=(json:unknown)=>route.fulfill({json});
  if(path==='/api/v1/games')return reply({id:game.id});
  if(path==='/api/v1/world/locations')return reply([location]);
  if(path===`/api/v1/games/${game.id}`)return reply(game);
  if(path.endsWith('/investigation'))return reply(state);
  if(path.endsWith('/world'))return reply(world);
  if(path.endsWith('/movement'))return reply(world);
  if(path.endsWith('/approaches'))return reply({id:'chat',game_id:game.id,npc_id:'capitu',created_at:new Date().toISOString()});
  if(path.endsWith('/close'))return route.fulfill({status:204});
  if(path.endsWith('/messages')){
   if(route.request().method()==='POST'){
    for(const speaker of ['player','npc'])messages.push({id:speaker,speaker,content:payload,created_at:new Date().toISOString()});
    return reply({conversation_id:'chat',message:messages.at(-1)});
   }
   return reply({conversation_id:'chat',messages});
  }
  return route.fulfill({status:404});
 });
 await page.goto('/');await page.locator('#start').click();await expect(page.locator('#scene-loading')).toBeHidden({timeout:30000});await page.locator('#read-journal').click();
 await page.locator('#approach').click();await expect(page.locator('#message-input')).toBeEnabled();await page.locator('#message-input').fill(payload);await page.locator('#send-message').click();
 await expect(page.locator('.message.npc .message-content')).toHaveText(payload);
 await expect(page.locator('#messages img, #messages script')).toHaveCount(0);
 expect(await page.evaluate(()=>Boolean((window as any).injected))).toBe(false);
 await page.locator('#close-dialogue').click();await page.locator('#approach').click();
 await expect(page.locator('.message.npc .message-content')).toHaveText(payload);
 await expect(page.locator('#messages img, #messages script')).toHaveCount(0);
 expect(await page.evaluate(()=>Boolean((window as any).injected))).toBe(false);
});
