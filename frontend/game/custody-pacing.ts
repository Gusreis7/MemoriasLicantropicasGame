/** Cell jambs are x324..636. Keep the full human silhouette inside them. */
export const CELL_PACING = {left:410,right:550,speed:42,ground:370};
export function custodyPacing(elapsedMs:number) {
  const distance=Math.max(0,Number.isFinite(elapsedMs)?elapsedMs:0)/1000*CELL_PACING.speed;
  const span=CELL_PACING.right-CELL_PACING.left;
  const phase=(distance+span/2)%(span*2);
  const returning=phase>=span;
  return {x:CELL_PACING.left+(returning?span*2-phase:phase),facing:returning?'left' as const:'right' as const,distance};
}
