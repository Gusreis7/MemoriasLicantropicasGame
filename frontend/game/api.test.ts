import {afterEach, describe, expect, it, vi} from 'vitest';
import {api, ApiError, request, type WorldSnapshot} from '../shared/api';

afterEach(() => vi.unstubAllGlobals());

describe('contratos HTTP do jogo', () => {
  it('abre debate com discurso e referências, e conclui sem permitir votos escolhidos pelo cliente', async () => {
    const fetch = vi.fn().mockImplementation(() => Promise.resolve(new Response('{}', {status: 200})));
    vi.stubGlobal('fetch', fetch);
    await api.openAssembly('case', 'capitu', ['ev'], ['statement'], 'Ouçam o que encontrei.');
    expect(fetch.mock.calls[0][0]).toBe('/api/v1/games/case/assembly/open');
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({suspect_id: 'capitu', evidence_ids: ['ev'], testimony_ids: ['statement'], speech: 'Ouçam o que encontrei.'});
    await api.resolveAssembly('case', 'Peço que reconsiderem.');
    expect(fetch.mock.calls[1][0]).toBe('/api/v1/games/case/assembly/resolve');
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({reply: 'Peço que reconsiderem.'});
  });

  it('interroga um período e confronta com referências sem escolher confissão ou culpa', async () => {
    const fetch = vi.fn().mockImplementation(() => Promise.resolve(new Response('{}', {status: 200})));
    vi.stubGlobal('fetch', fetch);
    await api.interrogate('case', 'capitu', 0, 'night');
    expect(fetch.mock.calls[0][0]).toBe('/api/v1/games/case/interrogations');
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({npc_id: 'capitu', day: 0, period: 'night'});
    await api.confront('case', 'capitu', ['ev'], ['statement'], ['alibi']);
    expect(fetch.mock.calls[1][0]).toBe('/api/v1/games/case/confrontations');
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({npc_id: 'capitu', evidence_ids: ['ev'], testimony_ids: ['statement'], interrogation_ids: ['alibi']});
  });
  it('consulta apenas relatos ouvidos pelo jogador, sem pedir estado social privado', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('{"reports":[]}', {status: 200}));
    vi.stubGlobal('fetch', fetch);
    await expect(api.reports('game-id')).resolves.toEqual({reports: []});
    expect(fetch.mock.calls[0][0]).toBe('/api/v1/games/game-id/social/reports');
    expect(fetch.mock.calls[0][1].method).toBe('GET');
  });
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

  it('preserva o código seguro do provedor sem tratar toda indisponibilidade como erro de conversa', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({
      detail: 'Não foi possível renovar a autorização.', code: 'llm_credentials_unavailable',
    }), {status: 503})).mockResolvedValueOnce(new Response(JSON.stringify({detail: 'Persistência indisponível.'}), {status: 503}));
    vi.stubGlobal('fetch', fetch);
    await expect(api.send('game', 'conversation', 'Olá')).rejects.toMatchObject({
      status: 503, code: 'llm_credentials_unavailable', message: 'Não foi possível renovar a autorização.',
    });
    await expect(api.world('game')).rejects.toMatchObject({status: 503, code: undefined, message: 'Persistência indisponível.'});
  });

  it('não repete envio quando a rede falha', async () => {
    const fetch = vi.fn().mockRejectedValue(new TypeError('network failure'));
    vi.stubGlobal('fetch', fetch);
    await expect(api.send('game', 'conversation', 'Olá')).rejects.toBeInstanceOf(ApiError);
    expect(fetch).toHaveBeenCalledOnce();
  });

  it('busca e apresenta vestígios sem escolher dono, reconhecimento ou fase', async () => {
    const fetch = vi.fn().mockImplementation(() => Promise.resolve(new Response('{}', {status: 200})));
    vi.stubGlobal('fetch', fetch);
    await api.search('game-id', 'crime-id');
    expect(fetch.mock.calls[0][0]).toBe('/api/v1/games/game-id/crime-scenes/crime-id/search');
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({});
    await api.present('game-id', 'evidence-id', 'capitu');
    expect(fetch.mock.calls[1][0]).toBe('/api/v1/games/game-id/evidence/evidence-id/present');
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({npc_id: 'capitu'});
    await api.accuse('game-id', 'capitu', ['evidence-id'], ['testimony-id']);
    expect(JSON.parse(fetch.mock.calls[2][1].body)).toEqual({suspect_id: 'capitu', evidence_ids: ['evidence-id'], testimony_ids: ['testimony-id']});
  });
  it('examina um vestígio enviando corpo vazio e recebe o caderno atualizado', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('{"inventory":[{"id":"ev","examined":true,"inspection_text":"Uma marca de tinta."}]}', {status: 200}));
    vi.stubGlobal('fetch', fetch);
    await expect(api.inspectEvidence('game-id', 'ev')).resolves.toMatchObject({inventory: [{examined: true, inspection_text: 'Uma marca de tinta.'}]});
    expect(fetch.mock.calls[0][0]).toBe('/api/v1/games/game-id/evidence/ev/inspect');
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({});
  });
});
