import type {CaseCrime, CasePublic, WorldSnapshot} from '../shared/api';

export const DAY_DURATION_SECONDS = 300;
const MORNING_MINUTES = 9 * 60;
const SUNSET_MINUTES = 18 * 60;

/** The local monotonic clock displays a server deadline; it never advances a phase. */
export class CaseClock {
  private state: CasePublic | null = null;
  private sampledAt = 0;
  private remaining = 0;
  private paused = false;

  accept(state: CasePublic, monotonicNow = performance.now()) {
    this.state = state;
    this.sampledAt = monotonicNow;
    this.paused = state.phase === 'day' && state.assembly_session?.phase === 'debate' && !state.assembly;
    // The server extends the day by the debate's duration. The gap between
    // these public deadlines is the frozen day time, including after reload.
    const reference = this.paused ? state.assembly_session!.deadline : state.server_time;
    const deadline = (Date.parse(state.phase_ends_at) - Date.parse(reference)) / 1000;
    this.remaining = Number.isFinite(deadline) ? Math.max(0, Math.min(deadline, state.seconds_remaining)) : 0;
  }

  seconds(monotonicNow = performance.now()) {
    const elapsed = this.paused ? 0 : Math.max(0, monotonicNow - this.sampledAt) / 1000;
    return Math.max(0, Math.ceil(this.remaining - elapsed));
  }

  blocked(monotonicNow = performance.now()) {
    return !this.state || this.state.phase !== 'day' || this.state.status !== 'active' || this.seconds(monotonicNow) === 0;
  }
}

/** Daylight runs from 09:00 to 18:00 within the server's five-minute day. */
export function gameDayProgress(secondsRemaining: number) {
  if (Number.isNaN(secondsRemaining)) return 0;
  return Math.min(1, Math.max(0, 1 - secondsRemaining / DAY_DURATION_SECONDS));
}

export function formatGameTime(secondsRemaining: number) {
  const minutes = Math.floor(MORNING_MINUTES + gameDayProgress(secondsRemaining) * (SUNSET_MINUTES - MORNING_MINUTES));
  return `${Math.floor(minutes / 60).toString().padStart(2, '0')}:${(minutes % 60).toString().padStart(2, '0')}`;
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
