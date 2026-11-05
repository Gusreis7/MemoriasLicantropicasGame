"""Extração limitada de relatos e projeção do conhecimento privado por ator."""

import asyncio
import json
from src.textutils import word_tokens, has_word_start
import unicodedata
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5


from src.contracts.model import ChatMessage, GameCharacter
from src.contracts.social import KnowledgeEntry, SocialDay
from src.modules.agents.guard import (
    DialogueGuard,
    SAFE_DIALOGUE_REPLY,
)
from src.modules.agents.service import HarnessService
from src.infrastructure.usage import usage_scope
from src.infrastructure.llm.structured import generate_structured
from src.contracts.generation import Extraction
from src.prompts.knowledge import extraction_instructions
import logging

logger = logging.getLogger(__name__)
from src.modules.knowledge.seeds import seed_social_state
from src.modules.knowledge.rules import (
    apply_relationship,
    initial_relationships,
    relationship_for,
)


def attributed_utterance(content: str, speaker_name: str, listener_name: str) -> str:
    """Preservar a fala inteira e o destinatário evita inverter pronomes/sujeitos."""
    return f"{speaker_name} disse a {listener_name}: «{content}»"


class KnowledgeService:
    def __init__(self, repository, characters, llm, clock=None):
        self._repository, self._characters, self._llm = repository, characters, llm
        self._clock = clock or (lambda: datetime.now(UTC))
        self._guard = DialogueGuard()

    async def process_pending(self, game_id, day):
        async with self._repository.lease(game_id) as acquired:
            if not acquired:
                return False
            if not await self._repository.backfill_history(game_id):
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
        profile = await self._characters.get(npc_id)
        markers = (
            ()
            if profile is None
            else tuple(
                dict.fromkeys(
                    (
                        *HarnessService._private_markers(
                            profile, GameCharacter(character_id=npc_id, role="civil")
                        ),
                        *HarnessService._private_markers(
                            profile, GameCharacter(character_id=npc_id, role="werewolf")
                        ),
                    )
                )
            )
        )
        valid = [
            record
            for record in batch
            if profile is not None
            and record.incoming.sender_id == "player"
            and record.outgoing.sender_id == npc_id
            and record.outgoing.generation_status == "accepted"
            and self._guard.inspect_input(record.incoming.content).allowed
            and record.outgoing.content != SAFE_DIALOGUE_REPLY
            and self._guard.inspect_output(
                record.outgoing.content,
                ()
                if getattr(record.outgoing, "narrative_authorized", False)
                else markers,
                **(
                    {"allow_role_disclosure": True}
                    if getattr(record.outgoing, "narrative_authorized", False)
                    else {}
                ),
            ).allowed
        ]
        usage = next(
            (item for item in state.days if item.day == day), SocialDay(day=day)
        )
        if valid and usage.extraction_calls >= 8:
            return False
        profiles = await self._characters.list()
        names = {profile.id: profile.name for profile in profiles} | {
            "player": "Floriano"
        }
        permitted_ids = {item.id for item in profiles} | {"player", "bras_cubas"}
        if valid:
            charged = usage.model_copy(
                update={"extraction_calls": usage.extraction_calls + 1}
            )
            charged_state = state.model_copy(
                update={
                    "revision": state.revision + 1,
                    "days": (
                        *tuple(item for item in state.days if item.day != day),
                        charged,
                    ),
                    "relationships": state.relationships
                    or initial_relationships(tuple(item.id for item in profiles)),
                }
            )
            if not await self._repository.save(
                charged_state, state.revision, require_day=day
            ):
                return False
            state = charged_state
            sources = {
                message.id: message
                for record in valid
                for message in (record.incoming, record.outgoing)
            }
            source_days = {
                message.id: record.day
                for record in valid
                for message in (record.incoming, record.outgoing)
            }
            own_claims = {
                entry.id: entry for entry in state.knowledge if entry.owner_id == npc_id
            }
            payload = [
                {
                    "message_id": str(message.id),
                    "speaker_id": message.sender_id,
                    "text": message.content,
                }
                for message in sources.values()
            ]
            prompt = (
                ChatMessage(
                    role="system", content=extraction_instructions(permitted_ids)
                ),
                ChatMessage(
                    role="user",
                    content=json.dumps(
                        {
                            "npc_id": npc_id,
                            "messages": payload,
                            "known_claims": [
                                {
                                    "claim_id": str(entry.id),
                                    "text": entry.proposition,
                                    "direct_speaker_id": entry.speaker_id,
                                    "claimed_source_id": entry.claimed_source_id,
                                }
                                for entry in tuple(own_claims.values())[-12:]
                            ],
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            try:
                async with asyncio.timeout(12):
                    with usage_scope(game_id, "knowledge_extraction", npc_id):
                        result = await generate_structured(
                            self._llm, prompt, Extraction, max_attempts=1
                        )
                if not result.ok and result.response is None:
                    # Transport failure: no response to retain; keep the cursor for a later bounded retry.
                    logger.warning(
                        "knowledge_extraction_unavailable code=%s", result.error_code
                    )
                    return False
                if not result.ok:
                    logger.warning(
                        "knowledge_extraction_literal_fallback code=%s",
                        result.error_code,
                    )
                extraction = result.value if result.ok else Extraction(claims=())
            except TimeoutError:
                return False  # Cursor durável intacto; tentativas continuam limitadas à cota.
            additions = []
            reactions = []
            player_reactions = []
            for claim in extraction.claims:
                source = sources.get(claim.message_id)
                if source is None or claim.source_span not in source.content:
                    continue
                # O modelo seleciona uma fala, mas sua paráfrase não se torna o
                # conteúdo propagado. Falas longas aguardam revisão literal.
                if len(source.content) > 1200:
                    continue
                if any(
                    identifier not in permitted_ids for identifier in claim.subject_ids
                ):
                    continue
                if (
                    claim.claimed_source_id is not None
                    and claim.claimed_source_id not in permitted_ids
                ):
                    continue
                if any(
                    identifier not in own_claims
                    for identifier in claim.parent_claim_ids
                ):
                    continue
                if not self._guard.inspect_input(claim.source_span).allowed:
                    continue
                if (
                    not self._guard.inspect_input(claim.proposition).allowed
                    or not self._guard.inspect_output(
                        claim.proposition,
                        ()
                        if getattr(source, "narrative_authorized", False)
                        else markers,
                        **(
                            {"allow_role_disclosure": True}
                            if getattr(source, "narrative_authorized", False)
                            else {}
                        ),
                    ).allowed
                ):
                    continue
                if source.sender_id == "player" and claim.disposition in (
                    "cooperation",
                    "insult",
                    "confidence_breach",
                ):
                    player_reactions.append(
                        (source_days[source.id] or day, claim.disposition)
                    )
                listener_id = npc_id if source.sender_id == "player" else "player"
                proposition = attributed_utterance(
                    source.content,
                    names.get(source.sender_id, source.sender_id),
                    names.get(listener_id, listener_id),
                )
                identifier = uuid5(
                    NAMESPACE_URL, f"{game_id}:{npc_id}:{source.id}:{claim.kind}"
                )
                if any(entry.id == identifier for entry in additions):
                    continue
                parents = tuple(own_claims[item] for item in claim.parent_claim_ids)
                # Repetição literal pela mesma fonte, inclusive dentro do lote, não cria corroboração.
                if not parents:
                    repeated = next(
                        (
                            entry
                            for entry in (*own_claims.values(), *additions)
                            if entry.speaker_id == source.sender_id
                            and entry.proposition == proposition
                            and entry.claimed_source_id == claim.claimed_source_id
                            and entry.kind == claim.kind
                        ),
                        None,
                    )
                    parents = (repeated,) if repeated else ()
                root_id = parents[0].root_id if parents else identifier
                additions.append(
                    KnowledgeEntry(
                        id=identifier,
                        owner_id=npc_id,
                        root_id=root_id,
                        source_message_id=source.id,
                        speaker_id=source.sender_id,
                        claimed_source_id=claim.claimed_source_id,
                        source_span=source.content,
                        proposition=proposition,
                        subject_ids=tuple(dict.fromkeys(claim.subject_ids)),
                        parent_ids=tuple(parent.id for parent in parents),
                        kind=claim.kind,
                        day=source_days[source.id],
                        created_at=source.created_at,
                    )
                )
                normalized = "".join(
                    character
                    for character in unicodedata.normalize(
                        "NFKD", claim.source_span.casefold()
                    )
                    if not unicodedata.combining(character)
                )
                named_source = claim.claimed_source_id
                aliases = (
                    ("floriano", "detetive")
                    if named_source == "player"
                    else (named_source or "",)
                )
                if (
                    source.sender_id == "player"
                    and claim.disposition == "accusation"
                    and named_source
                    and named_source != npc_id
                    and any(alias and alias in normalized for alias in aliases)
                    and has_word_start(normalized, ('denunci','acus','delat'))
                ):
                    reactions.append((named_source, root_id))
            # Uma transcrição ambígua continua recuperável, mas não entra na agenda de fofoca.
            cited = {entry.source_message_id for entry in additions}
            for source in sources.values():
                if source.id in cited:
                    continue
                identifier = uuid5(
                    NAMESPACE_URL, f"{game_id}:{npc_id}:{source.id}:literal"
                )
                additions.append(
                    KnowledgeEntry(
                        id=identifier,
                        owner_id=npc_id,
                        root_id=identifier,
                        source_message_id=source.id,
                        speaker_id=source.sender_id,
                        source_span=source.content[:1200],
                        proposition=source.content[:1200],
                        kind="literal",
                        day=source_days[source.id],
                        created_at=source.created_at,
                    )
                )
        else:
            additions = []
            reactions = []
            player_reactions = []
        latest = await self._repository.get(game_id)
        if latest.exchange_cursor != state.exchange_cursor:
            return False
        for target, cause in reactions:
            latest = apply_relationship(
                latest, npc_id, target, cause, trust=-1, resentment=2
            )
        deltas = {
            "cooperation": {"affinity": 3, "trust": 5},
            "insult": {"trust": -2, "resentment": 3, "suspicion": 1},
            "confidence_breach": {"trust": -3, "resentment": 4},
        }
        for source_day, disposition in player_reactions:
            cause = uuid5(
                NAMESPACE_URL,
                f"{game_id}:{npc_id}:{source_day}:player_reaction:{disposition}",
            )
            latest = apply_relationship(
                latest, npc_id, "player", cause, **deltas[disposition]
            )
        existing = {entry.id for entry in latest.knowledge}
        updated = latest.model_copy(
            update={
                "revision": latest.revision + 1,
                "exchange_cursor": latest.exchange_cursor + len(batch),
                "knowledge": (
                    *latest.knowledge,
                    *tuple(entry for entry in additions if entry.id not in existing),
                ),
            }
        )
        return await self._repository.save(updated, latest.revision, require_day=day)

    async def context(self, game_id, npc_id, other_id="player"):
        state = await self._repository.get(game_id)
        profiles = await self._characters.list()
        state = seed_social_state(
            state, tuple(item.id for item in profiles), self._clock()
        )
        own = [entry for entry in state.knowledge if entry.owner_id == npc_id]
        own.sort(
            key=lambda entry: (
                other_id in entry.subject_ids or entry.speaker_id == other_id,
                entry.created_at,
                str(entry.id),
            ),
            reverse=True,
        )
        encounters = [
            encounter
            for encounter in state.encounters
            if npc_id in encounter.participant_ids
            and encounter.phase not in ("travelling", "talking")
            and (encounter.messages or encounter.phase == "refused")
        ]
        encounters.sort(
            key=lambda encounter: (
                other_id in encounter.participant_ids,
                encounter.started_at,
                str(encounter.id),
            ),
            reverse=True,
        )
        profile = next((p for p in profiles if p.id == npc_id), None)
        relation = relationship_for(state, npc_id, other_id)
        from src.modules.knowledge.mechanics import (
            can_share,
            can_confide_personal,
        )
        from src.modules.knowledge.seeds import TOPICS
        from src.modules.achievements.rules import TOPIC_DISCOVERIES

        confidences = (
            list(profile.protected_secrets)
            if profile and can_confide_personal(npc_id, relation)
            else []
        )
        shared = [
            entry
            for entry in own
            if can_share(entry, state.relationships, npc_id, other_id)
            or entry.visibility == "private"
            and entry.speaker_id == npc_id
            and confidences
        ]
        topic_roots = {
            uuid5(NAMESPACE_URL, f"{game_id}:author-topic:{topic}"): topic
            for topic, *_ in TOPICS
        }
        allowed = {
            TOPIC_DISCOVERIES[topic_roots[entry.root_id]]
            for entry in shared
            if entry.root_id in topic_roots
            and topic_roots[entry.root_id] in TOPIC_DISCOVERIES
        }
        if npc_id != "capitu" or not confidences:
            allowed.discard("capitu_separation")
        if npc_id != "escobar" or not confidences:
            allowed.discard("escobar_affection")
        from src.modules.knowledge.affects import (
            private_affect_context,
        )

        return {
            "sentimentos_proprios": private_affect_context(state, npc_id, confidences),
            "confidencias_autorizadas": confidences,
            "descobertas_autorizadas": sorted(allowed),
            "vinculos_conhecidos": [
                r.model_dump(mode="json")
                for r in state.relationships
                if r.actor_id == npc_id
            ],
            "relacao_com_interlocutor": relationship_for(
                state, npc_id, other_id
            ).model_dump(mode="json"),
            "memorias_relevantes": [
                {
                    "claim_id": str(entry.id),
                    "conteudo": entry.proposition,
                    "origem": entry.origin,
                    "mensagem_origem_id": str(entry.source_message_id),
                    "quem_falou": entry.speaker_id,
                    "fonte_alegada": entry.claimed_source_id,
                    "trecho_ouvido": entry.source_span,
                    "tipo": entry.kind,
                    "confianca": entry.confidence,
                    "posicao": entry.stance,
                    "dia": entry.day,
                    "visibilidade": entry.visibility,
                    "revelar_so_com_vinculo": entry.disclosure_threshold,
                    "compartilhavel": True,
                }
                for entry in shared[:8]
            ],
            "encontros_anteriores": [
                {
                    "dia": encounter.day,
                    "phase": encounter.phase,
                    "interlocutor_id": next(
                        identifier
                        for identifier in encounter.participant_ids
                        if identifier != npc_id
                    ),
                    "falas": [
                        {"quem_falou": message.sender_id, "fala": message.content}
                        for message in encounter.messages[-4:]
                        if message.sender_id in encounter.participant_ids
                        and self._guard.inspect_input(message.content).allowed
                        and self._guard.inspect_output(message.content).allowed
                    ],
                }
                for encounter in encounters[:3]
            ],
            "regra": "Relatos e interpretações não confirmam fatos do mundo. Não invente fontes nem consulte conversas alheias.",
        }
