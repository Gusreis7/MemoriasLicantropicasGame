import {describe,it,expect} from 'vitest';
import {wolfWalkFrame,WOLF_STRIDE_PIXELS} from './wolf-walk';
describe('wolf ground-distance gait',()=>{
  it('alternates all eight poses and repeats only after a full stride',()=>{
    expect(Array.from({length:8},(_,i)=>wolfWalkFrame(i*WOLF_STRIDE_PIXELS/8))).toEqual(['0','1','2','3','4','5','6','7']);
    expect(wolfWalkFrame(WOLF_STRIDE_PIXELS)).toBe('0');
  });
  it('keeps the same pose when stationary and sanitizes invalid distances',()=>{
    expect(wolfWalkFrame(21)).toBe(wolfWalkFrame(21));
    expect(wolfWalkFrame(-1)).toBe('0');expect(wolfWalkFrame(NaN)).toBe('0');
  });
});
