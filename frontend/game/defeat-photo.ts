import type {LocationID} from '../shared/api';

/** Reuse the public monster and moonlit location, never a suspect's identity. */
export async function renderDefeatPhoto(target:HTMLImageElement,location:LocationID,signal:AbortSignal) {
  const canvas=document.createElement('canvas');canvas.width=600;canvas.height=400;
  const ctx=canvas.getContext('2d');if(!ctx)return;
  ctx.fillStyle='#080e16';ctx.fillRect(0,0,canvas.width,canvas.height);
  const load=(path:string)=>new Promise<HTMLImageElement>((resolve,reject)=>{
    const img=new Image();img.onload=()=>resolve(img);img.onerror=reject;
    signal.addEventListener('abort',()=>{img.src='';reject(new Error('Cancelado'));},{once:true});img.src=path;
  });
  try {
    const [background,wolf,atlas]=await Promise.all([
      load(`/assets/locations/${location}-00h.png`),load('/assets/cinematics/werewolf.png'),
      fetch('/assets/cinematics/werewolf.json',{signal}).then(r=>{if(!r.ok)throw new Error('Atlas indisponível');return r.json();}),
    ]);
    if(signal.aborted)return;
    ctx.imageSmoothingEnabled=false;
    ctx.filter='grayscale(1) brightness(.5)';ctx.drawImage(background,0,0,600,400);
    // Same feral artwork as the custody reveal, with readable newspaper shading.
    const f=atlas.frames['2'].frame;
    const height=300,width=height*f.w/f.h;
    ctx.filter='grayscale(1) brightness(.82) contrast(1.08)';
    ctx.drawImage(wolf,f.x,f.y,f.w,f.h,300-width/2,78,width,height);
    ctx.filter='none';
    const shade=ctx.createRadialGradient(300,210,65,300,210,350);
    shade.addColorStop(0,'rgba(2,7,17,0)');shade.addColorStop(1,'rgba(2,7,17,.55)');
    ctx.fillStyle=shade;ctx.fillRect(0,0,600,400);
    target.src=canvas.toDataURL('image/png');
    await target.decode();
    if(!signal.aborted)target.dataset.loaded='true';
  } catch { /* A missing illustration must not block the final edition. */ }
}
