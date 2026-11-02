import Phaser from 'phaser';
import type {CharacterAsset} from '../shared/api';
export type CustodyMode = 'waiting' | 'night' | 'transformed' | 'released';

export class CustodyScene extends Phaser.Scene {
  private human?: Phaser.GameObjects.Sprite;
  private wolf?: Phaser.GameObjects.Sprite;
  private gate?: Phaser.GameObjects.Container;
  private ready = false;
  private finishTimer?: ReturnType<typeof setTimeout>;
  private mode: CustodyMode = 'waiting';
  private done?: () => void;
  private reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  constructor(private character: CharacterAsset) {super('custody');}
  preload() {
    this.load.image('jail-room','/assets/cinematics/jail.png');
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
    for (let x=324;x<=636;x+=26) this.gate.add(this.add.rectangle(x,210,6,328,0x253735).setStrokeStyle(1,0x819080));
    this.gate.add([this.add.rectangle(480,46,318,10,0x34463d),this.add.rectangle(480,374,318,10,0x34463d)]);
    this.events.once(Phaser.Scenes.Events.SHUTDOWN,()=>{clearTimeout(this.finishTimer);});
    this.events.once(Phaser.Scenes.Events.DESTROY,()=>{clearTimeout(this.finishTimer);});
    this.ready=true;this.applyMode();
  }
  setMode(mode:CustodyMode,done?:()=>void) {
    if(this.mode===mode && this.ready) {if(done)done();return;}
    this.mode=mode;this.done=done;if(this.ready)this.applyMode();
  }
  private applyMode() {
    if(!this.human || !this.wolf || !this.gate)return;
    if(this.mode==='waiting' || this.mode==='night') {
      this.human.setPosition(480,370).setAlpha(1).stop().setFrame(this.character.frameNames?.[0] ?? 0);
      this.wolf.setVisible(false);this.gate.setX(0);
    } else if(this.mode==='transformed') {
      this.wolf.setVisible(true).setAlpha(this.reduced?1:0);
      if(!this.reduced)this.wolf.play('wolf-breathe');
      this.tweens.add({targets:this.human,alpha:0,duration:this.reduced?0:1300});
      this.tweens.add({targets:this.wolf,alpha:1,duration:this.reduced?0:1800});
      this.finishTimer=setTimeout(()=>this.done?.(),this.reduced?150:3400);
    } else if(this.mode==='released') {
      this.tweens.add({targets:this.gate,x:330,duration:this.reduced?0:800});
      if(!this.reduced)this.human.play('detainee-walk');
      this.tweens.add({targets:this.human,y:448,delay:this.reduced?0:650,duration:this.reduced?0:400});
      this.tweens.add({targets:this.human,x:1050,delay:this.reduced?0:1050,duration:this.reduced?0:1300});
      this.finishTimer=setTimeout(()=>this.done?.(),this.reduced?150:2500);
    }
  }
}
export function makeCustodyGame(parent:HTMLElement,scene:CustodyScene) {
  return new Phaser.Game({type:Phaser.AUTO,parent,width:960,height:540,scene:[scene],audio:{noAudio:true},
    input:{keyboard:false},render:{pixelArt:true,roundPixels:true},scale:{mode:Phaser.Scale.FIT,autoCenter:Phaser.Scale.CENTER_BOTH}});
}
