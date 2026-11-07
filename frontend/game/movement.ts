import {ApiError, type Direction, type WorldSnapshot, type MovementInput} from '../shared/api';

export const WALK_SPEED = 210;
export const APPROACH_DISTANCE = 64;
// Match the server's bounded movement window; never predict through a disconnect.
const MAX_PREDICTION_MS = 1000;
const MAX_INPUTS = 128;
export const clampX = (x: number, width: number) => Math.min(width - 32, Math.max(32, x));

export function closestNPC(world: WorldSnapshot, x: number) {
  let nearest: WorldSnapshot['visible_npcs'][number] | undefined;
  let distance = APPROACH_DISTANCE;
  for (const npc of world.visible_npcs) {
    const next = Math.abs(npc.x - x);
    if (next <= distance && (!nearest || next < distance)) {nearest = npc; distance = next;}
  }
  return nearest;
}

export class MovementController {
  world: WorldSnapshot;
  x: number;
  direction: Direction = 'idle';
  facing: 'left' | 'right';
  private queuedDirection: Direction = 'idle';
  private elapsed = 0;
  private pending: Promise<void> | null = null;
  private disposed = false;
  private inputs: MovementInput[] = [];
  private nextInput: number;
  private stopping: Promise<void> | null = null;
  private suspended = false;
  private transmissionError: unknown = null;
  private observation: WorldSnapshot | null = null;
  private inFlight: {command: number; input: number} | null = null;

  constructor(world: WorldSnapshot,
    private send: (world: WorldSnapshot, direction: Direction, inputs?: MovementInput[]) => Promise<WorldSnapshot>,
    private refresh: () => Promise<WorldSnapshot>,
    private changed: (world: WorldSnapshot) => void,
    private failed: (error: unknown) => void,
    private clock: () => number = () => performance.now()) {
    this.world = world; this.x = world.player.x;
    this.facing = world.player.facing;
    this.nextInput = (world.player.input_seq ?? 0) + 1;
  }

  accept(world: WorldSnapshot) {
    this.world = world; this.x = world.player.x;
    this.facing = world.player.facing;
    this.direction = this.queuedDirection = 'idle';
    this.elapsed = 0; this.inputs = [];
    this.nextInput = (world.player.input_seq ?? 0) + 1;
    this.suspended = false;
    this.transmissionError = null;
    this.observation = null;
    this.changed(world);
  }

  /** Refresh public NPC activity without changing a predicted player position. */
  observe(world: WorldSnapshot): boolean {
    if (this.disposed || world.game_id !== this.world.game_id
      || world.location.id !== this.world.location.id || world.revision < this.world.revision
      || world.player.movement_epoch !== this.world.player.movement_epoch
      || (this.observation && world.revision < this.observation.revision)) return false;
    const input = world.player.input_seq ?? 0;
    const same = world.player.movement_seq === this.world.player.movement_seq
      && input === (this.world.player.input_seq ?? 0);
    const awaiting = this.inFlight && world.player.movement_seq === this.inFlight.command
      && input >= (this.world.player.input_seq ?? 0) && input <= this.inFlight.input;
    if (!same && !awaiting) return false;
    if (!same) {
      this.observation = world;
      this.world = {...this.world, visible_npcs: world.visible_npcs,
        npc_presences: world.npc_presences, travel_targets: world.travel_targets};
      this.changed(this.world); return true;
    }
    this.world = this.observation = world; this.changed(world); return true;
  }

  private mark(direction: Direction) {
    if (direction === this.queuedDirection || this.inputs.length >= MAX_INPUTS) return;
    this.inputs.push({seq: this.nextInput++, direction, duration_ms: 0});
    this.queuedDirection = direction;
  }

