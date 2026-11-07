import Phaser from 'phaser';
import {assetURL} from '../shared/assets';
import type {CasePublic, CharacterAsset, CharacterManifest, Direction, Location, LocationID, WorldSnapshot} from '../shared/api';
import {POPULATION} from './population';
import {locationLighting, sunsetOpacity} from './daylight';
import {ambientResourceIDs, criticalCharacterIDs, lightingPeriod} from './scene-resources';

interface SceneHooks {
  frame: (delta: number, direction: Direction) => {x: number; facing: 'left' | 'right'};
  approach: () => void;
  inspect?: (crimeID: string) => void;
  map: () => void;
  blocked: () => boolean;
  loaded: () => void;
  failed: () => void;
  loading?: () => void;
  dayProgress?: () => number;
}

type AmbientFrame = 'tree' | 'dog' | 'cat' | 'bird';
interface AmbientPlacement {frame: AmbientFrame; x: number; y: number; width: number; height: number; drift?: number}
interface SceneResource {key: string; path: string; atlasPath?: string; character?: CharacterAsset; priority: number}
const AMBIENT: Record<LocationID, AmbientPlacement[]> = {
  praca_verde: [
    {frame: 'tree', x: 90, y: 279, width: 132, height: 170}, {frame: 'tree', x: 820, y: 285, width: 124, height: 158},
    {frame: 'dog', x: 275, y: 307, width: 45, height: 31, drift: 12},
    {frame: 'cat', x: 750, y: 303, width: 32, height: 26}, {frame: 'bird', x: 355, y: 115, width: 18, height: 16, drift: 24},
  ],
  cabana_capitu: [
    {frame: 'tree', x: 105, y: 286, width: 134, height: 176}, {frame: 'tree', x: 790, y: 278, width: 115, height: 150},
    {frame: 'cat', x: 250, y: 306, width: 34, height: 27, drift: 8},
    {frame: 'bird', x: 670, y: 110, width: 17, height: 15, drift: 22},
  ],
  casa_verde: [
    {frame: 'tree', x: 115, y: 285, width: 132, height: 166}, {frame: 'tree', x: 845, y: 282, width: 120, height: 154},
    {frame: 'dog', x: 275, y: 305, width: 45, height: 30},
    {frame: 'bird', x: 615, y: 105, width: 18, height: 16, drift: 26},
  ],
  cafe_largo: [
    {frame: 'tree', x: 115, y: 280, width: 120, height: 156}, {frame: 'dog', x: 280, y: 306, width: 44, height: 30, drift: 10},
    {frame: 'cat', x: 805, y: 307, width: 33, height: 27}, {frame: 'bird', x: 550, y: 120, width: 18, height: 16, drift: 18},
  ],
  cais_lanternas: [
    // Keep the gas lamp on the left readable; the backdrop already has a tree behind it.
    {frame: 'cat', x: 320, y: 306, width: 34, height: 27, drift: 8}, {frame: 'dog', x: 570, y: 307, width: 44, height: 30},
    {frame: 'bird', x: 610, y: 118, width: 18, height: 16, drift: 30}, {frame: 'bird', x: 765, y: 85, width: 17, height: 15, drift: 26},
  ],
};

export class CityScene extends Phaser.Scene {
  private player?: Phaser.GameObjects.Sprite;
  private npcs: Phaser.GameObjects.GameObject[] = [];
  private ambient: Phaser.GameObjects.GameObject[] = [];
  private wanderers: Array<{image: Phaser.GameObjects.Image | Phaser.GameObjects.Sprite; placement: AmbientPlacement}> = [];
  private background?: Phaser.GameObjects.Image;
  private sunsetBackground?: Phaser.GameObjects.Image;
  private midnightBackground?: Phaser.GameObjects.Image;
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
  private npcPositions = new Map<string, number>();
  private touchDirection: Direction = 'idle';
  loading = false;
  private queuedImages = new Set<string>();
  private resourceQueue: SceneResource[] = [];
  private activeResource: SceneResource | null = null;
  private resourceCooldown = false;
  private walking = false;
  private decorationSignature = '';
  private reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  constructor(private manifest: CharacterManifest, private locations: Location[], world: WorldSnapshot, private hooks: SceneHooks) {
    super({key: 'city'});
    this.currentWorld = world;
    manifest.characters.forEach(asset => this.assets.set(asset.id, asset));
  }

