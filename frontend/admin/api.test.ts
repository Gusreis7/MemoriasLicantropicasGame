import {afterEach, describe, expect, it, vi} from 'vitest';
import {ApiError, deathAuthor, eventDetails, formatDate, request} from './api';

afterEach(() => vi.unstubAllGlobals());

describe('contrato HTTP admin', () => {
  it('envia credenciais em JSON com cookie de mesma origem e sem cache', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({username: 'admin'}), {status: 200}));
    vi.stubGlobal('fetch', fetcher);
    await expect(request('/auth/login', {username: 'admin', password: 'test-only-password'})).resolves.toEqual({username: 'admin'});
    const [url, options] = fetcher.mock.calls[0];
    expect(url).toBe('/admin/api/v1/auth/login');
    expect(options.method).toBe('POST');
    expect(options.credentials).toBe('same-origin');
    expect(options.cache).toBe('no-store');
    expect(JSON.parse(options.body)).toEqual({username: 'admin', password: 'test-only-password'});
    expect(url).not.toContain('password');
  });

  it('preserva 401 para a UI invalidar a sessão sem expor payload de erro', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('private-backend-detail', {status: 401})));
    await expect(request('/games')).rejects.toMatchObject({status: 401});
    await expect(request('/games')).rejects.not.toThrow('private-backend-detail');
  });

  it('apresenta limite de tentativas sem repetir login automaticamente', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response('', {status: 429}));
    vi.stubGlobal('fetch', fetcher);
    await expect(request('/auth/login', {})).rejects.toThrow('Muitas tentativas');
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('traduz falha de rede', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('private-network-details')));
    await expect(request('/health')).rejects.toBeInstanceOf(ApiError);
    await expect(request('/health')).rejects.not.toThrow('private-network-details');
  });

  it('aceita logout sem conteúdo', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, {status: 204})));
    await expect(request('/auth/logout', {})).resolves.toBeUndefined();
  });
});

describe('autoria e eventos', () => {
  it('não atribui autoria desconhecida a um personagem', () => {
    expect(deathAuthor({victim_id: 'bras_cubas', killer_id: 'capitu', attribution: 'unknown', source: 'scenario'})).toBe('Autoria não registrada');
    expect(deathAuthor({victim_id: 'bras_cubas', killer_id: null, attribution: 'unknown', source: 'scenario'})).toBe('Autoria não registrada');
  });

  it('exibe autor quando registrado pelo sistema', () => {
    expect(deathAuthor({victim_id: 'rubiao', killer_id: 'virgilia', attribution: 'confirmed', source: 'rules'})).toBe('Virgília Neves');
  });

  it('mantém a morte inicial sem autoria', () => {
    const details = eventDetails({id: 'test', type: 'story.initial_death', occurred_at: '', source: 'scenario', data: {victim_id: 'bras_cubas', killer_id: null}});
    expect(details).toContain('Brás Cubas');
    expect(details).toContain('Autoria não registrada');
  });

  it('trata data inválida sem quebrar o painel', () => {
    expect(formatDate('not-a-date')).toBe('Data não registrada');
  });
});
