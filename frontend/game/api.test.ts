import {afterEach, describe, expect, it, vi} from 'vitest';
import {api, ApiError, request, type WorldSnapshot} from '../shared/api';

afterEach(() => vi.unstubAllGlobals());

describe('contratos HTTP do jogo', () => {
  it('aborda enviando somente a persona e envia somente texto na conversa', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('{}', {status: 200}));
    vi.stubGlobal('fetch', fetch);
    await api.approach('game-id', 'capitu');
    expect(fetch.mock.calls[0][0]).toBe('/api/v1/games/game-id/approaches');
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({npc_id: 'capitu'});
    fetch.mockResolvedValue(new Response('{}', {status: 200}));
    await api.send('game-id', 'conversation-id', 'O que viu?');
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({content: 'O que viu?'});
    expect(fetch.mock.calls[1][1].credentials).toBe('same-origin');
  });

  it('diferencia uma saída a pé da viagem pelo mapa sem escolher a posição de chegada', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('{}', {status: 200}));
    vi.stubGlobal('fetch', fetch);
    const world = {game_id: 'game-id', revision: 7} as WorldSnapshot;
    await api.travel(world, 'cabana_capitu', 'left');
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({target_location_id: 'cabana_capitu', revision: 7, exit_side: 'left'});
    fetch.mockResolvedValue(new Response('{}', {status: 200}));
    await api.travel(world, 'casa_verde');
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({target_location_id: 'casa_verde', revision: 7});
  });

  it('preserva status HTTP para recuperar conflitos e indisponibilidade', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({detail: 'Estado mudou'}), {status: 409})));
    await expect(request('/api/v1/games/game/world')).rejects.toMatchObject({status: 409, message: 'Estado mudou'});
  });

  it('não repete envio quando a rede falha', async () => {
    const fetch = vi.fn().mockRejectedValue(new TypeError('network failure'));
    vi.stubGlobal('fetch', fetch);
    await expect(api.send('game', 'conversation', 'Olá')).rejects.toBeInstanceOf(ApiError);
    expect(fetch).toHaveBeenCalledOnce();
  });
});
