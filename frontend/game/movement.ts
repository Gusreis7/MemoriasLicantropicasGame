import {ApiError, type Direction, type WorldSnapshot} from '../shared/api';

export const WALK_SPEED = 210;
export const APPROACH_DISTANCE = 64;
// Match the server's bounded movement window; never predict through a disconnect.
const MAX_PREDICTION_MS = 1000;
const CORRECTION_SPEED = WALK_SPEED / 2;
type PredictedInput = {start: number; end: number; direction: Direction};
export const clampX = (x: number, width: number) => Math.min(width - 32, Math.max(32, x));

export function closestNPC(world: WorldSnapshot, x: number) {
  return world.visible_npcs.filter(npc => Math.abs(npc.x - x) <= APPROACH_DISTANCE)
    .sort((a, b) => Math.abs(a.x - x) - Math.abs(b.x - x))[0];
}

export class MovementController {
  world: WorldSnapshot;
  x: number;
  direction: Direction = 'idle';
  private lastSentDirection: Direction = 'idle';
  private elapsed = 0;
  private pending: Promise<void> | null = null;
  private disposed = false;
  private predictedX: number;
  private sentAt: number | null = null;
  private inputs: PredictedInput[] = [];
  private stopping: Promise<void> | null = null;
  private suspended = false;

  constructor(world: WorldSnapshot,
    private send: (world: WorldSnapshot, direction: Direction) => Promise<WorldSnapshot>,
    private refresh: () => Promise<WorldSnapshot>,
    private changed: (world: WorldSnapshot) => void,
    private failed: (error: unknown) => void,
    private clock: () => number = () => performance.now()) {
    this.world = world;
    this.x = this.predictedX = world.player.x;
  }

  accept(world: WorldSnapshot) {
    this.world = world;
    this.x = this.predictedX = world.player.x;
    this.direction = 'idle';
    this.lastSentDirection = 'idle';
    this.elapsed = 0;
    this.inputs = [];
    this.suspended = false;
    this.changed(world);
  }

  /** Refresh NPC activity without cancelling the player's predicted walk. */
  observe(world: WorldSnapshot): boolean {
    if (this.disposed || this.pending || world.game_id !== this.world.game_id
      || world.location.id !== this.world.location.id || world.revision < this.world.revision
      || world.player.movement_seq !== this.world.player.movement_seq) return false;
    this.world = world;
    this.changed(world);
    return true;
  }

  update(delta: number, desired: Direction) {
    if (this.disposed) return;
    if (this.stopping || this.suspended) desired = 'idle';
    this.direction = desired;
    const now = this.clock();
    const dt = Math.max(0, Math.min(delta, 50));
    const start = now - dt;
    const end = this.sentAt === null ? now : Math.min(now, this.sentAt + MAX_PREDICTION_MS);
    const movementMs = Math.max(0, end - start);
    const distance = (desired === 'left' ? -1 : desired === 'right' ? 1 : 0) * WALK_SPEED * movementMs / 1000;
    const previousX = this.x;
    this.predictedX = clampX(this.predictedX + distance, this.world.location.width);
    this.x = clampX(this.x + distance, this.world.location.width);
    // Keep normal corrections slower than walking, so a held key never makes
    // Floriano step backwards when an acknowledgement arrives late.
    const error = this.predictedX - this.x;
    const correction = Math.sign(error) * Math.min(Math.abs(error) * (1 - Math.exp(-dt / 90)), CORRECTION_SPEED * dt / 1000);
    this.x = clampX(this.x + correction, this.world.location.width);
    // At a boundary the forward step can be clamped to zero; avoid a backwards
    // correction there too. A stop will finish reconciling to the canonical point.
    if (desired === 'right') this.x = Math.max(previousX, this.x);
    else if (desired === 'left') this.x = Math.min(previousX, this.x);
    if (this.sentAt !== null && movementMs > 0) this.inputs.push({start, end, direction: desired});
    this.elapsed += dt;
    if (!this.stopping && !this.suspended && !this.pending
      && (desired !== this.lastSentDirection || (desired !== 'idle' && this.elapsed >= 150))) {
      void this.transmit(desired);
    }
  }

  private async transmit(direction: Direction) {
    if (this.pending || this.disposed) return;
    this.elapsed = 0;
    const sentAt = this.sentAt = this.clock();
    this.inputs = [];
    const work = async () => {
      try {
        const next = await this.send(this.world, direction);
        if (this.disposed) return;
        this.world = next;
        this.lastSentDirection = direction;
        // Estimate receipt at the server using half the round trip. Replay only
        // local inputs after that point; smooth the rendered position separately.
        // No client coordinate or clock is sent to the authoritative server.
        const acknowledgedAt = sentAt + (this.clock() - sentAt) / 2;
        this.predictedX = next.player.x;
        for (const input of this.inputs) {
          const ms = Math.max(0, input.end - Math.max(input.start, acknowledgedAt));
          const sign = input.direction === 'left' ? -1 : input.direction === 'right' ? 1 : 0;
          this.predictedX = clampX(this.predictedX + sign * WALK_SPEED * ms / 1000, next.location.width);
        }
        this.changed(next);
      } catch (error) {
        this.direction = 'idle';
        this.lastSentDirection = 'idle';
        if (error instanceof ApiError && error.status === 409) {
          try { this.accept(await this.refresh()); } catch (refreshError) { this.failed(refreshError); }
        } else { this.failed(error); }
      }
    };
    this.pending = work();
    await this.pending;
    this.pending = null;
    this.sentAt = null;
    this.inputs = [];
  }

  stop(): Promise<void> {
    if (this.stopping) return this.stopping;
    this.direction = 'idle';
    const work = async () => {
      await this.pending;
      if (this.lastSentDirection !== 'idle') await this.transmit('idle');
      this.predictedX = this.world.player.x;
    };
    this.stopping = work().finally(() => {this.stopping = null;});
    return this.stopping;
  }

  /** Wait for an in-flight intention before accepting a server phase transition. */
  async suspend() {
    this.suspended = true;
    this.direction = 'idle';
    await this.pending;
    this.predictedX = this.world.player.x;
  }

  dispose() {this.disposed = true;}
}
