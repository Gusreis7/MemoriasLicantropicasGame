import Phaser from 'phaser';
import type {CasePublic, CharacterAsset, CharacterManifest, Direction, Location, LocationID, WorldSnapshot} from '../shared/api';

interface SceneHooks {
  frame: (delta: number, direction: Direction) => {x: number; facing: 'left' | 'right'};
  approach: () => void;
  inspect?: (crimeID: string) => void;
  map: () => void;
  blocked: () => boolean;
  loaded: () => void;
  failed: () => void;
}

type AmbientFrame = 'tree' | 'dog' | 'cat' | 'bird' | 'citizen-man' | 'citizen-woman';
interface AmbientPlacement {frame: AmbientFrame; x: number; y: number; width: number; height: number; drift?: number}
const AMBIENT: Record<LocationID, AmbientPlacement[]> = {
  praca_verde: [
    {frame: 'tree', x: 90, y: 279, width: 132, height: 170}, {frame: 'tree', x: 820, y: 285, width: 124, height: 158},
    {frame: 'citizen-woman', x: 665, y: 294, width: 48, height: 76}, {frame: 'dog', x: 275, y: 307, width: 45, height: 31, drift: 12},
    {frame: 'cat', x: 750, y: 303, width: 32, height: 26}, {frame: 'bird', x: 355, y: 115, width: 18, height: 16, drift: 24},
  ],
  cabana_capitu: [
    {frame: 'tree', x: 105, y: 286, width: 134, height: 176}, {frame: 'tree', x: 790, y: 278, width: 115, height: 150},
    {frame: 'citizen-man', x: 610, y: 295, width: 47, height: 76}, {frame: 'cat', x: 250, y: 306, width: 34, height: 27, drift: 8},
    {frame: 'bird', x: 670, y: 110, width: 17, height: 15, drift: 22},
  ],
  casa_verde: [
    {frame: 'tree', x: 115, y: 285, width: 132, height: 166}, {frame: 'tree', x: 845, y: 282, width: 120, height: 154},
    {frame: 'citizen-woman', x: 680, y: 293, width: 47, height: 76}, {frame: 'dog', x: 275, y: 305, width: 45, height: 30},
    {frame: 'bird', x: 615, y: 105, width: 18, height: 16, drift: 26},
  ],
  cafe_largo: [
    {frame: 'tree', x: 115, y: 280, width: 120, height: 156}, {frame: 'citizen-man', x: 670, y: 292, width: 48, height: 76},
    {frame: 'citizen-woman', x: 730, y: 294, width: 47, height: 75}, {frame: 'dog', x: 280, y: 306, width: 44, height: 30, drift: 10},
    {frame: 'cat', x: 805, y: 307, width: 33, height: 27}, {frame: 'bird', x: 550, y: 120, width: 18, height: 16, drift: 18},
  ],
  cais_lanternas: [
    // Keep the gas lamp on the left readable; the backdrop already has a tree behind it.
    {frame: 'citizen-man', x: 700, y: 293, width: 48, height: 76},
    {frame: 'cat', x: 320, y: 306, width: 34, height: 27, drift: 8}, {frame: 'dog', x: 785, y: 307, width: 44, height: 30},
    {frame: 'bird', x: 610, y: 118, width: 18, height: 16, drift: 30}, {frame: 'bird', x: 765, y: 85, width: 17, height: 15, drift: 26},
  ],
};

