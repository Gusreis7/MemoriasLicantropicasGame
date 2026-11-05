import type {LocationID} from '../shared/api';

/** Two lighting plates share the same layout and world coordinates. */
export function locationLighting(id: LocationID) {
  return {
    morning: {key: `location-${id}-09h`, path: `/assets/locations/${id}-09h.png`},
    sunset: {key: `location-${id}-18h`, path: `/assets/locations/${id}-18h.png`},
  };
}

/** Keep daylight until 15:00, then ease into the 18:00 plate. */
export function sunsetOpacity(dayProgress: number) {
  const progress = Number.isFinite(dayProgress) ? dayProgress : 0;
  const afternoon = Math.max(0, Math.min(1, progress * 3 - 2));
  return afternoon * afternoon * (3 - 2 * afternoon);
}