  preload() {
    const critical = criticalCharacterIDs(this.currentWorld);
    for (const asset of this.manifest.characters.filter(asset => critical.has(asset.id))) {
      if (asset.type === 'atlas' && asset.atlasPath) this.load.atlas(asset.id, assetURL(asset.path), asset.atlasPath);
      else if (asset.type === 'image') this.load.image(asset.id, assetURL(asset.path));
      else this.load.spritesheet(asset.id, assetURL(asset.path), {frameWidth: asset.frameWidth, frameHeight: asset.frameHeight});
    }
    const morning = locationLighting(this.currentWorld.location.id).morning;
    this.load.image(morning.key, morning.path);
    this.load.on('loaderror', (file: Phaser.Loader.File) => {
      if (!this.ready || (this.loading && file.key === locationLighting(this.currentWorld.location.id).morning.key)) {
        this.assetsFailed = true; this.hooks.failed();
      }
    });
  }

  create() {
    this.registerAnimations();
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
    this.resourceCooldown = true;
    this.time.delayedCall(150, () => {this.resourceCooldown = false; this.pumpResources();});
    this.events.once(Phaser.Scenes.Events.SHUTDOWN, () => {this.resourceQueue = []; this.ready = false;});
    this.apply(this.currentWorld);
    if (this.assetsFailed) this.hooks.failed();
    else if (!this.loading) this.hooks.loaded();
  }

  private registerAnimations() {
    for (const asset of this.manifest.characters) {
      if (!this.textures.exists(asset.id)) continue;
      this.textures.get(asset.id).setFilter(Phaser.Textures.FilterMode.NEAREST);
      if (asset.walkFrames.length && !this.anims.exists(`${asset.id}-walk`)) {
        this.anims.create({key: `${asset.id}-walk`, frames: asset.walkFrames.map(frame => ({key: asset.id, frame})), frameRate: asset.id === 'player' ? 12 : 7, repeat: -1});
      }
    }
    if (this.textures.exists('animals-walk')) for (const kind of ['dog','cat','bird']) {
      if (!this.anims.exists(`${kind}-move`)) this.anims.create({key:`${kind}-move`,frames:[0,1,2,3].map(i=>({key:'animals-walk',frame:`${kind}-${i}`})),frameRate:kind==='bird'?8:6,repeat:-1});
    }
    if (this.textures.exists('capoeira') && !this.anims.exists('capoeira-roda')) {
      this.textures.get('capoeira').setFilter(Phaser.Textures.FilterMode.NEAREST);
      this.anims.create({key:'capoeira-roda',frames:['0','1','2','3'].map(frame=>({key:'capoeira',frame})),frameRate:3,repeat:-1});
    }
  }

  private queueResource(resource: SceneResource) {
    if (this.textures.exists(resource.key) || this.queuedImages.has(resource.key)) return;
    this.queuedImages.add(resource.key); this.resourceQueue.push(resource);
    this.resourceQueue.sort((a, b) => a.priority - b.priority);
    this.pumpResources();
  }

