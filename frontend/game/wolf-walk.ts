/** Eight measured contact/passing frames per 84px of ground travel. */
export const WOLF_STRIDE_PIXELS = 84;
export function wolfWalkFrame(distance: number) {
  const traveled = Number.isFinite(distance) ? Math.max(0, distance) : 0;
  return String(Math.floor(traveled / WOLF_STRIDE_PIXELS * 8) % 8);
}
