import {ApiError, type Direction, type WorldSnapshot} from '../shared/api';

export const WALK_SPEED = 210;
export const APPROACH_DISTANCE = 64;
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

  constructor(world: WorldSnapshot,
    private send: (world: WorldSnapshot, direction: Direction) => Promise<WorldSnapshot>,
    private refresh: () => Promise<WorldSnapshot>,
    private changed: (world: WorldSnapshot) => void,
    private failed: (error: unknown) => void) {
    this.world = world;
    this.x = world.player.x;
  }

  accept(world: WorldSnapshot) {
    this.world = world;
    this.x = world.player.x;
    this.direction = 'idle';
    this.lastSentDirection = 'idle';
    this.elapsed = 0;
    this.changed(world);
  }

  update(delta: number, desired: Direction) {
    if (this.disposed) return;
    this.direction = desired;
    const dt = Math.min(delta, 50);
    this.x = clampX(this.x + (desired === 'left' ? -1 : desired === 'right' ? 1 : 0) * WALK_SPEED * dt / 1000, this.world.location.width);
    this.elapsed += dt;
    if (!this.pending && (desired !== this.lastSentDirection || (desired !== 'idle' && this.elapsed >= 150))) {
      void this.transmit(desired);
    }
  }

  private async transmit(direction: Direction) {
    if (this.pending || this.disposed) return;
    this.elapsed = 0;
    const work = async () => {
      try {
        const next = await this.send(this.world, direction);
        if (this.disposed) return;
        this.world = next;
        this.lastSentDirection = direction;
        // O renderer prevê entre comandos; um stop precisa terminar no ponto canônico.
        this.x = next.player.x;
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
  }

  async stop() {
    this.direction = 'idle';
    await this.pending;
    if (this.lastSentDirection !== 'idle') await this.transmit('idle');
    this.x = this.world.player.x;
  }

  /** Wait for an in-flight intention before accepting a server phase transition. */
  async suspend() {
    this.direction = 'idle';
    await this.pending;
    this.x = this.world.player.x;
  }

  dispose() {this.disposed = true;}
}