  private pumpResources() {
    if (!this.ready || this.resourceCooldown || this.activeResource || this.load.isLoading()) return;
    if (this.walking && this.resourceQueue[0]?.priority === 3) return;
    const resource = this.resourceQueue.shift();
    if (!resource) return;
    this.activeResource = resource;
    this.load.once('complete', () => {
      this.activeResource = null; this.queuedImages.delete(resource.key);
      this.resourceCooldown = true;
      if (!this.ready) return;
      if (this.textures.exists(resource.key)) {
        this.registerAnimations(); this.npcSignature = '\0';
        this.apply(this.currentWorld);
      } else if (this.loading && resource.key === locationLighting(this.currentWorld.location.id).morning.key) {this.hooks.failed();}
      // Spread decoding/upload over separate turns; never flood the critical
      // movement requests with every character, place and period at once.
      this.time.delayedCall(32, () => {this.resourceCooldown = false; this.pumpResources();});
    });
    if (resource.character?.type === 'spritesheet') {
      this.load.spritesheet(resource.key, assetURL(resource.path), {frameWidth: resource.character.frameWidth, frameHeight: resource.character.frameHeight});
    } else if (resource.atlasPath) this.load.atlas(resource.key, assetURL(resource.path), resource.atlasPath);
    else this.load.image(resource.key, assetURL(resource.path));
    this.load.start();
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
    if (this.textures.exists('scene-life')) this.textures.get('scene-life').setFilter(Phaser.Textures.FilterMode.NEAREST);
    if (this.textures.exists('citizens')) this.textures.get('citizens').setFilter(Phaser.Textures.FilterMode.NEAREST);
    for(const placement of this.textures.exists('citizens') ? POPULATION[id] : []) {
      const sprite=this.add.sprite(placement.x,groundY,'citizens',`${placement.occupation}-0`)
        .setName(`citizen-${placement.id}`).setOrigin(.5,260/280).setDisplaySize(64,86).setDepth(0);
      sprite.setData('occupation',placement.occupation);
      const label=this.add.text(placement.x,groundY-88,`${placement.name} · ${placement.occupation}`,{
        fontFamily:'Georgia,serif',fontSize:'11px',color:'#fff4d2',backgroundColor:'#183c33ee',padding:{x:6,y:4},
      }).setOrigin(.5,1).setDepth(5).setVisible(false);
      sprite.setInteractive().on('pointerover',()=>label.setVisible(true)).on('pointerout',()=>label.setVisible(false));
      this.ambient.push(sprite,label);
    }
    for (const placement of AMBIENT[id]) {
      const animal=['dog','cat','bird'].includes(placement.frame);
      if (!this.textures.exists(animal ? 'animals-walk' : 'scene-life')) continue;
      const image = (animal ? this.add.sprite(placement.x,placement.y,'animals-walk',`${placement.frame}-0`) : this.add.image(placement.x,placement.y,'scene-life',placement.frame))
        .setOrigin(.5,1).setDepth(placement.frame==='tree'?-3:-1);
      image.setName(`ambient-${placement.frame}-${placement.x}`);
      if(animal && !this.reducedMotion)(image as Phaser.GameObjects.Sprite).play(`${placement.frame}-move`);
      // Fit each atlas cutout inside its box without stretching its natural silhouette.
      image.setScale(Math.min(placement.width / image.width, placement.height / image.height));
      this.ambient.push(image);
      if ((animal || placement.drift) && !this.reducedMotion) this.wanderers.push({image, placement});
    }
    if (id === 'cais_lanternas' && this.textures.exists('capoeira')) {
      // Put the roda on the forward part of the promenade, clear of the seawall.
      // The atlas feet baseline is y=480 in each 512px frame.
      const roda = this.add.sprite(745, groundY + 20, 'capoeira', '0').setOrigin(.5, 480 / 512).setDepth(-2);
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
      this.caseMarkers.push(this.add.ellipse(x, 301, 55, 12, 0xff303b, .18).setStrokeStyle(2, 0xff303b).setDepth(2));
      this.caseMarkers.push(this.add.text(x, 315, count === 1 ? 'Cena do crime' : `${count} cenas · vestígios`, {
        fontFamily: 'Georgia, serif', fontSize: '10px', color: '#fff0c4', backgroundColor: '#1b342cdd', padding: {x: 5, y: 3},
      }).setOrigin(.5, 0).setDepth(4));
    }
  }

