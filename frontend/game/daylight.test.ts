import {readFileSync} from 'node:fs';
import {describe, expect, it} from 'vitest';
import type {LocationID} from '../shared/api';
import {gameDayProgress} from './case';
import {locationLighting, sunsetOpacity} from './daylight';

describe('iluminação dos locais', () => {
  it('mantém manhã até 15h e chega ao pôr do sol às 18h no mesmo relógio', () => {
    expect(sunsetOpacity(gameDayProgress(300))).toBe(0); // 09:00
    expect(sunsetOpacity(gameDayProgress(150))).toBe(0); // 13:30
    expect(sunsetOpacity(gameDayProgress(100))).toBe(0); // 15:00
    expect(sunsetOpacity(gameDayProgress(50))).toBeCloseTo(.5); // 16:30
    expect(sunsetOpacity(gameDayProgress(0))).toBe(1); // 18:00
    expect(sunsetOpacity(Number.NaN)).toBe(0);
  });

  it('carrega três artes reais por local, correspondentes ao manifesto e à área do mundo', () => {
    const root = new URL('../public', import.meta.url);
    const manifest = JSON.parse(readFileSync(new URL('assets/locations/manifest.json', `${root}/`), 'utf8'));
    expect(manifest.assets).toHaveLength(5);
    for (const asset of manifest.assets) {
      const layers = locationLighting(asset.id as LocationID);
      for (const period of ['morning', 'sunset', 'midnight'] as const) {
        expect(layers[period].path).toBe(asset.lighting[period].path);
        const png = readFileSync(new URL(layers[period].path.slice(1), `${root}/`));
        expect(png.subarray(1, 4).toString()).toBe('PNG');
        const width = png.readUInt32BE(16), height = png.readUInt32BE(20);
        expect([width, height]).toEqual([asset.lighting[period].width, asset.lighting[period].height]);
        expect(width / height).toBeCloseTo(asset.displayWidth / asset.displayHeight, 2);
      }
    }
  });
});
