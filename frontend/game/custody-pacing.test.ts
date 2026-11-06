import {describe,it,expect} from 'vitest';
import {custodyPacing,CELL_PACING} from './custody-pacing';
describe('prison pacing',()=>{
  it('starts at cell center and turns without crossing the safe bounds',()=>{
    expect(custodyPacing(0).x).toBe(480);
    for(let t=0;t<30000;t+=100){const p=custodyPacing(t);expect(p.x).toBeGreaterThanOrEqual(CELL_PACING.left);expect(p.x).toBeLessThanOrEqual(CELL_PACING.right);}
    expect(custodyPacing(2000).facing).toBe('left');expect(custodyPacing(5500).facing).toBe('right');
  });
  it('keeps speed and distance deterministic for the atlas step phases',()=>{
    expect(custodyPacing(1000).distance).toBe(42);expect(custodyPacing(NaN).x).toBe(480);
  });
});
