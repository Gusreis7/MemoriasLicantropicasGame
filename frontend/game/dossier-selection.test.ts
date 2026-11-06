import {describe, expect, it} from 'vitest';
import type {CaseEvidence, CaseTestimony} from '../shared/api';
import {dossierEvidence} from './dossier-selection';

const inventory = [{id: 'first', item_id: 'cordel'}, {id: 'copy', item_id: 'cordel'}, {id: 'other', item_id: 'fita'}] as CaseEvidence[];
const testimonies = [{id: 't', evidence_id: 'copy'}] as CaseTestimony[];

describe('object testimony dependencies', () => {
  it('attaches the visible exemplar when a testimony is selected', () => {
    expect(dossierEvidence(inventory, testimonies, [], ['t'])).toEqual(['first']);
  });
  it('preserves an already selected equivalent copy without duplicates', () => {
    expect(dossierEvidence(inventory, testimonies, ['copy', 'other'], ['t', 't'])).toEqual(['copy', 'other']);
  });
  it('does not attach objects for unselected testimonies or table reports', () => {
    expect(dossierEvidence(inventory, testimonies, [], ['alibi-id'])).toEqual([]);
  });
});
