/** Local CC0 recordings; no requests to third-party audio services at runtime. */
export type SoundEffect = 'paper' | 'close' | 'clue' | 'step' | 'sneak' | 'slash' | 'impact' | 'howl';
const files: Record<SoundEffect, string[]> = {
  paper: ['bookFlip1'], close: ['bookClose'], clue: ['handleSmallLeather'],
  step: ['footstep00', 'footstep01'], sneak: ['cloth1'],
  slash: ['knifeSlice', 'knifeSlice2'],
  impact: ['impact-1', 'impact-2', 'impact-3', 'impact-4'], howl: ['howl-long'],
};

export class GameAudio {
  private unlocked = false;
  private enabled = false;
  private night = false;
  private loop: HTMLAudioElement | null = null;
  private effects = new Set<HTMLAudioElement>();
  private cinematicEffects = new Set<HTMLAudioElement>();
  private effectGains = new WeakMap<HTMLAudioElement, number>();
  private lastStep = 0;
  private alternating = 0;
  volume = .45;
  muted = false;

  constructor() {
    try {
      const saved = JSON.parse(localStorage.getItem('ml.audio') ?? 'null');
      if (saved && typeof saved.volume === 'number' && Number.isFinite(saved.volume)) this.volume = Math.max(0, Math.min(1, saved.volume));
      if (saved && typeof saved.muted === 'boolean') this.muted = saved.muted;
    } catch { /* Audio settings are optional when storage is unavailable. */ }
    if (typeof document !== 'undefined') document.addEventListener('visibilitychange', () => {
      if (document.hidden) this.stopEffects();
      this.sync();
    });
  }

  /** Call synchronously from a user gesture, before awaiting launch requests. */
  unlock() {this.unlocked = true; this.sync();}
  start() {this.enabled = true; this.sync();}
  stop() {this.enabled = false; this.stopEffects(); this.sync();}
  setNight(night: boolean) {
    if (this.night === night) return;
    this.night = night;
    this.loop?.pause(); this.loop = null;
    this.sync();
  }
  setVolume(volume: number) {
    this.volume = Number.isFinite(volume) ? Math.max(0, Math.min(1, volume)) : this.volume;
    this.persist(); this.sync();
  }
  setMuted(muted: boolean) {
    this.muted = muted;
    if (muted) this.stopEffects();
    this.persist(); this.sync();
  }
  private persist() {
    try {localStorage.setItem('ml.audio', JSON.stringify({volume: this.volume, muted: this.muted}));} catch { /* optional */ }
  }
  private audible() {return this.unlocked && this.enabled && !this.muted && this.volume > 0 && !document.hidden;}
  private sync() {
    if (!this.audible()) {this.loop?.pause(); return;}
    if (!this.loop) {
      this.loop = new Audio(`/assets/audio/${this.night ? 'night-ominous.ogg' : 'day-birds.ogg'}`);
      this.loop.loop = true; this.loop.preload = 'auto';
    }
    this.loop.volume = this.volume * .28;
    for (const sound of this.effects) sound.volume = this.volume * (this.effectGains.get(sound) ?? .55);
    if (this.loop.paused) void this.loop.play().catch(() => {});
  }
  effect(name: SoundEffect, variant = 0) {
    if (!this.audible()) return;
    if (name === 'step') {
      const now = performance.now();
      if (now - this.lastStep < 280) return;
      this.lastStep = now; variant = this.alternating++;
    }
    if (this.effects.size >= 6) return;
    const options = files[name];
    const cinematic = name === 'howl' || name === 'impact' || name === 'sneak' || name === 'slash';
    const folder = name === 'howl' || name === 'impact' ? 'werewolf' : 'kenney';
    const index = Number.isFinite(variant) ? Math.abs(Math.trunc(variant)) % options.length : 0;
    const sound = new Audio(`/assets/audio/${folder}/${options[index]}.ogg`);
    const gain = name === 'step' ? .24 : name === 'howl' ? .85 : .55;
    sound.volume = this.volume * gain; this.effectGains.set(sound, gain);
    this.effects.add(sound);
    if (cinematic) this.cinematicEffects.add(sound);
    const release = () => {this.effects.delete(sound); this.cinematicEffects.delete(sound);};
    sound.addEventListener('ended', release, {once: true});
    sound.addEventListener('error', release, {once: true});
    void sound.play().catch(release);
  }
  /** Cancel only cinematic sounds when skipping or closing an attack. */
  stopCinematicEffects() {
    for (const sound of this.cinematicEffects) {sound.pause(); this.effects.delete(sound);}
    this.cinematicEffects.clear();
  }
  private stopEffects() {for (const sound of this.effects) sound.pause(); this.effects.clear(); this.cinematicEffects.clear();}
}

export const gameAudio = new GameAudio();
