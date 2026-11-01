import {afterEach, describe, expect, it, vi} from 'vitest';
import type {CasePublic, WorldSnapshot} from '../shared/api';
import {CaseClock, CasePoller, closestCrime, formatClock} from './case';

const state = {game_id: 'case', revision: 0, day: 1, phase: 'day', status: 'active',
  server_time: '2026-11-01T12:00:00Z', phase_ends_at: '2026-11-01T12:05:00Z', seconds_remaining: 300,
  crimes: [{id: 'crime', location_id: 'praca_verde', x: 600, remaining_clues: 2}],
} as CasePublic;
afterEach(() => vi.useRealTimers());

describe('server clock', () => {
  it('uses server interval and a monotonic clock, even with a wrong computer date', () => {
    const clock = new CaseClock(); clock.accept(state, 1000);
    expect(clock.seconds(1500)).toBe(300);
    expect(clock.seconds(61000)).toBe(240);
    expect(clock.blocked(301000)).toBe(true);
    expect(clock.seconds(601000)).toBe(0);
    expect(clock.seconds(0)).toBe(300);
  });
  it('blocks until synchronized and throughout night or final state', () => {
    const clock = new CaseClock(); expect(clock.blocked()).toBe(true);
    clock.accept({...state, phase: 'night', seconds_remaining: 8}, 0); expect(clock.blocked(1)).toBe(true);
    clock.accept({...state, phase: 'finished', status: 'won'}, 0); expect(clock.blocked(1)).toBe(true);
    clock.accept(state, 0); expect(clock.blocked(1)).toBe(false);
  });
  it('keeps invalid or exhausted deadlines blocked and formats zero safely', () => {
    const clock = new CaseClock(); clock.accept({...state, phase_ends_at: 'invalid'}, 0);
    expect(clock.blocked(0)).toBe(true);
    expect(formatClock(300)).toBe('05:00'); expect(formatClock(8)).toBe('00:08'); expect(formatClock(-1)).toBe('00:00');
  });
});

it('only offers clues in reach, at the current location, during the day', () => {
  const world = {location: {id: 'praca_verde'}} as WorldSnapshot;
  expect(closestCrime(state, world, 510)?.id).toBe('crime');
  expect(closestCrime(state, world, 509)).toBeUndefined();
  expect(closestCrime({...state, phase: 'night'}, world, 600)).toBeUndefined();
  expect(closestCrime(state, {location: {id: 'cais_lanternas'}} as WorldSnapshot, 600)).toBeUndefined();
  expect(closestCrime({...state, crimes: [{...state.crimes[0], remaining_clues: 0}]}, world, 600)).toBeUndefined();
});

it('polls sequentially and cannot restart after stop while a request is in flight', async () => {
  vi.useFakeTimers();
  let release!: () => void; const waiting = new Promise<void>(resolve => {release = resolve;});
  const poll = vi.fn(() => waiting); const runner = new CasePoller(); runner.start(poll, 1000);
  await vi.advanceTimersByTimeAsync(1000); expect(poll).toHaveBeenCalledTimes(1);
  await vi.advanceTimersByTimeAsync(10000); expect(poll).toHaveBeenCalledTimes(1);
  runner.stop(); release(); await Promise.resolve();
  await vi.advanceTimersByTimeAsync(10000); expect(poll).toHaveBeenCalledTimes(1);
});
