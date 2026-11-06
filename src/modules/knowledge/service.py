"""Knowledge access and disclosure are rules; free text is only attributed testimony."""

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from src.contracts.errors import AccessDeniedError
from src.contracts.social import KnowledgeEntry
from src.modules.agents.guard import DialogueGuard, SAFE_DIALOGUE_REPLY
from src.modules.knowledge.rules import apply_relationship, initial_relationships, relationship_for
from src.modules.knowledge.seeds import TOPICS, seed_social_state
from src.modules.knowledge.mechanics import can_share
from src.textutils import normalize, word_tokens


def attributed_utterance(content: str, speaker_name: str, listener_name: str) -> str:
    return f"{speaker_name} disse a {listener_name}: «{content}»"


class KnowledgeService:
    def __init__(self, repository, characters, llm=None, clock=None):
        self._repository, self._characters = repository, characters
        # Kept as dependency metadata only; extraction has no authority to write knowledge.
        self._llm = llm
        self._clock = clock or (lambda: datetime.now(UTC))
        self._guard = DialogueGuard()

    async def _snapshot(self, game_id, npc_id, recipient_id="player"):
        profiles = await self._characters.list()
        ids = {profile.id for profile in profiles}
        if npc_id not in ids or recipient_id not in ids | {"player"}:
            raise AccessDeniedError("Identidade da consulta não pertence ao elenco.")
        state = seed_social_state(await self._repository.get(game_id), tuple(sorted(ids)), self._clock())
        return state, profiles

    async def owned_entries(self, game_id, npc_id):
        state, _ = await self._snapshot(game_id, npc_id)
        return tuple(entry for entry in state.knowledge if entry.owner_id == npc_id)

    async def shared_entries(self, game_id, npc_id, recipient_id="player"):
        state, _ = await self._snapshot(game_id, npc_id, recipient_id)
        return tuple(entry for entry in state.knowledge
                     if entry.owner_id == npc_id and entry.kind != "literal"
                     and can_share(entry, state.relationships, npc_id, recipient_id, game_id=game_id))

    async def process_pending(self, game_id, day):
        async with self._repository.lease(game_id) as acquired:
            if not acquired:
                return False
            return await self._process_pending(game_id, day)

    async def _process_pending(self, game_id, day):
        state = await self._repository.get(game_id)
        queue = await self._repository.exchanges(game_id, state.exchange_cursor)
        if not queue:
            return False
        npc_id = queue[0].npc_id
        batch = []
        for record in queue:
            if record.npc_id != npc_id:
                break
            batch.append(record)
        profiles = await self._characters.list()
        names = {profile.id: profile.name for profile in profiles} | {"player": "Floriano"}
        profile = next((profile for profile in profiles if profile.id == npc_id), None)
        seeded = state.model_copy(update={"relationships": state.relationships or initial_relationships(tuple(profile.id for profile in profiles))})
        additions = []
        existing = {entry.id for entry in seeded.knowledge}
        for record in batch:
            if (record.incoming.sender_id != "player" or record.outgoing.sender_id != npc_id
                    or profile is None
                    or record.outgoing.generation_status != "accepted"
                    or record.outgoing.content == SAFE_DIALOGUE_REPLY
                    or not self._guard.inspect_input(record.incoming.content).allowed
                    or not self._guard.inspect_output(record.outgoing.content,
                        () if record.outgoing.narrative_authorized else profile.protected_secrets,
                        allow_role_disclosure=record.outgoing.narrative_authorized).allowed):
                continue
            # A player can assert anything, but the claim remains a quotation attributed
            # to that player. No model creates roots, parents, sources or confidence gains.
            for source in (record.incoming, record.outgoing):
                identifier = uuid5(NAMESPACE_URL, f"{game_id}:{npc_id}:{source.id}:utterance-v2")
                if identifier in existing:
                    continue
                listener = npc_id if source.sender_id == "player" else "player"
                text = source.content[:1200]
                is_player_report = source.sender_id == "player" and len(source.content) <= 1200
                proposition = attributed_utterance(text, names[source.sender_id], names[listener])
                previous = next((entry for entry in (*seeded.knowledge, *additions)
                                 if entry.owner_id == npc_id and entry.speaker_id == source.sender_id
                                 and entry.proposition == proposition), None)
                tokens = set(word_tokens(normalize(text)))
                subjects = tuple(sorted(profile.id for profile in profiles
                                        if profile.id in tokens or normalize(profile.name.replace("Dr. ", "").split()[0]) in tokens))
                additions.append(KnowledgeEntry(
                    id=identifier, owner_id=npc_id, root_id=previous.root_id if previous else identifier,
                    source_message_id=source.id, speaker_id=source.sender_id,
                    source_span=text,
                    proposition=proposition, subject_ids=subjects,
                    parent_ids=(previous.id,) if previous else (),
                    kind="report" if is_player_report else "literal",
                    confidence="low", stance="undecided", day=record.day,
                    origin="dialogue", visibility="public", created_at=source.created_at,
                ))
                existing.add(identifier)
        updated = seeded.model_copy(update={
            "revision": state.revision + 1,
            "exchange_cursor": state.exchange_cursor + len(batch),
            "knowledge": (*seeded.knowledge, *additions),
        })
        return await self._repository.save(updated, state.revision, require_day=day)

    async def record_canonical_help(self, game_id, npc_id, event_id, day):
        """Only server-validated help calls this method; one bounded gain per NPC/day."""
        if day < 1 or event_id is None:
            raise ValueError("Ajuda exige evento canônico e dia válido.")
        async with self._repository.lease(game_id) as acquired:
            if not acquired:
                return False
            state = await self._repository.get(game_id)
            profiles = await self._characters.list()
            if npc_id not in {profile.id for profile in profiles}:
                raise AccessDeniedError("Morador não pertence ao elenco.")
            seeded = seed_social_state(state, tuple(profile.id for profile in profiles), self._clock())
            cause = uuid5(NAMESPACE_URL, f"{game_id}:{npc_id}:{day}:canonical-help")
            if cause in relationship_for(seeded, npc_id, "player").causes:
                return False
            updated = apply_relationship(seeded, npc_id, "player", cause, trust=5, affinity=3)
            return await self._repository.save(updated.model_copy(update={"revision": state.revision + 1}),
                                               state.revision, require_day=day)

    async def context(self, game_id, npc_id, other_id="player"):
        state, profiles = await self._snapshot(game_id, npc_id, other_id)
        names = {profile.id: profile.name for profile in profiles}
        own = [entry for entry in state.knowledge if entry.owner_id == npc_id]
        own.sort(key=lambda entry: (other_id in entry.subject_ids or entry.speaker_id == other_id,
                                    entry.created_at, str(entry.id)), reverse=True)
        shared = [entry for entry in own if can_share(entry, state.relationships, npc_id, other_id, game_id=game_id)]
        roots = {uuid5(NAMESPACE_URL, f"{game_id}:author-topic:{topic}"): topic for topic, *_ in TOPICS}
        from src.modules.achievements.rules import TOPIC_DISCOVERIES
        from src.modules.knowledge.affects import private_affect_context, relational_impulses
        private_shared = [entry for entry in shared if entry.visibility == "private" and entry.owner_id == npc_id]
        # Authorization is per disclosed topic, never all profile.protected_secrets.
        confidences = [entry.proposition for entry in private_shared]
        discoveries = sorted({TOPIC_DISCOVERIES[roots[entry.root_id]] for entry in shared
                              if entry.root_id in roots and roots[entry.root_id] in TOPIC_DISCOVERIES})
        encounters = [encounter for encounter in state.encounters if npc_id in encounter.participant_ids
                      and encounter.phase not in ("travelling", "talking")
                      and (encounter.messages or encounter.phase == "refused")]
        encounters.sort(key=lambda item: (other_id in item.participant_ids, item.started_at, str(item.id)), reverse=True)
        return {
            "sentimentos_proprios": private_affect_context(state, npc_id, confidences),
            "impulsos_relacionais": relational_impulses(state, npc_id, names),
            "confidencias_autorizadas": confidences,
            "descobertas_autorizadas": discoveries,
            "vinculos_conhecidos": [r.model_dump(mode="json") for r in state.relationships if r.actor_id == npc_id],
            "relacao_com_interlocutor": relationship_for(state, npc_id, other_id).model_dump(mode="json"),
            "memorias_relevantes": [{
                "claim_id": str(entry.id), "root_id": str(entry.root_id), "conteudo": entry.proposition,
                "origem": entry.origin, "mensagem_origem_id": str(entry.source_message_id),
                "quem_falou": entry.speaker_id, "fonte_alegada": entry.claimed_source_id,
                "trecho_ouvido": entry.source_span, "tipo": entry.kind,
                "confianca": entry.confidence, "posicao": entry.stance,
                "dia": entry.day, "visibilidade": entry.visibility,
                "revelar_so_com_vinculo": entry.disclosure_threshold, "compartilhavel": True,
            } for entry in shared[:12]],
            "encontros_anteriores": [{
                "dia": encounter.day, "phase": encounter.phase,
                "interlocutor_id": next(person for person in encounter.participant_ids if person != npc_id),
                "falas": [{"quem_falou": message.sender_id, "fala": message.content}
                          for message in encounter.messages[-4:]
                          if message.sender_id in encounter.participant_ids
                          and self._guard.inspect_input(message.content).allowed
                          and self._guard.inspect_output(message.content).allowed],
            } for encounter in encounters[:3]],
            "regra": "Conhecimento e liberação são autorizações da mesa. Relatos atribuídos não confirmam fatos.",
        }
