import type {PublicCharacter} from './api';

// Metadata is public identity, never inferred from a name, portrait or secret role.
export function personWords(character?: Partial<PublicCharacter>) {
  if (character?.grammatical_gender === 'feminine') return {accused: 'A acusada', release: 'solta', expelled:'Expulsa', deceased:'Falecida', alive:'Viva'};
  if (character?.grammatical_gender === 'masculine') return {accused: 'O acusado', release: 'solto', expelled:'Expulso', deceased:'Falecido', alive:'Vivo'};
  // Old saved clients/fixtures may not have the additive field yet.
  return {accused: 'A pessoa acusada', release: 'posta em liberdade', expelled:'Fora da cidade', deceased:'Sem vida', alive:'Com vida'};
}
