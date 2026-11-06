import type {CaseEvidence, CaseTestimony} from '../shared/api';

/** Every selected object testimony carries a collected exemplar of its item type. */
export function dossierEvidence(inventory: CaseEvidence[], testimonies: CaseTestimony[], evidenceIDs: string[], testimonyIDs: string[]): string[] {
  const selected = new Set(evidenceIDs);
  const selectedTypes = new Set(inventory.filter(item => selected.has(item.id)).map(item => item.item_id));
  for (const testimony of testimonies) {
    if (!testimonyIDs.includes(testimony.id)) continue;
    const original = inventory.find(item => item.id === testimony.evidence_id);
    if (!original || selectedTypes.has(original.item_id)) continue;
    const exemplar = inventory.find(item => item.item_id === original.item_id)!;
    selected.add(exemplar.id); selectedTypes.add(exemplar.item_id);
  }
  return [...selected];
}
