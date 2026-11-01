import {describe, expect, it, vi} from 'vitest';
import {ApiError, type WorldSnapshot} from '../shared/api';
import {clampX, closestNPC, MovementController} from './movement';

function snapshot(x = 160): WorldSnapshot {
  return {
    game_id: 'game', world_version: '1', revision: 0,
    location: {id: 'praca_verde', name: 'Praça Verde', width: 1920, height: 360, ground_y: 300, background: '/scene.png'},
    player: {location_id: 'praca_verde', x, facing: 'right', movement_seq: 0},
    visible_npcs: [{npc_id: 'rubiao', name: 'Rubião', x: 440, sprite_id: 'rubiao', can_approach: false}],
    travel_targets: ['cabana_capitu'],
  };
}

describe('movimento e abordagem', () => {
  it('respeita limites e só seleciona um morador ao alcance', () => {
    expect(clampX(-100, 1920)).toBe(32);
    expect(clampX(3000, 1920)).toBe(1888);
    expect(closestNPC(snapshot(), 160)).toBeUndefined();
    expect(closestNPC(snapshot(), 400)?.npc_id).toBe('rubiao');
  });

  it('mantém apenas um comando em andamento e confirma parada antes de abordar', async () => {
    let resolve: (world: WorldSnapshot) => void = () => {};
    const send = vi.fn().mockImplementationOnce(() => new Promise<WorldSnapshot>(done => {resolve = done;}))
      .mockImplementation(async (world, direction) => ({...world, revision: world.revision + 1,
        player: {...world.player, movement_seq: world.player.movement_seq + 1, x: 202}}));
    const controller = new MovementController(snapshot(), send, vi.fn(), vi.fn(), vi.fn());
    controller.update(16, 'right');
    controller.update(200, 'right');
    expect(send).toHaveBeenCalledTimes(1);
    const stopped = controller.stop();
    resolve({...snapshot(202), revision: 1, player: {...snapshot(202).player, movement_seq: 1}});
    await stopped;
    expect(send).toHaveBeenCalledTimes(2);
    expect(send.mock.calls[1][1]).toBe('idle');
    expect(controller.x).toBe(202);
  });

  it('recupera snapshot após conflito de revisão sem reenviar o comando automaticamente', async () => {
    const refresh = vi.fn().mockResolvedValue({...snapshot(220), revision: 3});
    const changed = vi.fn();
    const send = vi.fn().mockRejectedValue(new ApiError(409, 'Conflito'));
    const controller = new MovementController(snapshot(), send, refresh, changed, vi.fn());
    controller.update(16, 'right');
    await controller.stop();
    expect(refresh).toHaveBeenCalledOnce();
    expect(send).toHaveBeenCalledOnce();
    expect(controller.world.revision).toBe(3);
    expect(controller.x).toBe(220);
  });

  it('aplica a sequência recebida após viagem em vez de voltar para zero', () => {
    const controller = new MovementController(snapshot(), vi.fn(), vi.fn(), vi.fn(), vi.fn());
    const target = {...snapshot(), revision: 4, player: {...snapshot().player, movement_seq: 8}};
    controller.accept(target);
    expect(controller.world.player.movement_seq).toBe(8);
    expect(controller.direction).toBe('idle');
  });
});
