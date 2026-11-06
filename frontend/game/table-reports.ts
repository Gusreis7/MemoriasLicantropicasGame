import type {CaseReport} from '../shared/api';

const KIND_LABELS: Record<CaseReport['kind'], string> = {
  alibi: 'Álibi', sighting: 'Avistamento', suspicion: 'Suspeita', gossip: 'Fofoca',
  secret: 'Confidência', public_fact: 'Informação pública',
};

const STATUS_LABELS: Record<CaseReport['confirmation_status'], string> = {
  confirmed: 'Álibi confirmado · favorece a pessoa investigada', awaiting_confirmation: 'Aguardando a outra confirmação',
  alone: 'Sem companhia durante a noite', partial: 'Companhia em parte da noite',
  unavailable: 'Informação indisponível', reported: 'Relato registrado',
};

export function caseReportKind(report: CaseReport) {return KIND_LABELS[report.kind];}
export function caseReportStatus(report: CaseReport) {return STATUS_LABELS[report.confirmation_status];}

/** Dossier eligibility comes from the server, never from the wording of a reply. */
export function canSubmitCaseReport(report: CaseReport) {return report.admissible;}