  apply(world: WorldSnapshot) {
    this.currentWorld = world;
    if (!this.ready) return;
    const lighting = locationLighting(world.location.id);
    if (!this.textures.exists(lighting.morning.key)) {
      if (!this.loading) {this.loading = true; this.setInputEnabled(false); this.hooks.loading?.();}
      this.queueResource({...lighting.morning, priority: 0});
      return;
    }
    const wasLoading = this.loading;
    this.loading = false;
    for (const id of criticalCharacterIDs(world)) {
      const character = this.assets.get(id);
      if (character && !this.textures.exists(id)) this.queueResource({key:id, path:character.path, atlasPath:character.atlasPath, character, priority:1});
    }
    for (const id of ambientResourceIDs(world.location.id)) {
      this.queueResource({key:id, path:`/assets/ambient/${id}.png`, atlasPath:`/assets/ambient/${id}.json`, priority:3});
    }
    // The backdrop and decorations are built once per location, never per movement snapshot.
    if (world.location.id !== this.currentLocation) {
      this.currentLocation = world.location.id; this.npcPositions.clear();
      this.background?.destroy();
      this.sunsetBackground?.destroy();
      this.midnightBackground?.destroy();
      const lighting = locationLighting(world.location.id);
      this.background = this.add.image(0, 0, lighting.morning.key).setName('background-morning').setOrigin(0)
        .setDisplaySize(world.location.width, world.location.height).setDepth(-10).setScrollFactor(0);
      this.sunsetBackground = undefined; this.midnightBackground = undefined;
      this.decorationSignature = '';
      this.npcSignature = '\0';
      this.drawCaseMarkers();
      if (!this.player) {
        this.add.ellipse(world.player.x, world.location.ground_y + 1, 34, 7, 0x173e31, .3).setName('player-shadow').setDepth(2);
        this.player = this.sprite('player', world.player.x, world.location.ground_y)?.setName('player');
        this.selected = this.add.ellipse(0, world.location.ground_y + 2, 43, 11).setStrokeStyle(1, 0xf9d18b, .9).setVisible(false).setDepth(2);
      }
      this.player?.setPosition(Math.round(world.player.x), world.location.ground_y).setDepth(3);
      this.cameras.main.stopFollow();
      this.cameras.main.setBounds(0, 0, world.location.width, world.location.height);
      this.cameras.main.setScroll(0, 0);
    }
    this.syncLighting();
    const decorationSignature = world.location.id + ':' + ambientResourceIDs(world.location.id).filter(id => this.textures.exists(id)).join(',');
    if (decorationSignature !== this.decorationSignature) {
      this.decorationSignature = decorationSignature; this.dressLocation(world.location.id, world.location.ground_y);
    }
    const visible = world.visible_npcs.filter(npc => this.textures.exists(npc.sprite_id));
    const signature = visible.map(npc => `${npc.npc_id}:${npc.name}:${npc.activity}:${npc.social_partner_id}:${npc.speech ?? ""}`).join('|');
    if (signature !== this.npcSignature) {
      this.npcSignature = signature;
      this.npcs.forEach(npc => {this.tweens.killTweensOf(npc); npc.destroy();}); this.npcs = [];
      for (const npc of visible) {
        const previousX = this.npcPositions.get(npc.npc_id) ?? npc.x;
        this.npcPositions.set(npc.npc_id, npc.x);
        const shadow = this.add.ellipse(previousX, world.location.ground_y + 1, 34, 7, 0x173e31, .3).setName(`npc-shadow-${npc.npc_id}`);
        const sprite = this.sprite(npc.sprite_id, previousX, world.location.ground_y);
        const partner = world.visible_npcs.find(other => other.npc_id === npc.social_partner_id);
        if (npc.activity === 'talking' && partner) sprite?.setFlipX(partner.x < npc.x);
        if (sprite) {sprite.setName(`npc-sprite-${npc.npc_id}`);this.npcs.push(sprite); if (npc.activity === 'travelling' && !this.reducedMotion) {sprite.setFlipX(npc.x < previousX); if (this.anims.exists(`${npc.sprite_id}-walk`)) sprite.anims.play(`${npc.sprite_id}-walk`, true);}}
        this.npcs.push(shadow);
        const caption = npc.activity === 'talking' ? `${npc.name}\n${partner ? `Com ${partner.name}` : 'Conversando'}` : npc.activity === 'travelling' ? `${npc.name}\nCaminhando` : npc.name;
        const label = this.add.text(previousX, world.location.ground_y - 96, caption, {fontFamily: 'Georgia, serif', fontSize: '11px', align: 'center', color: '#fff4d2', backgroundColor: '#183c33cc', padding: {x: 5, y: 3}}).setOrigin(.5, 1).setDepth(4);
        if (npc.speech) {
          const bubble = this.add.text(npc.x, world.location.ground_y - 142, npc.speech.length > 160 ? `${npc.speech.slice(0,157)}…` : npc.speech,
            {fontFamily:'Georgia,serif',fontSize:'12px',color:'#263f30',backgroundColor:'#f4ebce',wordWrap:{width:180},padding:{x:9,y:7}})
            .setOrigin(npc.x > 750 ? 1 : npc.x < 180 ? 0 : .5,1).setDepth(6);
          this.npcs.push(bubble);
        }
        label.setName(`npc-label-${npc.npc_id}`);this.npcs.push(label);
        this.tweens.add({targets: [shadow, label, ...(sprite ? [sprite] : [])], x: npc.x, duration: this.reducedMotion ? 0 : 950, ease: "Linear"});
      }
      this.addExitSigns(world);
    }
    if (wasLoading) this.hooks.loaded();
    for (const npc of visible) {
      const sprite = this.children.getByName(`npc-sprite-${npc.npc_id}`) as Phaser.GameObjects.Sprite | null;
      const targets = ['sprite','shadow','label'].map(kind => this.children.getByName(`npc-${kind}-${npc.npc_id}`)).filter(Boolean);
      if (this.npcPositions.get(npc.npc_id) !== npc.x) {
        this.tweens.killTweensOf(targets);
        if (sprite && npc.activity === 'travelling') sprite.setFlipX(npc.x < sprite.x);
        this.tweens.add({targets, x:npc.x, duration:this.reducedMotion ? 0 : 950,ease:'Linear'});
        this.npcPositions.set(npc.npc_id,npc.x);
      }
      if (sprite && npc.activity === 'travelling' && !this.reducedMotion && this.anims.exists(`${npc.sprite_id}-walk`)) sprite.anims.play(`${npc.sprite_id}-walk`,true);
    }
  }

