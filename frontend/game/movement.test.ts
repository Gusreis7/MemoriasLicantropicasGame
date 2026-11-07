import {describe, expect, it, vi} from 'vitest';
import {ApiError, type WorldSnapshot, type Direction, type MovementInput} from '../shared/api';
import {clampX, closestNPC, MovementController, WALK_SPEED} from './movement';
function snapshot(x=160):WorldSnapshot{return {game_id:'game',world_version:'1',revision:0,location:{id:'praca_verde',name:'Praça',width:960,height:360,ground_y:300,background:'/scene.png',exits:[]},player:{location_id:'praca_verde',x,facing:'right',movement_seq:0,input_seq:0},visible_npcs:[{npc_id:'rubiao',name:'Rubião',x:440,sprite_id:'rubiao',can_approach:false}],travel_targets:[]};}
function network(delays:number[]){
 let now=0,requests=0,last=0,credit=0,accepted=0;let canonical=snapshot(),direction:Direction='idle';
 const events:Array<{at:number;run:()=>void}>=[],failed=vi.fn();
 const send=vi.fn((world:WorldSnapshot,_desired:Direction,inputs:MovementInput[]=[])=>new Promise<WorldSnapshot>(resolve=>{
  const rtt=delays[requests++%delays.length];events.push({at:now+rtt/2,run:()=>{
   credit=direction==='idle'?0:Math.min(1000,credit+now-last);last=now;let x=canonical.player.x;
   for(const input of inputs){
    if(input.seq!==accepted+1)throw Error('input gap');if(input.duration_ms>credit+.000001)break;
    if(input.duration_ms===0){direction=input.direction;if(direction==='idle')credit=0;}
    else{credit-=input.duration_ms;x=clampX(x+(direction==='left'?-1:1)*WALK_SPEED*input.duration_ms/1000,960);}
    accepted=input.seq;
   }
   canonical={...world,revision:world.revision+1,player:{...world.player,x,input_seq:accepted,movement_seq:world.player.movement_seq+1}};
   const reply=canonical;events.push({at:now+rtt/2,run:()=>resolve(reply)});
  }});
 }));
 const controller=new MovementController(snapshot(),send,async()=>canonical,vi.fn(),failed,()=>now);
 async function frame(desired:Direction,delta=10){now+=delta;let i;while((i=events.findIndex(e=>e.at<=now))>=0){events.splice(i,1)[0].run();for(let j=0;j<8;j++)await Promise.resolve();}controller.update(delta,desired);}
 return {controller,send,failed,frame,get canonical(){return canonical;}};
}
describe('entradas confirmadas',()=>{
 it('respeita limites e alcance',()=>{expect(clampX(-1,960)).toBe(32);expect(clampX(999,960)).toBe(928);expect(closestNPC(snapshot(),160)).toBeUndefined();expect(closestNPC(snapshot(),400)?.npc_id).toBe('rubiao');});
 for(const delays of [[200],[120,320,180,450,200,600]])it(`não desliza ao soltar com RTT ${delays}`,async()=>{
  const n=network(delays);for(let i=0;i<18;i++)await n.frame('right');const x=n.controller.x;expect(x).toBeCloseTo(197.8);
  for(let i=0;i<220;i++){await n.frame('idle');expect(n.controller.x).toBeCloseTo(x,7);}
  expect(n.canonical.player.x).toBeCloseTo(x,7);expect(n.failed).not.toHaveBeenCalled();n.controller.dispose();
 });
 it('confirma inversões rápidas e um frame longo na ordem certa',async()=>{
  const n=network([600,180,320]);for(let i=0;i<10;i++)await n.frame('right');for(let i=0;i<4;i++)await n.frame('left');await n.frame('right',180);
  const x=n.controller.x;expect(x).toBeCloseTo(160+WALK_SPEED*(.1-.04+.18));
  for(let i=0;i<260;i++){await n.frame('idle');expect(n.controller.x).toBeCloseTo(x,7);}expect(n.canonical.player.x).toBeCloseTo(x,7);expect(n.failed).not.toHaveBeenCalled();n.controller.dispose();
 });
 it('drena a parada antes de ações sem acrescentar entradas nem deslocar sprite',async()=>{
  vi.useFakeTimers();try{const n=network([200]);for(let i=0;i<18;i++)await n.frame('right');const x=n.controller.x;
   let done=false;const stopped=n.controller.stop().then(()=>{done=true;});
   n.controller.update(10,'right');expect(n.controller.x).toBeCloseTo(x,7);
   for(let i=0;i<180&&!done;i++){await n.frame('idle');await vi.advanceTimersByTimeAsync(10);expect(n.controller.x).toBeCloseTo(x,7);}await stopped;
   expect(n.canonical.player.x).toBeCloseTo(x,7);expect(n.send.mock.calls.at(-1)?.[1]).toBe('idle');expect(n.failed).not.toHaveBeenCalled();n.controller.dispose();
  }finally{vi.useRealTimers();}
 });
 it('limita previsão durante desconexão',()=>{const send=vi.fn(()=>new Promise<WorldSnapshot>(()=>{}));const c=new MovementController(snapshot(),send,vi.fn(),vi.fn(),vi.fn());for(let i=0;i<300;i++)c.update(10,'right');expect(c.x).toBeLessThanOrEqual(160+WALK_SPEED+.00001);expect(send).toHaveBeenCalledTimes(1);c.dispose();});
 it('ressincroniza conflito e aplica sequência após viagem',async()=>{const fresh={...snapshot(220),revision:3},refresh=vi.fn(async()=>fresh);const c=new MovementController(snapshot(),vi.fn(async()=>{throw new ApiError(409,'Conflito');}),refresh,vi.fn(),vi.fn());c.update(16,'right');for(let i=0;i<8;i++)await Promise.resolve();expect(refresh).toHaveBeenCalledOnce();expect(c.world.revision).toBe(3);expect(c.x).toBe(220);c.accept({...snapshot(96),player:{...snapshot(96).player,input_seq:80}});expect(c.world.player.input_seq).toBe(80);expect(c.direction).toBe('idle');c.dispose();});
 it('mantém a última orientação local após inverter e soltar antes do ACK',async()=>{
  const n=network([600]);for(let i=0;i<10;i++)await n.frame('right');await n.frame('left');
  expect(n.controller.facing).toBe('left');
  for(let i=0;i<180;i++){await n.frame('idle');expect(n.controller.facing).toBe('left');}
  expect(n.failed).not.toHaveBeenCalled();n.controller.dispose();
 });
 it('não confirma parada se não conseguiu obter posição canônica após falha',async()=>{
  const error=new ApiError(0,'Conexão interrompida');const c=new MovementController(snapshot(),vi.fn(async()=>{throw error;}),vi.fn(async()=>{throw error;}),vi.fn(),vi.fn());
  c.update(16,'right');await expect(c.stop()).rejects.toBe(error);c.dispose();
 });
 it('preserva NPCs observados durante comando em trânsito sem corrigir a pose',async()=>{
  const n=network([200]);await n.frame('right');const x=n.controller.x;
  const observed={...n.controller.world,revision:1,visible_npcs:[],player:{...n.controller.world.player,x:500,movement_seq:1,input_seq:1}};
  expect(n.controller.observe({...observed,player:{...observed.player,movement_seq:2,input_seq:999}})).toBe(false);
  expect(n.controller.observe(observed)).toBe(true);expect(n.controller.x).toBe(x);
  expect(n.controller.world.player.movement_seq).toBe(0);
  expect(n.controller.world.player.x).toBe(160);
  for(let i=0;i<30;i++)await n.frame('right');
  expect(n.controller.world.visible_npcs).toEqual([]);
  expect(n.failed).not.toHaveBeenCalled();n.controller.dispose();
 });
 it('suspende a fase sem enviar entradas antigas para o novo dia',async()=>{
  const n=network([200]);await n.frame('right');let done=false;
  const suspended=n.controller.suspend().then(()=>{done=true;});
  for(let i=0;i<30&&!done;i++)await n.frame('right');await suspended;
  expect(n.send).toHaveBeenCalledTimes(1);expect(n.controller.direction).toBe('idle');
  n.controller.accept(snapshot(96));expect(n.controller.x).toBe(96);n.controller.dispose();
 });
 it('observa NPCs sem interromper previsão',()=>{const c=new MovementController(snapshot(),vi.fn(),vi.fn(),vi.fn(),vi.fn());c.x=207;c.direction='right';expect(c.observe({...snapshot(),revision:2,visible_npcs:[]})).toBe(true);expect(c.x).toBe(207);expect(c.observe(snapshot())).toBe(false);c.dispose();});
});
