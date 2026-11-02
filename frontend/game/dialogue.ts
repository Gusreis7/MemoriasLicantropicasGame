import {ApiError, type Message} from '../shared/api';

export interface DialogueResult {
  blocked?: boolean;
  outcome: 'confirmed' | 'failed' | 'uncertain';
  messages: Message[];
  clearDraft: boolean;
  status: string;
}

/** A lost acknowledgement may still have committed the complete exchange. */
export function findConfirmedExchange(history: Message[], baseline: Message[], question: string): boolean {
  const knownIDs = new Set(baseline.map(message => message.id));
  return history.some((message, index) => message.speaker === 'player'
    && message.content.trim() === question.trim() && !knownIDs.has(message.id)
    && history[index + 1]?.speaker === 'npc' && !knownIDs.has(history[index + 1].id));
}

export async function sendDialogue(options: {
  content: string;
  baseline: Message[];
  send: () => Promise<Message>;
  history: () => Promise<Message[]>;
  onConfirmed?: (messages: Message[]) => void;
  now?: () => string;
}): Promise<DialogueResult> {
  const {content, baseline, send, history, onConfirmed} = options;
  let reply: Message;
  try {
    reply = await send();
  } catch (error) {
    // Uma rejeição explícita precede a inferência/persistência. Não é uma confirmação perdida.
    if (error instanceof ApiError && (error.status === 403 || error.status === 404)) {
      const detail = error.message === 'Acesso não permitido.' ? 'Esta conversa não está mais disponível. Feche e aborde o personagem novamente.' : error.message;
      return {outcome:'failed', blocked:true, messages:baseline, clearDraft:false,
        status:`${detail} Seu rascunho foi mantido.`};
    }
    let recovered: Message[];
    try {recovered = await history();}
    catch {
      const detail = error instanceof ApiError && error.status > 0 ? `${error.message} ` : '';
      return {outcome: 'uncertain', messages: baseline, clearDraft: false,
        status: `${detail}Não foi possível consultar o histórico para confirmar o envio. Seu rascunho foi mantido; reabra a conversa e confira antes de enviar novamente.`};
    }
    if (findConfirmedExchange(recovered, baseline, content)) {
      onConfirmed?.(recovered);
      return {outcome: 'confirmed', messages: recovered, clearDraft: true,
        status: 'A resposta foi encontrada no histórico. A conversa está atualizada.'};
    }
    const detail = error instanceof ApiError && error.status > 0 ? error.message : 'A conexão foi interrompida durante o envio.';
    return {outcome: 'failed', messages: recovered, clearDraft: false,
      status: `${detail} Ainda não há resposta registrada para esta pergunta. Seu rascunho foi mantido.`};
  }

  // POST já confirmou a resposta. Uma falha na leitura seguinte não desfaz esse sucesso.
  const confirmed = [...baseline, {id: `confirmed-question:${reply.id}`, speaker: 'player' as const,
    content, created_at: (options.now ?? (() => new Date().toISOString()))()}, reply];
  onConfirmed?.(confirmed);
  try {
    const refreshed = await history();
    if (refreshed.some(message => message.id === reply.id)) {
      return {outcome: 'confirmed', messages: refreshed, clearDraft: true, status: ''};
    }
  } catch { /* A resposta confirmada segue visível enquanto o histórico não chega. */ }
  return {outcome: 'confirmed', messages: confirmed, clearDraft: true,
    status: 'Resposta recebida. O histórico completo não pôde ser atualizado agora.'};
}
