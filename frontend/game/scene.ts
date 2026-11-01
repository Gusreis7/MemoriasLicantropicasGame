import Phaser from 'phaser';
import type {CharacterAsset, CharacterManifest, Direction, Location, WorldSnapshot} from '../shared/api';

interface SceneHooks {
  frame: (delta: number, direction: Direction) => {x: number; facing: 'left' | 'right'};
  approach: () => void;
  map: () => void;
  blocked: () => boolean;
  loaded: () => void;
  failed: () => void;
}

export class CityScene extends Phaser.Scene {
  private player?: Phaser.GameObjects.Sprite;
  private npcs: Phaser.GameObjects.GameObject[] = [];
  private background?: Phaser.GameObjects.Image;
  private currentLocation = '';
  private cursors?: Phaser.Types.Input.Keyboard.CursorKeys;
  private keys?: Record<string, Phaser.Input.Keyboard.Key>;
  private assets = new Map<string, CharacterAsset>();
  private currentWorld: WorldSnapshot;
  private ready = false;
  private assetsFailed = false;
  private selected?: Phaser.GameObjects.Ellipse;

  constructor(private manifest: CharacterManifest, private locations: Location[], world: WorldSnapshot, private hooks: SceneHooks) {
    super({key: 'city'});
    this.currentWorld = world;
    manifest.characters.forEach(asset => this.assets.set(asset.id, asset));
  }

  preload() {
    for (const asset of this.manifest.characters) {
      if (asset.type === 'atlas' && asset.atlasPath) this.load.atlas(asset.id, asset.path, asset.atlasPath);
      else if (asset.type === 'image') this.load.image(asset.id, asset.path);
      else this.load.spritesheet(asset.id, asset.path, {frameWidth: asset.frameWidth, frameHeight: asset.frameHeight});
    }
    for (const location of this.locations) this.load.image(`location-${location.id}`, location.background);
    this.load.on('loaderror', () => {this.assetsFailed = true; this.hooks.failed();});
  }

  create() {
    for (const asset of this.manifest.characters) {
      for (const [name, frames, speed] of [['idle', asset.idleFrames, 2], ['walk', asset.walkFrames, 8]] as const) {
        if (frames?.length) this.anims.create({key: `${asset.id}-${name}`, frames: frames.map(frame => ({key: asset.id, frame})), frameRate: speed, repeat: -1});
      }
    }
    this.cursors = this.input.keyboard?.createCursorKeys();
    this.keys = this.input.keyboard?.addKeys('A,D,E,M') as Record<string, Phaser.Input.Keyboard.Key>;
    this.input.keyboard?.on('keydown-E', () => { if (!this.hooks.blocked()) this.hooks.approach(); });
    this.input.keyboard?.on('keydown-M', () => { if (!this.hooks.blocked()) this.hooks.map(); });
    this.game.events.on(Phaser.Core.Events.BLUR, () => { this.input.keyboard?.resetKeys(); });
    this.ready = true;
    this.apply(this.currentWorld);
    if (this.assetsFailed) this.hooks.failed();
    else this.hooks.loaded();
  }

  private sprite(id: string, x: number, y: number) {
    const asset = this.assets.get(id);
    if (!asset || !this.textures.exists(id)) { this.assetsFailed = true; this.hooks.failed(); return undefined; }
    const sprite = this.add.sprite(x, y, id, asset.frameNames?.[0] ?? 0);
    sprite.setOrigin(asset.origin.x, asset.origin.y).setDisplaySize(asset.displayWidth, asset.displayHeight);
    if (this.anims.exists(`${id}-idle`)) sprite.play(`${id}-idle`);
    return sprite;
  }

  setInputEnabled(enabled: boolean) {
    if (!this.input?.keyboard) return;
    this.input.keyboard.resetKeys();
    this.input.keyboard.enabled = enabled;
    if (enabled) this.input.keyboard.enableGlobalCapture();
    else this.input.keyboard.disableGlobalCapture();
  }

  apply(world: WorldSnapshot) {
    this.currentWorld = world;
    if (!this.ready) return;
    if (world.location.id !== this.currentLocation) {
      this.currentLocation = world.location.id;
      this.background?.destroy();
      this.background = this.add.image(0, 0, `location-${world.location.id}`).setOrigin(0).setDisplaySize(world.location.width, world.location.height).setDepth(-10);
      this.npcs.forEach(npc => npc.destroy());
      this.npcs = [];
      for (const npc of world.visible_npcs) {
        const shadow = this.add.ellipse(npc.x, world.location.ground_y + 1, 30, 7, 0x173e31, .3);
        const sprite = this.sprite(npc.sprite_id, npc.x, world.location.ground_y);
        if (sprite) this.npcs.push(sprite);
        this.npcs.push(shadow);
        const label = this.add.text(npc.x, world.location.ground_y - 72, npc.name, {fontFamily: 'Georgia, serif', fontSize: '10px', color: '#fff4d2', backgroundColor: '#183c33cc', padding: {x: 5, y: 3}}).setOrigin(.5, 1);
        this.npcs.push(label);
      }
      if (!this.player) {
        this.add.ellipse(world.player.x, world.location.ground_y + 1, 29, 7, 0x173e31, .3).setName('player-shadow');
        this.player = this.sprite('player', world.player.x, world.location.ground_y);
        this.selected = this.add.ellipse(0, world.location.ground_y + 2, 39, 11).setStrokeStyle(1, 0xf9d18b, .9).setVisible(false);
      }
      if (this.player) {
        this.player.setPosition(world.player.x, world.location.ground_y).setDepth(3);
        this.cameras.main.setBounds(0, 0, world.location.width, world.location.height);
        this.cameras.main.startFollow(this.player, true, .1, 1);
      }
    }
  }

  update(_time: number, delta: number) {
    const blocked = this.hooks.blocked();
    let direction: Direction = 'idle';
    if (!blocked) {
      const left = this.cursors?.left.isDown || this.keys?.A.isDown;
      const right = this.cursors?.right.isDown || this.keys?.D.isDown;
      direction = left && !right ? 'left' : right && !left ? 'right' : 'idle';
    }
    const position = this.hooks.frame(delta, direction);
    if (this.player) {
      this.player.x = position.x;
      this.player.setFlipX(position.facing === 'left');
      const animation = direction === 'idle' ? 'player-idle' : 'player-walk';
      if (this.anims.exists(animation)) this.player.anims.play(animation, true);
      const shadow = this.children.getByName('player-shadow') as Phaser.GameObjects.Ellipse | null;
      if (shadow) shadow.x = position.x;
    }
    const nearest = this.currentWorld.visible_npcs.find(npc => Math.abs(npc.x - position.x) <= 64);
    this.selected?.setVisible(Boolean(nearest) && !blocked);
    if (nearest) this.selected?.setX(nearest.x);
  }
}

export function makeGame(parent: HTMLElement, scene: CityScene) {
  return new Phaser.Game({
    type: Phaser.AUTO, parent, width: 640, height: 360,
    backgroundColor: '#163b32', render: {pixelArt: true, roundPixels: true},
    scale: {mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH},
    input: {keyboard: {capture: []}}, scene: [scene],
    audio: {noAudio: true},
  });
}
