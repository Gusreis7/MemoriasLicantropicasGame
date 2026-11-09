"""Bound, read-only queries into the authoritative table for a persona turn."""

from dataclasses import dataclass
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from src.contracts.table import TableStatement
from src.modules.agents.support import is_alibi_question, is_greeting
from src.textutils import normalize, word_tokens


@dataclass(frozen=True)
class PreparedTableTurn:
    statements: tuple[TableStatement, ...]
    text: str
    topic_status: Literal["information", "unknown", "exhausted"] = "information"


@dataclass(frozen=True)
class BoundGameAgent:
    """One server-selected persona; query arguments can never select another actor."""
    game_id: object
    npc_id: str
    recipient_id: str
    case: object
    names: dict
    now: object

    @property
    def tools(self):
        return ('consultar_meu_alibi', 'consultar_minhas_observacoes', 'consultar_informacoes_publicas')

    def my_alibi(self, day):
        from src.modules.table.rules import alibi_statement
        if day < 0 or day >= self.case.day:
            return None
        return alibi_statement(self.game_id, self.case.table, self.npc_id, day,
            self.names, self.now, recipient_id=self.recipient_id)

    def my_observations(self, day=None):
        from src.modules.table.rules import sighting_statements
        return sighting_statements(self.game_id, self.case.table, self.npc_id,
            self.names, self.now, recipient_id=self.recipient_id, day=day)

    def public_deaths(self, text):
        return tuple(crime for crime in self.case.crimes
                     if normalize(self.names.get(crime.victim_id, crime.victim_id)) in text)


class GameTableService:
    def __init__(self, turns, characters, knowledge):
        self.turns, self.characters, self.knowledge = turns, characters, knowledge

    async def prepare(self, game_id, npc_id, recipient_id, question):
        from src.modules.table.rules import alibi_statement, sighting_statements
        from src.modules.agents.table_agent import prepare_knowledge_turn

        case = await self.turns.require_day_locked(game_id)
        now = self.turns.now()
        names = {p.id: p.name for p in await self.characters.list()}
        names['bras_cubas'] = 'Brás Cubas'
        agent = BoundGameAgent(game_id, npc_id, recipient_id, case, names, now)
        text = normalize(question)
        tokens = set(word_tokens(text))
        disclosed = {item.id for item in case.table.statements
                     if item.speaker_id == npc_id and item.recipient_id == recipient_id}
        repeat_requested = bool(tokens & {'repita', 'repetir', 'relembre', 'recapitule'})

        def deliver(statements):
            fresh = tuple(item for item in statements if repeat_requested or item.id not in disclosed)
            if not fresh:
                return PreparedTableTurn((), 'Não sei de mais nada sobre esse assunto, Floriano. Podemos falar de outra coisa?', 'exhausted')
            return PreparedTableTurn(fresh, ' '.join(item.text for item in fresh))

        # The date refers to game time. A persona cannot select another night.
        confirmation = any(token.startswith('confirm') for token in tokens) and bool(tokens & {'com', 'companhia', 'noite', 'ontem', 'alibi', 'juntos', 'juntas'})
        company_question = bool(tokens & {'noite', 'ontem', 'anteontem'} and tokens & {'com', 'companhia', 'juntos', 'juntas', 'dormiu', 'dormia'})
        if is_alibi_question(question) or confirmation or company_question or (tokens & {'alibi', 'dormiu', 'dormi', 'companhia'} and tokens & {'noite', 'ontem', 'confirmar', 'seu', 'sua'}):
            day = max(0, case.day - 1)
            ordered = word_tokens(text)
            explicit = next((int(ordered[i + 1]) for i, token in enumerate(ordered[:-1])
                             if token in {'dia', 'noite'} and ordered[i + 1].isdigit()), None)
            if explicit is not None:
                day = explicit
            elif 'anteontem' in tokens:
                day = max(0, case.day - 2)
            elif not tokens & {'ontem', 'anteontem'}:
                matched = [crime.day for crime in case.crimes
                           if normalize(names.get(crime.victim_id, crime.victim_id)) in text]
                if matched:
                    day = max(matched)
            statement = agent.my_alibi(day)
            if statement is None:
                return PreparedTableTurn((), 'Essa noite ainda não foi resolvida. Pergunte por uma noite passada.')
            return deliver((statement,))

        if tokens & {'viu', 'presenciou', 'suspeita', 'suspeito', 'desconfia', 'lobisomem', 'fera', 'culpado', 'assassino'}:
            sightings = agent.my_observations()
            if sightings:
                return deliver(sightings)

        if tokens & {'morreu', 'faleceu', 'morte', 'morto', 'morta', 'matou', 'assassinato'}:
            crimes = agent.public_deaths(text)
            if crimes:
                statements = []
                for crime in crimes[-2:]:
                    root = uuid5(NAMESPACE_URL, f'{game_id}:public-death:{crime.id}')
                    statements.append(TableStatement(id=uuid5(NAMESPACE_URL, f'{root}:{npc_id}:{recipient_id}'),
                        kind='public_fact', speaker_id=npc_id, recipient_id=recipient_id, subject_id=crime.victim_id,
                        day=crime.day, period='night', source_ids=(root,), root_id=root,
                        text=f"A morte de {names.get(crime.victim_id, crime.victim_id)} foi anunciada no jornal. É uma notícia triste para a cidade.", created_at=now))
                return deliver(tuple(statements))

        if tokens & {'objeto', 'peca', 'pertence', 'dono', 'reconhece', 'vestigio'}:
            evidence_id = case.active_evidence_by_npc.get(npc_id)
            testimony = next((item for item in reversed(case.testimonies)
                              if item.witness_id == npc_id and item.evidence_id == evidence_id), None)
            if testimony:
                return PreparedTableTurn((), testimony.text)

        statements = await prepare_knowledge_turn(self.knowledge, game_id, npc_id, recipient_id, question, now, excluded_statement_ids=() if repeat_requested else disclosed)
        if statements:
            if all(item.kind == 'public_fact' and not item.source_ids
                   and item.text.startswith(('Não tenho nada concreto', 'Não tenho uma suspeita pessoal', 'Não conheço um relato'))
                   for item in statements):
                return PreparedTableTurn((), 'Não sei dizer sobre esse assunto, Floriano. Podemos conversar sobre outra coisa?', 'unknown')
            return deliver(statements)
        if is_greeting(question):
            return PreparedTableTurn((), 'Bom dia, Floriano. O que deseja esclarecer?')
        if tokens & {'acredita', 'crenca'} and tokens & {'lobisomem', 'lobisomens'}:
            return PreparedTableTurn((), 'Tenho minhas dúvidas, detetive. Prefiro que investiguemos o que de fato aconteceu.')
        return PreparedTableTurn((), 'Não sei dizer sobre esse assunto, Floriano. Podemos conversar sobre outra coisa?', 'unknown')
