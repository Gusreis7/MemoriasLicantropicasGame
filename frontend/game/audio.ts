/** Local CC0 recordings; no requests to third-party audio services at runtime. */
export type SoundEffect = 'paper' | 'close' | 'clue' | 'step' | 'sneak' | 'slash' | 'impact';
const files: Record<SoundEffect, string[]> = {
  paper: ['bookFlip1'], close: ['bookClose'], clue: ['handleSmallLeather'],
  step: ['footstep00', 'footstep01'], sneak: ['cloth1'],
  slash: ['knifeSlice', 'knifeSlice2'], impact: ['chop'],
};

export class GameAudio {
  private unlocked = false;
  private enabled = false;
  private night = false;
  private loop: HTMLAudioElement | null = null;
  private effects = new Set<HTMLAudioElement>();
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
    document.addEventListener('visibilitychange', () => {
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
      this.loop = new Audio(`/assets/audio/${this.night ? 'night-crickets.mp3' : 'day-birds.ogg'}`);
      this.loop.loop = true; this.loop.preload = 'auto';
    }
    this.loop.volume = this.volume * .28;
    for (const sound of this.effects) sound.volume = this.volume * .55;
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
    const sound = new Audio(`/assets/audio/kenney/${options[Math.abs(variant) % options.length]}.ogg`);
    sound.volume = this.volume * (name === 'step' ? .24 : .55);
    this.effects.add(sound);
    const release = () => {this.effects.delete(sound);};
    sound.addEventListener('ended', release, {once: true});
    sound.addEventListener('error', release, {once: true});
    void sound.play().catch(release);
  }
  private stopEffects() {for (const sound of this.effects) sound.pause(); this.effects.clear();}
}

export const gameAudio = new GameAudio();
