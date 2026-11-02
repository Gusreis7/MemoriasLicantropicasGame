import {describe, expect, it, vi} from 'vitest';
import {ApiError, type Message} from '../shared/api';
import {findConfirmedExchange, sendDialogue} from './dialogue';

const question = 'O que Virgília lhe contou?';
const message = (id: string, speaker: 'player' | 'npc', content: string): Message =>
  ({id, speaker, content, created_at: '2026-11-01T12:00:00Z'});
const incoming = message('incoming', 'player', question);
const reply = message('reply', 'npc', 'Ela me contou apenas uma versão, detetive.');

describe('confirmação de envio da conversa', () => {
  it('mantém a resposta recebida mesmo se a atualização posterior do histórico falhar', async () => {
    const onConfirmed = vi.fn();
    const send = vi.fn().mockResolvedValue(reply);
    const history = vi.fn().mockRejectedValue(new ApiError(503, 'Histórico indisponível.'));
    const result = await sendDialogue({content: question, baseline: [], send, history, onConfirmed});
    expect(result.outcome).toBe('confirmed');
    expect(result.clearDraft).toBe(true);
    expect(result.messages.map(item => item.content)).toEqual([question, reply.content]);
    expect(result.status).toContain('Resposta recebida');
    expect(onConfirmed).toHaveBeenCalledOnce();
    expect(send).toHaveBeenCalledOnce();
  });

  it('mostra a resposta imediatamente, antes da leitura adicional terminar', async () => {
    let resolve: (messages: Message[]) => void = () => {};
    const history = vi.fn().mockImplementation(() => new Promise<Message[]>(done => {resolve = done;}));
    const onConfirmed = vi.fn();
    const pending = sendDialogue({content: question, baseline: [], send: async () => reply, history, onConfirmed});
    await Promise.resolve();
    expect(onConfirmed).toHaveBeenCalledOnce();
    resolve([incoming, reply]);
    expect((await pending).messages).toEqual([incoming, reply]);
  });

  it('preserva o erro específico de credenciais e o rascunho quando nada foi confirmado', async () => {
    const send = vi.fn().mockRejectedValue(new ApiError(503,
      'O serviço de conversa está sem credenciais.', 'llm_credentials_missing'));
    const result = await sendDialogue({content: question, baseline: [], send, history: async () => []});
    expect(result.outcome).toBe('failed');
    expect(result.clearDraft).toBe(false);
    expect(result.status).toContain('sem credenciais');
    expect(result.messages).toEqual([]);
    expect(send).toHaveBeenCalledOnce();
  });

  it('recupera um ACK perdido pelo par novo no histórico sem repetir a pergunta', async () => {
    const send = vi.fn().mockRejectedValue(new ApiError(0, 'Conexão interrompida.'));
    const result = await sendDialogue({content: question, baseline: [], send,
      history: async () => [incoming, reply]});
    expect(result).toMatchObject({outcome: 'confirmed', clearDraft: true, messages: [incoming, reply]});
    expect(result.status).toContain('encontrada no histórico');
    expect(send).toHaveBeenCalledOnce();
  });

  it('não confunde uma resposta antiga à mesma pergunta com uma nova confirmação', async () => {
    const baseline = [incoming, reply];
    expect(findConfirmedExchange(baseline, baseline, question)).toBe(false);
    const send = vi.fn().mockRejectedValue(new ApiError(503, 'A resposta excedeu o prazo.', 'llm_timeout'));
    const result = await sendDialogue({content: question, baseline, send, history: async () => baseline});
    expect(result).toMatchObject({outcome: 'failed', clearDraft: false, messages: baseline});
    expect(result.status).toContain('excedeu o prazo');
  });

  it('mantém o rascunho e informa incerteza quando envio e leitura falham', async () => {
    const send = vi.fn().mockRejectedValue(new ApiError(0, 'Conexão interrompida.'));
    const history = vi.fn().mockRejectedValue(new ApiError(503, 'Histórico indisponível.'));
    const result = await sendDialogue({content: question, baseline: [], send, history});
    expect(result).toMatchObject({outcome: 'uncertain', clearDraft: false, messages: []});
    expect(result.status).toContain('confirmar o envio');
    expect(result.status).toContain('antes de enviar novamente');
    expect(send).toHaveBeenCalledOnce();
    expect(history).toHaveBeenCalledOnce();
  });

  it('preserva a resposta confirmada quando uma leitura atrasada ainda não a inclui', async () => {
    const result = await sendDialogue({content: question, baseline: [], send: async () => reply, history: async () => []});
    expect(result.outcome).toBe('confirmed');
    expect(result.messages.at(-1)?.id).toBe(reply.id);
    expect(result.clearDraft).toBe(true);
  });
});

it('uma rejeição de disponibilidade bloqueia o chat sem confundir com resposta perdida', async () => {
  const send = vi.fn().mockRejectedValue(new ApiError(403, 'O personagem saiu deste local.', 'npc_away'));
  const history = vi.fn();
  const result = await sendDialogue({content: question, baseline: [], send, history});
  expect(result.blocked).toBe(true);
  expect(result.clearDraft).toBe(false);
  expect(result.status).toContain('saiu deste local');
  expect(result.status).not.toContain('Ainda não há resposta');
  expect(history).not.toHaveBeenCalled();
  expect(send).toHaveBeenCalledOnce();
});