export class CityScene extends Phaser.Scene {
  private player?: Phaser.GameObjects.Sprite;
  private npcs: Phaser.GameObjects.GameObject[] = [];
  private ambient: Phaser.GameObjects.GameObject[] = [];
  private wanderers: Array<{image: Phaser.GameObjects.Image; placement: AmbientPlacement}> = [];
  private background?: Phaser.GameObjects.Image;
  private currentLocation = '';
  private cursors?: Phaser.Types.Input.Keyboard.CursorKeys;
  private keys?: Record<string, Phaser.Input.Keyboard.Key>;
  private assets = new Map<string, CharacterAsset>();
  private currentWorld: WorldSnapshot;
  private ready = false;
  private assetsFailed = false;
  private selected?: Phaser.GameObjects.Ellipse;
  private caseState: CasePublic | null = null;
  private caseMarkers: Phaser.GameObjects.GameObject[] = [];
  private npcSignature = '';
  private touchDirection: Direction = 'idle';
  private reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

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
    this.load.atlas('scene-life', '/assets/ambient/scene-life.png', '/assets/ambient/scene-life.json');
    this.load.atlas('capoeira', '/assets/ambient/capoeira.png', '/assets/ambient/capoeira.json');
    this.load.atlas('clarim', '/assets/ambient/clarim.png', '/assets/ambient/clarim.json');
    this.load.on('loaderror', () => {this.assetsFailed = true; this.hooks.failed();});
  }

  create() {
    for (const asset of this.manifest.characters) {
      if (this.textures.exists(asset.id)) this.textures.get(asset.id).setFilter(Phaser.Textures.FilterMode.NEAREST);
      if (asset.id === 'player' && asset.walkFrames.length) {
        this.anims.create({key: 'player-walk', frames: asset.walkFrames.map(frame => ({key: asset.id, frame})), frameRate: 7, repeat: -1});
      }
    }
    this.cursors = this.input.keyboard?.createCursorKeys();
    this.keys = this.input.keyboard?.addKeys('A,D,E,M') as Record<string, Phaser.Input.Keyboard.Key>;
    this.input.keyboard?.on('keydown-E', () => {
      if (this.hooks.blocked()) return;
      const crime = this.caseState?.crimes.find(crime => crime.location_id === this.currentLocation
        && crime.remaining_clues > 0 && this.player && Math.abs(crime.x - this.player.x) <= 90);
      if (crime && this.hooks.inspect) this.hooks.inspect(crime.id);
      else this.hooks.approach();
    });
    this.input.keyboard?.on('keydown-M', () => { if (!this.hooks.blocked()) this.hooks.map(); });
    this.game.events.on(Phaser.Core.Events.BLUR, () => { this.input.keyboard?.resetKeys(); this.touchDirection = 'idle'; });
    this.cameras.main.setRoundPixels(true);
    this.cameras.main.setBackgroundColor('#163b32');
    if (this.textures.exists('capoeira') && !this.anims.exists('capoeira-roda')) {
      this.textures.get('capoeira').setFilter(Phaser.Textures.FilterMode.NEAREST);
      this.anims.create({key: 'capoeira-roda', frames: ['0', '1', '2', '3'].map(frame => ({key: 'capoeira', frame})), frameRate: 3, repeat: -1});
    }
    this.ready = true;
    this.apply(this.currentWorld);
    if (this.assetsFailed) this.hooks.failed();
    else this.hooks.loaded();
  }

  private sprite(id: string, x: number, y: number) {
    const asset = this.assets.get(id);
    if (!asset || !this.textures.exists(id)) { this.assetsFailed = true; this.hooks.failed(); return undefined; }
    const sprite = this.add.sprite(Math.round(x), y, id, asset.frameNames?.[0] ?? 0);
    sprite.setOrigin(asset.origin.x, asset.origin.y).setDisplaySize(asset.displayWidth, asset.displayHeight);
    return sprite;
  }

  setTouchDirection(direction: Direction) { this.touchDirection = direction; }

  setInputEnabled(enabled: boolean) {
    this.touchDirection = 'idle';
    if (!this.input?.keyboard) return;
    this.input.keyboard.resetKeys();
    this.input.keyboard.enabled = enabled;
    if (enabled) this.input.keyboard.enableGlobalCapture();
    else this.input.keyboard.disableGlobalCapture();
  }

  private dressLocation(id: LocationID, groundY: number) {
    this.ambient.forEach(object => object.destroy()); this.ambient = []; this.wanderers = [];
    if (!this.textures.exists('scene-life')) return;
    this.textures.get('scene-life').setFilter(Phaser.Textures.FilterMode.NEAREST);
    for (const placement of AMBIENT[id]) {
      const image = this.add.image(placement.x, placement.y, 'scene-life', placement.frame)
        .setOrigin(.5, 1).setDepth(placement.frame === 'tree' ? -3 : -1);
      // Fit each atlas cutout inside its box without stretching its natural silhouette.
      image.setScale(Math.min(placement.width / image.width, placement.height / image.height));
      this.ambient.push(image);
      if (placement.drift && !this.reducedMotion) this.wanderers.push({image, placement});
    }
    if (id === 'cais_lanternas' && this.textures.exists('capoeira')) {
      // The atlas feet baseline is y=480 in a 512px frame. Place that baseline
      // on the walkable pavement, at the same ground_y as every person sprite.
      const roda = this.add.sprite(440, groundY, 'capoeira', '0').setOrigin(.5, 480 / 512).setDepth(-2);
      roda.setDisplaySize(168, 112);
      if (!this.reducedMotion) roda.play('capoeira-roda');
      this.ambient.push(roda);
    }
    if (id === 'praca_verde' && this.textures.exists('clarim')) {
      const banca = this.add.image(160, 284, 'clarim', 'stand').setOrigin(.5, 1)
        .setDisplaySize(136, 132).setDepth(-2);
      this.ambient.push(banca);
    }
  }

  setInvestigation(state: CasePublic) {
    this.caseState = state;
    if (this.ready) this.drawCaseMarkers();
  }

  private drawCaseMarkers() {
    this.caseMarkers.forEach(marker => marker.destroy()); this.caseMarkers = [];
    if (this.currentLocation === 'praca_verde') {
      this.caseMarkers.push(this.add.text(160, 143, 'O CLARIM DO RIO', {fontFamily: 'Georgia, serif', fontSize: '10px',
        color: '#183c32', backgroundColor: '#f2e7c8ee', padding: {x: 7, y: 5}}).setOrigin(.5).setDepth(4));
    }
    const crimes = this.caseState?.crimes.filter(crime => crime.location_id === this.currentLocation && crime.remaining_clues > 0) ?? [];
    for (const x of new Set(crimes.map(crime => crime.x))) {
      const count = crimes.filter(crime => crime.x === x).length;
      this.caseMarkers.push(this.add.ellipse(x, 301, 55, 12, 0xd9ba79, .18).setStrokeStyle(1, 0xe5c886).setDepth(2));
      this.caseMarkers.push(this.add.text(x, 315, count === 1 ? 'Cena do crime' : `${count} cenas · vestígios`, {
        fontFamily: 'Georgia, serif', fontSize: '10px', color: '#fff0c4', backgroundColor: '#1b342cdd', padding: {x: 5, y: 3},
      }).setOrigin(.5, 0).setDepth(4));
    }
  }

  apply(world: WorldSnapshot) {
    this.currentWorld = world;
    if (!this.ready) return;
    // The backdrop and decorations are built once per location, never per movement snapshot.
    if (world.location.id !== this.currentLocation) {
      this.currentLocation = world.location.id;
      this.background?.destroy();
      this.background = this.add.image(0, 0, `location-${world.location.id}`).setOrigin(0)
        .setDisplaySize(world.location.width, world.location.height).setDepth(-10).setScrollFactor(0);
      this.dressLocation(world.location.id, world.location.ground_y);
      this.npcSignature = '\0';
      this.drawCaseMarkers();
      if (!this.player) {
        this.add.ellipse(world.player.x, world.location.ground_y + 1, 34, 7, 0x173e31, .3).setName('player-shadow').setDepth(2);
        this.player = this.sprite('player', world.player.x, world.location.ground_y);
        this.selected = this.add.ellipse(0, world.location.ground_y + 2, 43, 11).setStrokeStyle(1, 0xf9d18b, .9).setVisible(false).setDepth(2);
      }
      this.player?.setPosition(Math.round(world.player.x), world.location.ground_y).setDepth(3);
      this.cameras.main.stopFollow();
      this.cameras.main.setBounds(0, 0, world.location.width, world.location.height);
      this.cameras.main.setScroll(0, 0);
    }
    const signature = world.visible_npcs.map(npc => `${npc.npc_id}:${npc.x}:${npc.name}`).join('|');
    if (signature !== this.npcSignature) {
      this.npcSignature = signature;
      this.npcs.forEach(npc => npc.destroy()); this.npcs = [];
      for (const npc of world.visible_npcs) {
        const shadow = this.add.ellipse(npc.x, world.location.ground_y + 1, 34, 7, 0x173e31, .3);
        const sprite = this.sprite(npc.sprite_id, npc.x, world.location.ground_y);
        if (sprite) this.npcs.push(sprite);
        this.npcs.push(shadow);
        const label = this.add.text(npc.x, world.location.ground_y - 96, npc.name, {fontFamily: 'Georgia, serif', fontSize: '11px', color: '#fff4d2', backgroundColor: '#183c33cc', padding: {x: 5, y: 3}}).setOrigin(.5, 1).setDepth(4);
        this.npcs.push(label);
      }
      this.addExitSigns(world);
    }
  }

  private addExitSigns(world: WorldSnapshot) {
    for (const side of ['left', 'right'] as const) {
      const count = world.location.exits.filter(exit => exit.side === side).length;
      if (!count) continue;
      const label = this.add.text(side === 'left' ? 16 : world.location.width - 16, 178,
        side === 'left' ? '‹ Caminhos' : 'Caminhos ›', {fontFamily: 'Georgia, serif', fontSize: '11px', color: '#fff2ce', backgroundColor: '#173b32bb', padding: {x: 6, y: 5}})
        .setOrigin(side === 'left' ? 0 : 1, .5).setDepth(4);
      this.npcs.push(label);
    }
  }

  update(time: number, delta: number) {
    const blocked = this.hooks.blocked();
    let direction: Direction = 'idle';
    if (!blocked) {
      const left = this.cursors?.left.isDown || this.keys?.A.isDown || this.touchDirection === 'left';
      const right = this.cursors?.right.isDown || this.keys?.D.isDown || this.touchDirection === 'right';
      direction = left && !right ? 'left' : right && !left ? 'right' : 'idle';
    }
    const position = this.hooks.frame(delta, direction);
    if (this.player) {
      this.player.x = Math.round(position.x);
      this.player.setFlipX(position.facing === 'left');
      if (direction === 'idle') {
        this.player.anims.stop();
        this.player.setFrame(this.assets.get('player')?.frameNames?.[0] ?? 0);
      } else if (this.anims.exists('player-walk')) this.player.anims.play('player-walk', true);
      const shadow = this.children.getByName('player-shadow') as Phaser.GameObjects.Ellipse | null;
      if (shadow) shadow.x = Math.round(position.x);
    }
    for (const {image, placement} of this.wanderers) {
      image.x = Math.round(placement.x + Math.sin(time / 1600 + placement.x) * (placement.drift ?? 0));
      if (placement.frame === 'bird') image.y = Math.round(placement.y + Math.sin(time / 900 + placement.x) * 4);
    }
    const nearest = this.currentWorld.visible_npcs.find(npc => Math.abs(npc.x - position.x) <= 64);
    this.selected?.setVisible(Boolean(nearest) && !blocked);
    if (nearest) this.selected?.setX(nearest.x);
  }
}

export function makeGame(parent: HTMLElement, scene: CityScene) {
  return new Phaser.Game({
    type: Phaser.AUTO, parent, width: 960, height: 360,
    backgroundColor: '#163b32', render: {pixelArt: true, roundPixels: true, clearBeforeRender: true, preserveDrawingBuffer: false},
    scale: {mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH},
    input: {keyboard: {capture: []}}, scene: [scene],
    audio: {noAudio: true},
  });
}
