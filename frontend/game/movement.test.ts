import {describe, expect, it, vi} from 'vitest';
import {ApiError, type WorldSnapshot} from '../shared/api';
import {clampX, closestNPC, MovementController, WALK_SPEED} from './movement';

function snapshot(x = 160): WorldSnapshot {
  return {
    game_id: 'game', world_version: '1', revision: 0,
    location: {id: 'praca_verde', name: 'Praça Verde', width: 960, height: 360, ground_y: 300, background: '/scene.png', exits: []},
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
    expect(controller.world.player.x).toBe(202);
    for (let frame = 0; frame < 60; frame++) controller.update(16, 'idle');
    expect(controller.x).toBeCloseTo(202, 1);
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

  it('atualiza a vida dos NPCs sem interromper a caminhada prevista', () => {
    const changed = vi.fn();
    const controller = new MovementController(snapshot(), vi.fn(), vi.fn(), changed, vi.fn());
    controller.x = 207; controller.direction = 'right';
    const social = {...snapshot(), revision: 2, visible_npcs: []};
    expect(controller.observe(social)).toBe(true);
    expect(controller.x).toBe(207);
    expect(controller.direction).toBe('right');
    expect(controller.world.visible_npcs).toEqual([]);
    expect(controller.observe(snapshot())).toBe(false);
    expect(controller.observe({...social, revision: 3, player: {...social.player, movement_seq: 7}})).toBe(false);
  });

  it('descarta observação recebida enquanto um comando aguarda confirmação', async () => {
    let resolve: (world: WorldSnapshot) => void = () => {};
    const send = vi.fn().mockImplementation(() => new Promise<WorldSnapshot>(done => {resolve = done;}));
    const controller = new MovementController(snapshot(), send, vi.fn(), vi.fn(), vi.fn());
    controller.update(16, 'right');
    expect(controller.observe({...snapshot(), revision: 4, visible_npcs: []})).toBe(false);
    resolve({...snapshot(), revision: 1});
    await Promise.resolve(); await Promise.resolve();
    controller.dispose();
  });

  it('reaplica entradas e caminha sem saltos com latência variável de 120 a 600 ms', async () => {
    let now = 0, request = 0, serverX = 160, serverTime = 0;
    let previousDirection = 'idle';
    const delays = [120, 320, 180, 450, 200, 600];
    const events: Array<{at: number; run: () => void}> = [];
    const corrections: number[] = [];
    const send = vi.fn((world: WorldSnapshot, direction: string) => new Promise<WorldSnapshot>(resolve => {
      const rtt = delays[request++ % delays.length];
      events.push({at: now + rtt / 2, run: () => {
        serverX += (previousDirection === 'right' ? 1 : 0) * WALK_SPEED * Math.min(1, (now - serverTime) / 1000);
        serverTime = now; previousDirection = direction;
        const next = {...world, revision: world.revision + 1,
          player: {...world.player, x: serverX, movement_seq: world.player.movement_seq + 1}};
        events.push({at: now + rtt / 2, run: () => {resolve(next);}});
      }});
    }));
    const controller = new MovementController(snapshot(), send, vi.fn(), vi.fn(), vi.fn(), () => now);
    for (now = 0; now <= 2200; now += 10) {
      const beforeReply = controller.x;
      let index: number;
      while ((index = events.findIndex(event => event.at <= now)) >= 0) {
        events.splice(index, 1)[0].run();
        for (let flush = 0; flush < 8; flush++) await Promise.resolve();
      }
      // Replies update the authoritative/predicted positions, never the sprite.
      expect(controller.x).toBe(beforeReply);
      controller.update(10, 'right');
      corrections.push(controller.x - beforeReply);
    }
    expect(send.mock.calls.length).toBeGreaterThan(6);
    expect(Math.min(...corrections)).toBeGreaterThanOrEqual(WALK_SPEED * .01 / 2 - .001);
    expect(Math.max(...corrections)).toBeLessThanOrEqual(WALK_SPEED * .01 * 1.5 + .001);
    expect(controller.x).toBeCloseTo(controller.world.player.x, -2);
    controller.dispose();
  });

  it('limita previsão na desconexão e serializa inversão e parada sem comandos extras', async () => {
    let now = 0;
    let resolve: (world: WorldSnapshot) => void = () => {};
    const send = vi.fn().mockImplementationOnce(() => new Promise<WorldSnapshot>(done => {resolve = done;}))
      .mockImplementation(async (world: WorldSnapshot) => ({...world, revision: world.revision + 1,
        player: {...world.player, movement_seq: world.player.movement_seq + 1, x: 181}}));
    const controller = new MovementController(snapshot(), send, vi.fn(), vi.fn(), vi.fn(), () => now);
    controller.update(10, 'right');
    for (now = 10; now <= 2000; now += 10) controller.update(10, 'right');
    expect(controller.x).toBeLessThanOrEqual(160 + WALK_SPEED * 1.01 + .001);
    const beforeReverse = controller.x;
    controller.update(10, 'left');
    expect(controller.x).toBe(beforeReverse); // No further prediction while disconnected.
    const stopped = controller.stop();
    expect(controller.stop()).toBe(stopped);
    controller.update(10, 'right');
    expect(controller.direction).toBe('idle');
    resolve({...snapshot(160), revision: 1, player: {...snapshot().player, movement_seq: 1}});
    await stopped;
    expect(send.mock.calls.map(call => call[1])).toEqual(['right', 'idle']);
    const before = controller.x;
    now += 16; controller.update(16, 'idle');
    expect(Math.abs(controller.x - before)).toBeLessThanOrEqual(WALK_SPEED / 2 * .016 + .001);
    expect(controller.world.player.x).toBe(181);
    controller.dispose();
  });

  it('reaplica a inversão feita enquanto a primeira intenção aguarda resposta', async () => {
    let now = 0;
    let resolve: (world: WorldSnapshot) => void = () => {};
    const send = vi.fn((_world: WorldSnapshot, _direction: string) => new Promise<WorldSnapshot>(done => {resolve = done;}));
    const controller = new MovementController(snapshot(), send, vi.fn(), vi.fn(), vi.fn(), () => now);
    controller.update(0, 'right');
    now = 100; controller.update(50, 'right');
    now = 150; controller.update(50, 'left');
    now = 200; controller.update(50, 'left');
    const before = controller.x;
    resolve({...snapshot(), revision: 1, player: {...snapshot().player, movement_seq: 1}});
    for (let flush = 0; flush < 8; flush++) await Promise.resolve();
    expect(controller.x).toBe(before);
    now += 16; controller.update(16, 'left');
    // The unconfirmed left input is replayed, pulling the correction left too.
    expect(controller.x).toBeLessThan(before - WALK_SPEED * .016);
    expect(send.mock.calls.map(call => call[1])).toEqual(['right', 'left']);
    controller.dispose();
  });

  it('não recua na borda quando chega uma posição confirmada atrás do sprite', async () => {
    let now = 0;
    let resolve: (world: WorldSnapshot) => void = () => {};
    const send = vi.fn((_world: WorldSnapshot, _direction: string) => new Promise<WorldSnapshot>(done => {resolve = done;}));
    const controller = new MovementController(snapshot(927), send, vi.fn(), vi.fn(), vi.fn(), () => now);
    controller.update(16, 'right');
    expect(controller.x).toBe(928);
    now = 200;
    resolve({...snapshot(900), revision: 1, player: {...snapshot(900).player, movement_seq: 1}});
    for (let flush = 0; flush < 8; flush++) await Promise.resolve();
    now += 16; controller.update(16, 'right');
    expect(controller.x).toBe(928);
    controller.dispose();
  });
});
