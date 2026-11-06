import {describe, expect, it} from 'vitest';
import type {CaseReport} from '../shared/api';
import {canSubmitCaseReport, caseReportKind, caseReportStatus} from './table-reports';

const report: CaseReport = {
  id: 'statement', npc_id: 'virgilia', npc_name: 'Virgília', subject_id: 'virgilia',
  day: 1, period: 'night', kind: 'alibi', text: 'Estava com Bacamarte.',
  location_id: 'casa_verde', companion_ids: ['bacamarte'], alibi_status: 'accompanied',
  confirmation_status: 'awaiting_confirmation', source_ids: ['shared-encounter'], admissible: false,
};

describe('structured table reports', () => {
  it('keeps waiting confirmation separate from being alone', () => {
    expect(caseReportStatus(report)).toBe('Aguardando a outra confirmação');
    expect(caseReportStatus({...report, confirmation_status: 'confirmed'})).toBe('Álibi confirmado · favorece a pessoa investigada');
    expect(caseReportStatus({...report, confirmation_status: 'alone'})).toBe('Sem companhia durante a noite');
  });
  it('uses eligibility from the backend instead of interpreting words', () => {
    expect(canSubmitCaseReport({...report, text: 'ninguém sozinho sem companhia'})).toBe(false);
    expect(canSubmitCaseReport({...report, text: 'Não falarei disso.', admissible: true})).toBe(true);
  });
  it('distinguishes gossip and witnessed presence in the notebook', () => {
    expect(caseReportKind({...report, kind: 'gossip'})).toBe('Fofoca');
    expect(caseReportKind({...report, kind: 'sighting'})).toBe('Avistamento');
  });
});
