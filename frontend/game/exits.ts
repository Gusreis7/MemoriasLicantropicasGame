import type {Direction, ExitSide, WorldSnapshot} from '../shared/api';

/** One invitation per visit to the boundary; cancelling requires walking back in. */
export class ExitBoundary {
  private locationID = '';
  private armed = true;

  observe(world: WorldSnapshot, predictedX: number, direction: Direction): ExitSide | null {
    if (this.locationID !== world.location.id) {
      this.locationID = world.location.id;
      this.armed = true;
    }
    const width = world.location.width;
    if (predictedX > 72 && predictedX < width - 72) this.armed = true;
    if (!this.armed) return null;
    // Prediction alone cannot authorize travel: wait for the authoritative position.
    const side = direction === 'left' && predictedX <= 33 && world.player.x <= 56 ? 'left'
      : direction === 'right' && predictedX >= width - 33 && world.player.x >= width - 56 ? 'right' : null;
    if (!side) return null;
    this.armed = false;
    return side;
  }
}
