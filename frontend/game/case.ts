import type {CaseCrime, CasePublic, WorldSnapshot} from '../shared/api';

/** The local monotonic clock displays a server deadline; it never advances a phase. */
export class CaseClock {
  private state: CasePublic | null = null;
  private sampledAt = 0;
  private remaining = 0;

  accept(state: CasePublic, monotonicNow = performance.now()) {
    this.state = state;
    this.sampledAt = monotonicNow;
    const deadline = (Date.parse(state.phase_ends_at) - Date.parse(state.server_time)) / 1000;
    this.remaining = Number.isFinite(deadline) ? Math.max(0, Math.min(deadline, state.seconds_remaining)) : 0;
  }

  seconds(monotonicNow = performance.now()) {
    return Math.max(0, Math.ceil(this.remaining - Math.max(0, monotonicNow - this.sampledAt) / 1000));
  }

  blocked(monotonicNow = performance.now()) {
    return !this.state || this.state.phase !== 'day' || this.state.status !== 'active' || this.seconds(monotonicNow) === 0;
  }
}

export function formatClock(seconds: number) {
  const safe = Math.max(0, Math.ceil(seconds));
  return `${Math.floor(safe / 60).toString().padStart(2, '0')}:${(safe % 60).toString().padStart(2, '0')}`;
}

export function closestCrime(state: CasePublic | null, world: WorldSnapshot, x: number): CaseCrime | undefined {
  if (!state || state.phase !== 'day' || state.status !== 'active') return undefined;
  return state.crimes.filter(crime => crime.location_id === world.location.id && crime.remaining_clues > 0 && Math.abs(crime.x - x) <= 90)
    .sort((a, b) => Math.abs(a.x - x) - Math.abs(b.x - x))[0];
}

/** Recursive scheduling: one request at a time, including slow responses and retries. */
export class CasePoller {
  private timer?: ReturnType<typeof setTimeout>;
  private generation = 0;

  start(poll: () => Promise<void>, interval = 1000) {
    this.stop();
    const generation = this.generation;
    const run = async () => {
      try {await poll();} finally {
        if (this.generation === generation) this.timer = setTimeout(() => {void run();}, interval);
      }
    };
    this.timer = setTimeout(() => {void run();}, interval);
  }

  stop() {this.generation++; clearTimeout(this.timer);}
}
