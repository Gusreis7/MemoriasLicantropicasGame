import {beforeEach, describe, expect, it, vi} from 'vitest';

const sounds: FakeAudio[] = [];
class FakeAudio {
  paused = true; loop = false; preload = ''; volume = 1;
  play = vi.fn(() => {this.paused = false; return Promise.resolve();});
  pause = vi.fn(() => {this.paused = true;});
  addEventListener = vi.fn();
  constructor(public src: string) {sounds.push(this);}
}
let visibility: () => void;
let page: {hidden: boolean; addEventListener: ReturnType<typeof vi.fn>};
let storage: Map<string, string>;

beforeEach(() => {
  vi.resetModules(); sounds.length = 0; storage = new Map();
  page = {hidden: false, addEventListener: vi.fn((_name, callback) => {visibility = callback;})};
  vi.stubGlobal('document', page); vi.stubGlobal('Audio', FakeAudio);
  vi.stubGlobal('localStorage', {getItem: (key: string) => storage.get(key) ?? null, setItem: (key: string, value: string) => storage.set(key, value)});
});

describe('política de áudio', () => {
  it('aguarda gesto e mantém só um ambiente ao alternar dia e noite', async () => {
    const {gameAudio} = await import('./audio');
    gameAudio.start(); expect(sounds).toHaveLength(0);
    gameAudio.unlock(); expect(sounds).toHaveLength(1);
    const day = sounds[0]; gameAudio.setNight(true);
    expect(day.paused).toBe(true); expect(sounds[1].src).toContain('night-ominous');
    gameAudio.setNight(true); expect(sounds).toHaveLength(2);
  });

  it('mute e aba oculta interrompem efeitos e retomam só ambiente', async () => {
    const {gameAudio} = await import('./audio');
    gameAudio.unlock(); gameAudio.start(); gameAudio.effect('slash');
    page.hidden = true; visibility();
    expect(sounds.every(sound => sound.paused)).toBe(true);
    page.hidden = false; visibility(); expect(sounds[0].paused).toBe(false); expect(sounds[1].paused).toBe(true);
    gameAudio.setMuted(true); gameAudio.effect('impact'); expect(sounds).toHaveLength(2);
    expect(JSON.parse(storage.get('ml.audio')!).muted).toBe(true);
  });

  it('limita sobreposição mesmo para golpes repetidos e para ao encerrar', async () => {
    const {gameAudio} = await import('./audio');
    gameAudio.unlock(); gameAudio.start();
    for (let i = 0; i < 10; i++) gameAudio.effect('impact');
    expect(sounds).toHaveLength(7); // one background, at most six effects
    gameAudio.stop(); expect(sounds.every(sound => sound.paused)).toBe(true);
  });

  it('cancela uivo e golpes ao pular sem interromper ambiente ou papel', async () => {
    const {gameAudio} = await import('./audio');
    gameAudio.unlock(); gameAudio.start(); gameAudio.effect('paper'); gameAudio.effect('howl');
    gameAudio.effect('impact', 3);
    expect(sounds[3].src).toContain('werewolf/impact-4.ogg');
    gameAudio.stopCinematicEffects();
    expect(sounds[0].paused).toBe(false); expect(sounds[1].paused).toBe(false);
    expect(sounds[2].paused).toBe(true); expect(sounds[3].paused).toBe(true);
  });

  it('preserva destaque do uivo respeitando o volume geral', async () => {
    const {gameAudio} = await import('./audio');
    gameAudio.unlock(); gameAudio.start(); gameAudio.effect('howl'); gameAudio.setVolume(.5);
    expect(sounds[1].volume).toBeCloseTo(.425);
  });
});
