import Phaser from 'phaser';
import type {CharacterAsset} from '../shared/api';
import {custodyPacing,CELL_PACING} from './custody-pacing';
export type CustodyMode = 'waiting' | 'night' | 'transformed' | 'released';
export type AdmissionStage = 'entering' | 'closing' | 'held';

export class CustodyScene extends Phaser.Scene {
  private human?: Phaser.GameObjects.Sprite;
  private wolf?: Phaser.GameObjects.Sprite;
  private gate?: Phaser.GameObjects.Container;
  private ready = false;
  private finishTimer?: ReturnType<typeof setTimeout>;
  private admissionTimers: Array<ReturnType<typeof setTimeout>> = [];
  private admissionPending = false;
  private pacing = false;
  private pacingElapsed = 0;
  private mode: CustodyMode = 'waiting';
  private done?: () => void;
  private reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  constructor(private character: CharacterAsset, private onAdmissionStage?: (stage:AdmissionStage)=>void) {super('custody');}
  preload() {
    this.load.image('jail-room','/assets/cinematics/jail.png');
    this.load.image('delegate-at-desk','/assets/custody/delegado-sentado.png');
    this.load.atlas('detainee',this.character.path,this.character.atlasPath!);
    this.load.atlas('wolf-reveal','/assets/cinematics/werewolf.png','/assets/cinematics/werewolf.json');
  }
  create() {
    this.add.image(480,270,'jail-room').setDisplaySize(960,540);
    // The cell is the central architectural opening. Both forms share its floor.
    this.human=this.add.sprite(480,370,'detainee',this.character.frameNames?.[0] ?? 0)
      .setName(`detainee-${this.character.id}`)
      .setOrigin(this.character.origin.x,this.character.origin.y).setDisplaySize(120,190);
    this.wolf=this.add.sprite(480,370,'wolf-reveal','0').setName('feral-werewolf')
      .setOrigin(.5,684/724).setDisplaySize(205,225).setVisible(false);
    this.anims.create({key:'detainee-walk',frames:this.character.walkFrames.map(frame=>({key:'detainee',frame})),frameRate:7,repeat:-1});
    this.anims.create({key:'wolf-breathe',frames:['0','1','2','3'].map(frame=>({key:'wolf-reveal',frame})),frameRate:4,repeat:-1});
    this.gate=this.add.container(0,0).setDepth(5);
    for (let x=324;x<=636;x+=26) {
      this.gate.add(this.add.rectangle(x,210,9,328,0x211d1a).setName('gate-bar').setStrokeStyle(1,0x171513));
      this.gate.add(this.add.rectangle(x-2,210,2,326,0x98744c).setName('gate-bar-sheen'));
    }
    this.gate.add([
      this.add.rectangle(480,46,318,12,0x30251d).setName('gate-rail').setStrokeStyle(2,0x98744c),
      this.add.rectangle(480,374,318,12,0x30251d).setName('gate-rail').setStrokeStyle(2,0x98744c),
    ]);
    // The delegate sits in the foreground of the desk, with the complete chair
    // and shoes visible. The source is 2:3, so 150x225 keeps a human scale in
    // the 960x540 room. Keep him on the floor in front of the desk artwork.
    this.add.image(145,435,'delegate-at-desk').setName('delegate-at-desk')
      .setOrigin(.5,1).setDisplaySize(150,225).setDepth(4);
    this.events.once(Phaser.Scenes.Events.SHUTDOWN,()=>this.clearTimers());
    this.events.once(Phaser.Scenes.Events.DESTROY,()=>this.clearTimers());
    this.ready=true;this.applyMode();
  }
  setMode(mode:CustodyMode,done?:()=>void,admit=false) {
    if(this.mode===mode && this.ready && !admit) {if(done)done();return;}
    this.admissionPending=admit && mode==='waiting';
    this.mode=mode;this.done=done;if(this.ready)this.applyMode();
  }
  private applyMode() {
    if(!this.human || !this.wolf || !this.gate)return;
    this.clearTimers();
    this.pacing=false;this.pacingElapsed=0;
    this.tweens.killTweensOf([this.human,this.wolf,this.gate]);
    // A server phase change interrupts admission safely, with the person in custody.
    this.human.setPosition(480,370).setAlpha(1).stop().setFrame(this.character.frameNames?.[0] ?? 0);
    this.wolf.setVisible(false);this.gate.setX(0);
    if(this.mode==='waiting' || this.mode==='night') {
      if(this.admissionPending && !this.reduced) this.admit();
      else {this.onAdmissionStage?.('held');this.pacing=!this.reduced;}
      this.admissionPending=false;
    } else if(this.mode==='transformed') {
      // This mode is entered only after the server has confirmed the transformation.
      // Show its first visible pose immediately rather than leaving a two-second gap.
      this.wolf.setVisible(true).setAlpha(this.reduced?1:.3);
      if(!this.reduced)this.wolf.play('wolf-breathe');
      this.tweens.add({targets:this.human,alpha:0,duration:this.reduced?0:450});
      this.tweens.add({targets:this.wolf,alpha:1,duration:this.reduced?0:650});
      this.finishTimer=setTimeout(()=>this.done?.(),this.reduced?150:1500);
    } else if(this.mode==='released') {
      this.tweens.add({targets:this.gate,x:330,duration:this.reduced?0:800});
      if(!this.reduced)this.human.play('detainee-walk');
      this.tweens.add({targets:this.human,y:448,delay:this.reduced?0:650,duration:this.reduced?0:400});
      this.tweens.add({targets:this.human,x:1050,delay:this.reduced?0:1050,duration:this.reduced?0:1300});
      this.finishTimer=setTimeout(()=>this.done?.(),this.reduced?150:2500);
    }
  }
  private clearTimers() {
    this.pacing=false;
    clearTimeout(this.finishTimer);
    this.admissionTimers.forEach(clearTimeout);this.admissionTimers=[];
  }
  update(_time:number,delta:number) {
    if(this.pacing && this.human && (this.mode==='waiting' || this.mode==='night')) {
      this.pacingElapsed+=Math.min(Math.max(delta,0),100);
      const pose=custodyPacing(this.pacingElapsed);
      const frames=this.character.walkFrames;
      this.human.setPosition(Math.round(pose.x),CELL_PACING.ground).setFlipX(pose.facing==='left').stop();
      if(frames.length)this.human.setFrame(frames[Math.floor(pose.distance/12)%frames.length]);
    }
    if(!this.gate)return;
    // Clip the native shapes to the doorway in both Canvas and WebGL.
    // Offscreen bars slide behind the wall; rails shorten at the right jamb.
    const offset=this.gate.x;
    for(const child of this.gate.list as Phaser.GameObjects.Rectangle[]) {
      if(child.name==='gate-bar' || child.name==='gate-bar-sheen')child.setVisible(child.x+offset<=639);
      else {
        const width=Math.max(0,318-offset);
        child.setVisible(width>0).setX(480-offset/2).setDisplaySize(Math.max(1,width),10);
      }
    }
  }
  private admit() {
    const human=this.human!,gate=this.gate!;
    gate.setX(330);human.setPosition(245,448).setFlipX(false).play('detainee-walk');
    this.onAdmissionStage?.('entering');
    // Walk across the clear foreground, then through the open doorway.
    this.tweens.add({targets:human,x:480,duration:900,ease:'Linear'});
    this.tweens.add({targets:human,y:370,delay:900,duration:650,ease:'Linear'});
    this.tweens.add({targets:gate,x:0,delay:1550,duration:600,ease:'Cubic.easeInOut'});
    this.admissionTimers.push(setTimeout(()=>{
      human.setPosition(480,370).stop().setFrame(this.character.frameNames?.[0] ?? 0);
      this.onAdmissionStage?.('closing');
    },1550));
    this.admissionTimers.push(setTimeout(()=>{
      this.tweens.killTweensOf([human,gate]);gate.setX(0);
      this.pacingElapsed=0;this.pacing=!this.reduced;
      this.onAdmissionStage?.('held');
    },2250));
  }
}
export function makeCustodyGame(parent:HTMLElement,scene:CustodyScene) {
  return new Phaser.Game({type:Phaser.AUTO,parent,width:960,height:540,scene:[scene],audio:{noAudio:true},
    input:{keyboard:false},render:{pixelArt:true,roundPixels:true},scale:{mode:Phaser.Scale.FIT,autoCenter:Phaser.Scale.CENTER_BOTH}});
}
