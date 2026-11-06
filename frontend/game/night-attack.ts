import type {CharacterManifest, JournalEdition, WorldSnapshot} from '../shared/api';
import {wolfWalkFrame} from './wolf-walk';
import {gameAudio} from './audio';

export const STRIKES = ['garra lateral', 'golpe descendente', 'bote rasteiro', 'salto de emboscada'] as const;
/** Stepped pixel clusters, with a dark wine edge and muted red core. */
function drawPixelClaws(ctx:CanvasRenderingContext2D,variant:number,progress:number) {
  ctx.save();ctx.globalAlpha=Math.min(1,(1-progress)*3);
  const count=Math.min(15,Math.ceil(progress*30));
  for(let claw=0;claw<3;claw++) for(let step=0;step<count;step++) {
    const x=variant===1?580+claw*18+Math.floor(step/4)*3:570+(variant===2?0:claw*18)+step*3;
    const y=variant===1?211+step*4:variant===2?249+claw*14+Math.floor(step/4)*3:235+step*3;
    const thickness=step<3||step>11?6:9;
    ctx.fillStyle='#420f21';ctx.fillRect(x-3,y-3,thickness+6,9);
    ctx.fillStyle='#781b36';ctx.fillRect(x,y,thickness,6);
    if(step>3&&step<11){ctx.fillStyle='#9b3048';ctx.fillRect(x,y,3,3);}
  }
  ctx.restore();
}
export function strikeVariant(day: number) {return Math.max(0, Math.trunc(day) - 2) % STRIKES.length;}
export function newNightVictim(previous: JournalEdition[], next: JournalEdition[]) {
  const latest = next.at(-1);
  return latest?.victim_id && latest.location_id && latest.day > 1 && !previous.some(item => item.day === latest.day && item.victim_id === latest.victim_id) ? latest : null;
}
type Frame = {frame: {x:number;y:number;w:number;h:number}; spriteSourceSize: {x:number;y:number}; sourceSize:{w:number;h:number}};
type Actor = {image:HTMLImageElement;frames:Record<string,Frame>};
let cancel: (()=>void) | undefined;
export function cancelNightAttack() {cancel?.();}
const image = (path:string, signal:AbortSignal) => new Promise<HTMLImageElement>((resolve,reject)=>{
  const img = new Image(); img.onload=()=>resolve(img); img.onerror=()=>reject(new Error('Arte indisponível'));
  signal.addEventListener('abort',()=>{img.src='';reject(new Error('Cancelado'));},{once:true}); img.src=path;
});
async function actor(path:string, atlas:string, signal:AbortSignal):Promise<Actor> {
  const [img,data]=await Promise.all([image(path,signal),fetch(atlas,{signal}).then(r=>r.json())]);
  return {image:img,frames:data.frames};
}
/** Replay only a public, server-confirmed death. The monster has no suspect identity. */
export async function playNightAttack(edition:JournalEdition, manifest:CharacterManifest, witnesses:WorldSnapshot['visible_npcs']) {
  cancelNightAttack();
  const victimAsset=manifest.characters.find(a=>a.id===edition.victim_id);
  if(!victimAsset?.atlasPath || !edition.location_id)return;
  const abort=new AbortController();
  const loadTimeout=window.setTimeout(()=>abort.abort(),8000);
  let stop=()=>abort.abort(); cancel=()=>stop();
  const reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const root=document.createElement('div'); root.className='night-attack-overlay'; root.id='night-attack-overlay';
  root.innerHTML='<section class="night-attack-dialog" role="dialog" aria-modal="true" aria-label="Acontecimentos da noite"><p class="eyebrow">MEIA-NOITE · A CIDADE ADORMECE</p><canvas width="960" height="360" aria-label="Um lobisomem espreita uma pessoa e desfere um golpe; a vítima cai nas sombras."></canvas><p role="status">Passos sorrateiros atravessam a noite…</p><button class="button secondary" type="button">Pular animação</button></section>';
  try {
    const bystanders=witnesses.filter(n=>n.npc_id!==edition.victim_id).slice(0,3);
    const [bg,wolf,wolfWalking,victim,fallen,pedestrians,...extras]=await Promise.all([
      image(`/assets/locations/${edition.location_id}-00h.png`,abort.signal),
      actor('/assets/cinematics/werewolf.png','/assets/cinematics/werewolf.json',abort.signal),
      actor('/assets/cinematics/werewolf-walk.png','/assets/cinematics/werewolf-walk.json',abort.signal),
      actor(victimAsset.path,victimAsset.atlasPath,abort.signal),
      Promise.all([
        image(`/assets/cinematics/fallen/${edition.victim_id}.png`,abort.signal),
        fetch(`/assets/cinematics/fallen/fallen-${edition.victim_id}.json`,{signal:abort.signal}).then(r=>{if(!r.ok)throw new Error('Pose indisponível');return r.json();}),
      ]).then(([image,data])=>({image,bbox:(data.renderBbox ?? data.bbox) as number[]})).catch(()=>null),
      actor('/assets/ambient/citizens.png','/assets/ambient/citizens.json',abort.signal),
      ...bystanders.map(n=>{const a=manifest.characters.find(a=>a.id===n.npc_id)!;return actor(a.path,a.atlasPath!,abort.signal);}),
    ]);
    clearTimeout(loadTimeout);
    if(abort.signal.aborted)return;
    document.body.append(root);
    if(fallen) root.dataset.fallenVictim=edition.victim_id ?? '';
    gameAudio.setNight(true);
    if (!reduced) gameAudio.effect('sneak');
    const canvas=root.querySelector('canvas')!; const ctx=canvas.getContext('2d')!;
    const button=root.querySelector('button')!; const previousFocus=document.activeElement as HTMLElement|null; button.focus();
    const drawActor=(a:Actor,frame:string,x:number,y:number,w:number,h:number,angle=0,alpha=1)=>{
      const f=a.frames[frame]??Object.values(a.frames)[0]; if(!f)return;
      ctx.save();ctx.globalAlpha=alpha;ctx.translate(x,y);ctx.rotate(angle);ctx.scale(w/f.sourceSize.w,h/f.sourceSize.h);
      ctx.drawImage(a.image,f.frame.x,f.frame.y,f.frame.w,f.frame.h,-f.sourceSize.w/2+f.spriteSourceSize.x,-f.sourceSize.h+f.spriteSourceSize.y,f.frame.w,f.frame.h);ctx.restore();
    };
    root.dataset.strike=String(strikeVariant(edition.day));
    await new Promise<void>(resolve=>{
      let raf=0; let ended=false; let lastFootfall=-1; let lastEscapeFootfall=-1; let slashed=false; let hit=false; let howled=false; const start=performance.now();
      const finish=()=>{if(ended)return;ended=true;cancelAnimationFrame(raf);document.removeEventListener('keydown',key);root.remove();previousFocus?.focus({preventScroll:true});resolve();};
      const key=(e:KeyboardEvent)=>{if(e.key==='Escape'){e.preventDefault();finish();}};
      stop=()=>{abort.abort();finish();};button.onclick=finish;document.addEventListener('keydown',key);
      const render=(now:number)=>{
        const elapsed=now-start;const t=reduced?3900:elapsed;const approach=Math.min(1,t/2900);const impact=Math.max(0,Math.min(1,(t-3100)/700));
        const escape=Math.max(0,Math.min(1,(t-5100)/1800));
        root.dataset.beat=t>=5100?'escape':t>=3800?'fallen':t>=2900?'strike':'approach';
        const variant=strikeVariant(edition.day); const lunging=t>2900&&t<3500;
        if (!reduced) {
          const footfall=Math.floor(approach*378/42);
          if(t<2900 && footfall>lastFootfall){gameAudio.effect('step');lastFootfall=footfall;}
          if(t>=2900&&!slashed){gameAudio.effect('slash',variant);slashed=true;}
          if(t>=3100&&!hit){gameAudio.effect('impact',variant);hit=true;}
          if(t>=3100&&!howled){gameAudio.effect('howl');howled=true;}
          const escapeFootfall=Math.floor(escape*600/42);
          if(escape>0 && escapeFootfall>lastEscapeFootfall){gameAudio.effect('step');lastEscapeFootfall=escapeFootfall;}
        }
        ctx.clearRect(0,0,960,360);ctx.imageSmoothingEnabled=false;
        ctx.save();ctx.filter=reduced?'none':`blur(${approach*2}px)`;ctx.drawImage(bg,0,0,960,360);
        Object.keys(pedestrians.frames).filter(f=>f.endsWith('-0')).slice(0,2).forEach((frame,i)=>{ctx.filter=`blur(${reduced?0:3+approach*5}px)`;for(let trail=0;trail<3;trail++)drawActor(pedestrians,frame,90+i*765+trail*6,308,60,86,0,1/(trail+1));});
        extras.forEach((a,i)=>{ctx.filter=`blur(${reduced?0:3+approach*5}px)`;for(let trail=0;trail<3;trail++)drawActor(a,'0',180+i*290+trail*5,306,64,91,0,1/(trail+1));});
        ctx.restore();ctx.fillStyle=`rgba(2,7,17,${.18+approach*.48})`;ctx.fillRect(0,0,960,360);
        const light=ctx.createRadialGradient(590,245,12,590,245,190);light.addColorStop(0,'rgba(196,215,240,.20)');light.addColorStop(1,'rgba(196,215,240,0)');ctx.fillStyle=light;ctx.fillRect(0,0,960,360);
        const wx=140+approach*378+(lunging?Math.sin((t-2900)/600*Math.PI)*(variant===2?52:35):0);
        const lift=lunging?(variant===3?-Math.sin((t-2900)/600*Math.PI)*62:variant===2?16:-8):0;
        if(t<3800 || !fallen) drawActor(victim,'0',620+impact*22,307,72,101,impact*1.35,1-impact*.9);
        else {
          const [x,y,right,bottom]=fallen.bbox;const width=right-x;const height=bottom-y;
          ctx.drawImage(fallen.image,x,y,width,height,590,310-112*height/width,112,112*height/width);
        }
        if(t<2900) {
          const walkFrame=wolfWalkFrame(approach*378);
          root.dataset.wolfWalkFrame=walkFrame;
          drawActor(wolfWalking,walkFrame,wx,307,125,130);
        } else if(escape>0) drawActor(wolfWalking,wolfWalkFrame(escape*600),518+escape*600,307,125,130);
        else drawActor(wolf,t>=3900?'3':variant===1?'2':variant===2?'0':variant===3?'3':'1',wx,314+lift,125,145,lunging?(variant-1.5)*.12:0);
        if(lunging&&!reduced) drawPixelClaws(ctx,variant,(t-2900)/600);
        if(t>5100)root.querySelector('[role=status]')!.textContent='O lobisomem foge pelas sombras. A vítima permanece imóvel.';
        else if(t>3800)root.querySelector('[role=status]')!.textContent='O silêncio retorna. O Clarim trará a notícia ao amanhecer.';
        if(reduced?elapsed>=1200:t>=7300){finish();return;}raf=requestAnimationFrame(render);
      };render(start);
    });
  } catch {root.remove();} finally {gameAudio.stopCinematicEffects();gameAudio.setNight(false);clearTimeout(loadTimeout);if(cancel)cancel=undefined;abort.abort();}
}
