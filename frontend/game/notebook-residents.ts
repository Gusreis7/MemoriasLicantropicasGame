import type {GamePublic, JournalEdition} from '../shared/api';

/** Notebook-only roster: the first victim is a memorial entry, never a suspect. */
export function notebookResidents(
  cast: GamePublic['characters'],
  journal: readonly JournalEdition[],
): GamePublic['characters'] {
  const initialVictim = journal.find(edition => edition.day === 1 && edition.victim_id === 'bras_cubas');
  if (!initialVictim) return [...cast];
  return [
    {character: {id: 'bras_cubas', name: initialVictim.victim_name || 'Brás Cubas', grammatical_gender: 'masculine'}, alive: false},
    ...cast.filter(member => member.character.id !== 'bras_cubas'),
  ];
}
