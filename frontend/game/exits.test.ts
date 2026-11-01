import {describe, expect, it} from 'vitest';
import type {WorldSnapshot} from '../shared/api';
import {ExitBoundary} from './exits';

function world(x = 160): WorldSnapshot {
  return {
    game_id: 'game', world_version: '1', revision: 0,
    location: {id: 'praca_verde', name: 'Praça Verde', width: 960, height: 360, ground_y: 300, background: '/scene.png',
      exits: [{side: 'left', target_location_id: 'cabana_capitu', arrival_side: 'right'},
        {side: 'left', target_location_id: 'cafe_largo', arrival_side: 'right'},
        {side: 'right', target_location_id: 'casa_verde', arrival_side: 'left'}]},
    player: {location_id: 'praca_verde', x, facing: 'right', movement_seq: 0}, visible_npcs: [], travel_targets: [],
  };
}

describe('saídas de rua', () => {
  it('aguarda a posição confirmada antes de oferecer a passagem', () => {
    const edge = new ExitBoundary();
    expect(edge.observe(world(80), 32, 'left')).toBeNull();
    expect(edge.observe(world(45), 32, 'left')).toBe('left');
  });

  it('oferece cada borda apenas uma vez até o jogador se afastar dela', () => {
    const edge = new ExitBoundary();
    expect(edge.observe(world(32), 32, 'left')).toBe('left');
    expect(edge.observe(world(32), 32, 'left')).toBeNull();
    expect(edge.observe(world(50), 60, 'right')).toBeNull();
    expect(edge.observe(world(32), 32, 'left')).toBeNull();
    expect(edge.observe(world(90), 90, 'right')).toBeNull();
    expect(edge.observe(world(32), 32, 'left')).toBe('left');
  });

  it('não oferece viagem ao ficar parado nem ao andar para dentro', () => {
    const edge = new ExitBoundary();
    expect(edge.observe(world(32), 32, 'idle')).toBeNull();
    expect(edge.observe(world(32), 32, 'right')).toBeNull();
    expect(edge.observe(world(928), 928, 'right')).toBe('right');
  });

  it('permite a outra ponta mesmo sem ligações e não reabre a escolha ao chegar', () => {
    const edge = new ExitBoundary();
    const next = world(928); next.location.exits = [];
    expect(edge.observe(next, 928, 'right')).toBe('right');
    next.location.id = 'casa_verde'; next.player.x = 96; next.location.exits = world().location.exits;
    expect(edge.observe(next, 96, 'idle')).toBeNull();
    expect(edge.observe({...next, player: {...next.player, x: 32}}, 32, 'left')).toBe('left');
  });
});
