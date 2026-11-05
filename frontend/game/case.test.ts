import {afterEach, describe, expect, it, vi} from 'vitest';
import type {CasePublic, WorldSnapshot} from '../shared/api';
import {CaseClock, CasePoller, closestCrime, formatClock, formatGameTime, gameDayProgress} from './case';

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
  it('restores the same city time from a new server snapshot or a reloaded clock', () => {
    const resumed = {...state, server_time: '2026-11-01T12:02:30Z', seconds_remaining: 150};
    const clock = new CaseClock(); clock.accept(state, 0);
    clock.accept(resumed, 5000);
    const restored = new CaseClock(); restored.accept(resumed, 80000);
    expect(formatGameTime(clock.seconds(5000))).toBe('13:30');
    expect(formatGameTime(restored.seconds(80000))).toBe('13:30');
    expect(formatGameTime(clock.seconds(65000))).toBe('15:18');
  });
  it('freezes city time during debate using public deadlines and resumes after voting', () => {
    const debating = {...state, phase_ends_at: '2026-11-01T12:06:00Z', server_time: '2026-11-01T12:02:15Z', seconds_remaining: 225,
      assembly_session: {id: 'assembly', suspect_id: 'bentinho', phase: 'debate', deadline: '2026-11-01T12:03:00Z',
        opening_speech: 'Examine as provas.', evidence_ids: [], testimony_ids: [], messages: []},
    } satisfies CasePublic;
    const clock = new CaseClock(); clock.accept(debating, 1000);
    expect(clock.seconds(1000)).toBe(180);
    expect(clock.seconds(31000)).toBe(180);
    expect(formatGameTime(clock.seconds(31000))).toBe('12:36');
    const restored = new CaseClock();
    restored.accept({...debating, server_time: '2026-11-01T12:02:45Z', seconds_remaining: 195}, 0);
    expect(restored.seconds(10000)).toBe(180);
    clock.accept({...state, server_time: '2026-11-01T12:02:50Z', phase_ends_at: '2026-11-01T12:05:50Z', seconds_remaining: 180}, 36000);
    expect(clock.seconds(46000)).toBe(170);
    expect(formatGameTime(clock.seconds(46000))).toBe('12:54');
  });
});

describe('city time', () => {
  it.each([[300, '09:00'], [250, '10:30'], [200, '12:00'], [150, '13:30'], [100, '15:00'], [50, '16:30'], [0, '18:00']])(
    'translates %s real seconds remaining to %s', (seconds, time) => {
      expect(formatGameTime(Number(seconds))).toBe(time);
    },
  );
  it('clamps daylight at morning and sunset and keeps a shared normalized progress', () => {
    expect(gameDayProgress(300)).toBe(0);
    expect(gameDayProgress(150)).toBe(.5);
    expect(gameDayProgress(0)).toBe(1);
    expect(formatGameTime(500)).toBe('09:00');
    expect(formatGameTime(-20)).toBe('18:00');
    expect(formatGameTime(Number.NaN)).toBe('09:00');
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