  private syncLighting() {
    if (!this.currentLocation) return;
    const world = this.currentWorld;
    const layers = locationLighting(this.currentLocation as LocationID);
    const progress = this.hooks.dayProgress?.() ?? 0;
    const period = lightingPeriod(this.caseState?.phase, progress);
    // A small lead time prepares sunset before it becomes visible. Midnight is
    // fetched only when the public phase says it is needed.
    if (period === 'midnight') this.queueResource({...layers.midnight, priority:2});
    else if (progress >= .55) this.queueResource({...layers.sunset, priority:2});
    if (!this.sunsetBackground && this.textures.exists(layers.sunset.key)) {
      this.sunsetBackground = this.add.image(0,0,layers.sunset.key).setName('background-sunset').setOrigin(0)
        .setDisplaySize(world.location.width,world.location.height).setDepth(-9).setScrollFactor(0);
    }
    if (!this.midnightBackground && this.textures.exists(layers.midnight.key)) {
      this.midnightBackground = this.add.image(0,0,layers.midnight.key).setName('background-midnight').setOrigin(0)
        .setDisplaySize(world.location.width,world.location.height).setDepth(-8).setScrollFactor(0);
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
    this.pumpResources();
    if (this.loading) return;
    this.syncLighting();
    this.midnightBackground?.setAlpha(this.caseState?.phase === 'night' ? 1 : 0);
    this.sunsetBackground?.setAlpha(sunsetOpacity(this.hooks.dayProgress?.() ?? 0));
    const blocked = this.hooks.blocked();
    let direction: Direction = 'idle';
    if (!blocked) {
      const left = this.cursors?.left.isDown || this.keys?.A.isDown || this.touchDirection === 'left';
      const right = this.cursors?.right.isDown || this.keys?.D.isDown || this.touchDirection === 'right';
      direction = left && !right ? 'left' : right && !left ? 'right' : 'idle';
    }
    const position = this.hooks.frame(delta, direction);
    this.walking = direction !== 'idle';
    if (this.player) {
      const moving = direction !== 'idle' && Math.abs(position.x - this.player.x) > .01;
      this.player.x = Math.round(position.x);
      this.player.setFlipX(position.facing === 'left');
      if (!moving) {
        this.player.anims.stop();
        this.player.setFrame(this.assets.get('player')?.idleFrames[0] ?? this.assets.get('player')?.frameNames?.[0] ?? 0);
      } else if (this.anims.exists('player-walk')) this.player.anims.play('player-walk', true);
      const shadow = this.children.getByName('player-shadow') as Phaser.GameObjects.Ellipse | null;
      if (shadow) shadow.x = Math.round(position.x);
    }
    for (const {image, placement} of this.wanderers) {
      const range=placement.frame==='bird'?200:placement.frame==='dog'?75:55;
      const speed=placement.frame==='bird'?35:placement.frame==='dog'?12:10;
      const phase=(time/1000*speed+placement.x)%(range*2);
      image.x=Math.round(placement.x-range/2+(phase<range?phase:range*2-phase));
      image.setFlipX(phase>=range);
      if (placement.frame === 'bird') image.y = Math.round(placement.y + Math.sin(time / 900 + placement.x) * 4);
    }
    // Townspeople are ambient scenery. Only the seven game characters travel between places.
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
