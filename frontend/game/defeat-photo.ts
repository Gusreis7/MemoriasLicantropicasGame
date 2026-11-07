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
    ctx.filter='grayscale(1) brightness(.28) blur(2px)';ctx.drawImage(background,0,0,600,400);
    // An indistinct, warped shadow: no visible fur, face, claws or anatomy study.
    const f=atlas.frames['0'].frame;
    const height=235,width=285;
    ctx.filter='brightness(0) blur(9px)';ctx.globalAlpha=.85;
    for(let y=0;y<height;y+=10) {
      const band=Math.min(10,height-y);
      const warp=Math.sin(y*.041)*16+Math.sin(y*.093)*7;
      const spread=1+Math.sin(y*.023)*.12;
      ctx.drawImage(wolf,f.x,f.y+y/height*f.h,f.w,band/height*f.h,
        300-width*spread/2+warp,137+y,width*spread,band+2);
    }
    ctx.globalAlpha=1;
    ctx.filter='none';
    const shade=ctx.createRadialGradient(300,210,65,300,210,350);
    shade.addColorStop(0,'rgba(2,7,17,.24)');shade.addColorStop(1,'rgba(2,7,17,.9)');
    ctx.fillStyle=shade;ctx.fillRect(0,0,600,400);
    target.src=canvas.toDataURL('image/png');
    await target.decode();
    if(!signal.aborted)target.dataset.loaded='true';
  } catch { /* A missing illustration must not block the final edition. */ }
}