  update(delta: number, desired: Direction) {
    if (this.disposed) return;
    if (this.stopping || this.suspended) desired = 'idle';
    this.direction = desired;
    if (desired !== 'idle') this.facing = desired;
    if (!this.stopping && !this.suspended) {
      this.mark(desired);
      let remaining = Math.min(Math.max(delta, 0), 250,
        Math.max(0, MAX_PREDICTION_MS - this.inputs.reduce((sum, input) => sum + input.duration_ms, 0)));
      while (desired !== 'idle' && desired === this.queuedDirection && remaining > .000001 && this.inputs.length < MAX_INPUTS) {
        const ms = Math.min(50, remaining);
        this.inputs.push({seq: this.nextInput++, direction: desired, duration_ms: ms});
        this.x = clampX(this.x + (desired === 'left' ? -1 : 1) * WALK_SPEED * ms / 1000, this.world.location.width);
        remaining -= ms;
      }
    }
    this.elapsed += Math.max(0, delta);
    if (!this.pending && !this.stopping && !this.suspended && this.inputs.length
        && (this.elapsed >= 150 || this.inputs.some(input => input.duration_ms === 0))) void this.transmit(desired);
  }

  private async transmit(direction: Direction) {
    if (this.pending || this.disposed || !this.inputs.length) return;
    this.elapsed = 0;
    const sent = this.inputs.map(input => ({...input}));
    this.inFlight = {command: this.world.player.movement_seq + 1, input: sent.at(-1)!.seq};
    const work = async () => {
      try {
        let next = await this.send(this.world, direction, sent);
        if (this.disposed) return;
        const acknowledged = next.player.input_seq;
        // Only explicit input acknowledgements drive replay. Full snapshots
        // without this field are accepted for API mocks/older deployed servers.
        const seq = acknowledged ?? sent.at(-1)!.seq;
        if (!Number.isSafeInteger(seq) || seq < (this.world.player.input_seq ?? 0) || seq > sent.at(-1)!.seq) throw new ApiError(409, 'Confirmação de movimento inválida.');
        this.inputs = this.inputs.filter(input => input.seq > seq);
        // Compact acknowledgements carry no NPC data. Preserve a newer public
        // observation received while the command was in flight, without ever
        // taking its player coordinates as a prediction correction.
        if (acknowledged !== undefined && this.observation
          && this.observation.game_id === next.game_id
          && this.observation.location.id === next.location.id
          && this.observation.player.movement_epoch === next.player.movement_epoch) {
          next = {...next, visible_npcs: this.observation.visible_npcs,
            npc_presences: this.observation.npc_presences, travel_targets: this.observation.travel_targets};
        }
        this.world = next;
        let predicted = next.player.x;
        for (const input of this.inputs) predicted = clampX(predicted + (input.direction === 'left' ? -1 : input.direction === 'right' ? 1 : 0)
          * WALK_SPEED * input.duration_ms / 1000, next.location.width);
        // With matching integration this is the existing position, including
        // after releasing the key. There is no idle drift or RTT approximation.
        this.x = predicted;
        this.transmissionError = null;
        this.changed(next);
      } catch (error) {
        try {this.accept(await this.refresh());} catch { /* Keep the last known canonical state. */ }
        this.direction = this.queuedDirection = 'idle';
        this.inputs = [];
        this.transmissionError = error;
        if (!this.stopping) this.failed(error);
      }
    };
    this.pending = work();
    try {await this.pending;} finally {this.pending = null; this.inFlight = null;}
  }

  stop(): Promise<void> {
    if (this.stopping) return this.stopping;
    this.direction = 'idle';
    this.mark('idle');
    const work = async () => {
      const deadline = this.clock() + 10000;
      await this.pending;
      if (this.transmissionError) throw this.transmissionError;
      this.mark('idle');
      // No new frames enter the queue during stop. A server with insufficient
      // elapsed time acknowledges a prefix; give it a real tick before retrying.
      while (!this.disposed && this.inputs.length) {
        if (this.clock() > deadline) {
          const error = new ApiError(0, 'A confirmação da parada demorou demais.');
          throw error;
        }
        await this.transmit('idle');
        if (this.transmissionError) throw this.transmissionError;
        this.mark('idle');
        if (this.inputs.length) await new Promise<void>(resolve => setTimeout(resolve, 25));
      }
    };
    this.stopping = work().finally(() => {this.stopping = null;});
    return this.stopping;
  }

  /** A confirmed phase change supersedes queued inputs; never send an old-day
   * stop into the new phase. accept() will install its authoritative position. */
  async suspend() {
    this.suspended = true; this.direction = 'idle';
    await this.pending;
    this.inputs = []; this.queuedDirection = 'idle';
  }
  dispose() {this.disposed = true;}
}
