"""Encontros limitados: geração fora de reservas do jogador e commit revalidado."""

import asyncio
import re
import unicodedata

from langsmith import tracing_context
from datetime import UTC, datetime, timedelta
from uuid import uuid4


from memorias_licantropicas.contracts.errors import ConflictError
from memorias_licantropicas.contracts.model import ChatMessage
from memorias_licantropicas.contracts.social import Encounter, SocialMessage
from memorias_licantropicas.modules.agents.guard import DialogueGuard
from memorias_licantropicas.modules.agents.service import HarnessService
from memorias_licantropicas.infrastructure.usage import usage_scope
from memorias_licantropicas.infrastructure.llm.structured import generate_structured
from memorias_licantropicas.contracts.generation import SpeechProposal
from memorias_licantropicas.prompts.social import social_instructions
from memorias_licantropicas.modules.investigation.interrogation import (
    npc_interrogation_context,
)
from memorias_licantropicas.modules.agents.grounding import grounding_issues
from memorias_licantropicas.modules.investigation.catalog import (
    INVENTORIES,
    ITEMS_BY_ID,
    OBSERVED_PEOPLE,
)
from memorias_licantropicas.modules.knowledge.rules import (
    apply_relationship,
    initial_relationships,
    transmit,
)
from memorias_licantropicas.modules.knowledge.seeds import seed_social_state
from memorias_licantropicas.modules.knowledge.mechanics import can_share
from memorias_licantropicas.modules.social.graph import build_social_cycle
from memorias_licantropicas.modules.social.policy import (
    SLOT_SECONDS,
    SLOT_WINDOW_SECONDS,
    day_record,
    replace_day,
    select_pair,
    should_refuse,
    social_tone,
)

ACTIVE_PHASES = ("travelling", "talking")


class InvalidSocialProposal(Exception):
    """Proposta externa rejeitada pelas regras; erros internos continuam propagando."""


def expresses_claim(text, proposition):
    """Citação metadata só acompanha fala que ao menos menciona o assunto.

    Guarda lexical conservadora, não prova equivalência semântica. Rejeita em vez de
    inserir uma citação que o NPC não disse. Variações naturais de flexão são aceitas.
    """
    stop = {
        "a",
        "o",
        "as",
        "os",
        "um",
        "uma",
        "que",
        "de",
        "da",
        "do",
        "dos",
        "das",
        "em",
        "no",
        "na",
        "nos",
        "nas",
        "por",
        "para",
        "com",
        "eu",
        "me",
        "se",
        "e",
        "ele",
        "ela",
        "isso",
        "isto",
        "esse",
        "essa",
        "foi",
        "disse",
        "contou",
        "floriano",
        "detetive",
        "senhor",
        "senhora",
    }

    def stems(value):
        normalized = "".join(
            c
            for c in unicodedata.normalize("NFKD", value.casefold())
            if not unicodedata.combining(c)
        )
        return {
            w[:5]
            for w in re.findall(r"[a-z]+", normalized)
            if len(w) > 3 and w not in stop
        }

    expected, spoken = stems(proposition), stems(text)
    return len(expected & spoken) >= 1 and bool(expected)


def replace_encounter(state, encounter):
    return state.model_copy(
        update={
            "encounters": tuple(
                encounter if item.id == encounter.id else item
                for item in state.encounters
            )
        }
    )


def current_encounter(state):
    return next(
        (item for item in state.encounters if item.phase in ACTIVE_PHASES), None
    )


class SocialService:
    def __init__(
        self,
        repository,
        knowledge,
        games,
        characters,
        world_repository,
        turns,
        llm,
        player_gate,
        clock=None,
        enabled=True,
    ):
        self._repository = repository
        self._knowledge = knowledge
        self._games = games
        self._characters = characters
        self._world = world_repository
        self._turns = turns
        self._llm = llm
        self._player_gate = player_gate
        self._clock = clock or (lambda: datetime.now(UTC))
        self._enabled = enabled
        self._guard = DialogueGuard()
        self._workflow = build_social_cycle(
            prepare=self._leased_node(self._prepare_cycle),
            advance=self._leased_node(self._advance_cycle),
            extract=self._extract_cycle,
            revalidate=self._revalidate_cycle,
            schedule=self._leased_node(self._schedule_cycle),
        )

    def now(self):
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Relógio social exige timezone.")
        return now.astimezone(UTC)

    async def _save(self, current, candidate, **kwargs):
        candidate = candidate.model_copy(update={"revision": current.revision + 1})
        return await self._repository.save(candidate, current.revision, **kwargs)

    def _event(self, event_type, **data):
        return {
            "id": str(uuid4()),
            "type": event_type,
            "source": "social",
            "occurred_at": self.now().isoformat(),
            "data": data,
        }

    @staticmethod
    def _released_world(world, encounter):
        return world.model_copy(
            update={
                "revision": world.revision + 1,
                "npcs": tuple(
                    npc.model_copy(
                        update={
                            "activity": "idle",
                            "social_encounter_id": None,
                            "travel_destination_id": None,
                            "travel_arrives_at": None,
                            "social_partner_id": None,
                        }
                    )
                    if getattr(npc, "social_encounter_id", None) == encounter.id
                    else npc
                    for npc in world.npcs
                ),
            }
        )

    async def _finish(
        self, state, world, encounter, phase, reason, *, player_idle=True
    ):
        updated = encounter.model_copy(update={"phase": phase, "reason": reason})
        candidate = replace_encounter(state, updated)
        # Um efeito por direção e encontro, limitado pelo helper e rastreado pela causa.
        for actor, recipient in (
            encounter.participant_ids,
            tuple(reversed(encounter.participant_ids)),
        ):
            messages = [
                message for message in encounter.messages if message.sender_id == actor
            ]
            if not messages:
                continue
            if any(message.intent in ("confront", "accuse") for message in messages):
                candidate = apply_relationship(
                    candidate, recipient, actor, encounter.id, trust=-1, resentment=3
                )
            elif any(
                message.intent in ("warn", "correct", "defend", "confide")
                and message.claim_ids
                for message in messages
            ):
                candidate = apply_relationship(
                    candidate, recipient, actor, encounter.id, affinity=1
                )
        return await self._save(
            state,
            candidate,
            world=self._released_world(world, encounter),
            expected_world_revision=world.revision,
            require_player_idle=player_idle,
            events=(
                self._event(
                    "social.encounter_ended",
                    encounter_id=str(encounter.id),
                    phase=phase,
                    reason=reason,
                ),
            ),
        )

    async def interrupt(self, game_id, npc_id):
        """Chamador mantém a reserva do jogador. Não faz inferência ou nova reserva."""
        for _ in range(5):
            state = await self._repository.get(game_id)
            encounter = current_encounter(state)
            if encounter is None or npc_id not in encounter.participant_ids:
                return False
            world = await self._world.get(game_id)
            if world is None:
                return False
            if await self._finish(
                state,
                world,
                encounter,
                "interrupted",
                "player_approach",
                player_idle=False,
            ):
                return True
        raise ConflictError("O encontro mudou durante a abordagem.")

    def _leased_node(self, action):
        async def invoke(state):
            # LangGraph nodes run in separate asyncio tasks. Lease ownership must
            # be acquired by the node performing a write, never inherited from tick.
            async with self._repository.lease(state["game_id"]) as acquired:
                if not acquired:
                    return {"route": "done", "result": False}
                return await action(state)

        return invoke

    async def tick(self, game_id):
        with tracing_context(enabled=False, parent=False):
            result = await self._workflow.ainvoke(
                {"game_id": game_id, "result": False, "nodes": ()},
                config={"recursion_limit": 8},
            )
        return result["result"]

    async def _prepare_cycle(self, invocation):
        game_id = invocation["game_id"]
        case = await self._turns.sync(game_id)
        state = await self._repository.get(game_id)
        world = await self._world.get(game_id)
        game = await self._games.get(game_id)
        result = {"route": "done", "nodes": ("prepare",), "result": False}
        if game is None or world is None:
            return result
        encounter = current_encounter(state)
        if case.assembly_session and case.assembly_session.phase == "debate":
            if encounter is not None:
                result["result"] = await self._finish(
                    state, world, encounter, "interrupted", "public_assembly"
                )
            return result
        if self._enabled and case.phase == "day" and case.status == "active":
            seeded = seed_social_state(
                state, tuple(m.character_id for m in game.characters), self.now()
            )
            if seeded != state:
                if not await self._save(state, seeded, require_day=case.day):
                    return result
                state = await self._repository.get(game_id)
        encounter = current_encounter(state)
        if not self._enabled:
            if encounter is not None:
                result["result"] = await self._finish(
                    state, world, encounter, "interrupted", "social_disabled"
                )
            return result
        if encounter is not None:
            eligible = {
                member.character_id
                for member in game.characters
                if member.alive and member.character_id != case.detained_npc_id
            }
            if (
                case.phase != "day"
                or case.status != "active"
                or case.day != encounter.day
                or not set(encounter.participant_ids) <= eligible
            ):
                result["result"] = await self._finish(
                    state, world, encounter, "interrupted", "phase_or_availability"
                )
                return result
            if self.now() >= encounter.deadline:
                result["result"] = await self._finish(
                    state, world, encounter, "finished", "deadline"
                )
                return result
            route = "advance"
        elif case.phase == "day" and case.status == "active":
            route = "extract"
        else:
            return result
        return {
            **result,
            "route": route,
            "case": case,
            "social": state,
            "world": world,
            "game": game,
            "encounter": encounter,
        }

    async def _advance_cycle(self, invocation):
        encounter = invocation["encounter"]
        if encounter.phase == "travelling":
            progressed = await self._arrive(
                invocation["social"], invocation["world"], encounter, invocation["case"]
            )
        else:
            progressed = await self._speak(
                invocation["social"],
                invocation["world"],
                encounter,
                invocation["case"],
                invocation["game"],
            )
        return {
            "result": progressed,
            "nodes": (*invocation["nodes"], "advance_encounter"),
        }

    async def _extract_cycle(self, invocation):
        progressed = await self._knowledge.process_pending(
            invocation["game_id"], invocation["case"].day
        )
        return {
            "result": progressed,
            "nodes": (*invocation["nodes"], "extract_knowledge"),
        }

    async def _revalidate_cycle(self, invocation):
        # The extraction can take time while a player moves or the day ends.
        game_id = invocation["game_id"]
        state = await self._repository.get(game_id)
        case = await self._turns.sync(game_id)
        world = await self._world.get(game_id)
        game = await self._games.get(game_id)
        route = (
            "schedule"
            if world is not None
            and game is not None
            and case.phase == "day"
            and case.status == "active"
            else "done"
        )
        return {
            "social": state,
            "case": case,
            "world": world,
            "game": game,
            "route": route,
            "nodes": (*invocation["nodes"], "revalidate_world"),
        }

    async def _schedule_cycle(self, invocation):
        progressed = await self._schedule(
            invocation["social"],
            invocation["world"],
            invocation["case"],
            invocation["game"],
        )
        return {
            "result": progressed or invocation["result"],
            "nodes": (*invocation["nodes"], "schedule_encounter"),
        }

    async def _schedule(self, state, world, case, game):
        now = self.now()
        start = case.phase_ends_at - timedelta(
            seconds=getattr(self._turns, "_day_seconds", 300)
        )
        elapsed = (now - start).total_seconds()
        record = day_record(state, case.day)
        expired = tuple(
            index
            for index, offset in enumerate(SLOT_SECONDS, 1)
            if elapsed >= offset + SLOT_WINDOW_SECONDS and index not in record.slots
        )
        due = next(
            (
                index
                for index, offset in enumerate(SLOT_SECONDS, 1)
                if offset <= elapsed < offset + SLOT_WINDOW_SECONDS
                and index not in record.slots
            ),
            None,
        )
        if due is None and not expired:
            return False
        new_slots = tuple(
            sorted(set((*record.slots, *expired, *((due,) if due is not None else ()))))
        )
        candidate = replace_day(state, record.model_copy(update={"slots": new_slots}))
        if not candidate.relationships:
            candidate = candidate.model_copy(
                update={
                    "relationships": initial_relationships(
                        tuple(member.character_id for member in game.characters)
                    )
                }
            )
        if due is None or (case.phase_ends_at - now).total_seconds() < 8:
            return await self._save(
                state, candidate, require_day=case.day, require_player_idle=True
            )
        positions = {npc.npc_id: npc for npc in world.npcs}
        pending_reader = getattr(self._repository, "pending_npc_ids", None)
        pending = (
            set(await pending_reader(game.id, state.exchange_cursor))
            if pending_reader
            else set()
        )
        eligible = tuple(
            member.character_id
            for member in game.characters
            if member.alive
            and member.character_id != case.detained_npc_id
            and member.character_id not in pending
            and member.character_id in positions
            and getattr(positions[member.character_id], "activity", "idle") == "idle"
            and (
                positions[member.character_id].player_engaged_until is None
                or positions[member.character_id].player_engaged_until <= now
            )
        )
        chosen = select_pair(candidate, eligible, world, case.day, due, now)
        if chosen is None:
            return await self._save(
                state, candidate, require_day=case.day, require_player_idle=True
            )
        _, _, actor, recipient, topic_ids, route = chosen
        origin, destination = positions[actor], positions[recipient]
        travelling = len(route) > 1 or abs(origin.x - destination.x) > 64
        # Até no mesmo cenário é preciso caminhar antes de conversar, sem salto de coordenada.
        travel_seconds = (
            12 * (len(route) - 1)
            if len(route) > 1
            else max(1, (abs(origin.x - destination.x) - 48) / 65)
            if travelling
            else 0
        )
        arrival = now + timedelta(seconds=travel_seconds)
        deadline = min(now + timedelta(seconds=40), case.phase_ends_at)
        if arrival >= deadline:
            return await self._save(
                state, candidate, require_day=case.day, require_player_idle=True
            )
        refused = should_refuse(candidate, actor, recipient, topic_ids)
        encounter = Encounter(
            id=uuid4(),
            day=case.day,
            slot=due,
            participant_ids=(actor, recipient),
            location_id=destination.location_id,
            phase="refused" if refused else "travelling" if travelling else "talking",
            started_at=now,
            deadline=deadline,
            arrival_at=arrival,
            route=route,
            origin_location_id=origin.location_id,
            topic_ids=topic_ids,
            reason="recipient_refused" if refused else None,
        )
        candidate = candidate.model_copy(
            update={"encounters": (*candidate.encounters, encounter)}
        )
        if refused:
            return await self._save(
                state,
                candidate,
                require_day=case.day,
                require_npcs=(actor, recipient),
                require_player_idle=True,
                expected_world_revision=world.revision,
                events=(
                    self._event(
                        "social.invitation_refused",
                        encounter_id=str(encounter.id),
                        participant_ids=[actor, recipient],
                    ),
                ),
            )
        updated_npcs = []
        for npc in world.npcs:
            if npc.npc_id not in (actor, recipient):
                updated_npcs.append(npc)
                continue
            updates = {
                "activity": "travelling"
                if travelling and npc.npc_id == actor
                else "talking",
                "social_encounter_id": encounter.id,
                "social_partner_id": recipient if npc.npc_id == actor else actor,
                "travel_destination_id": destination.location_id
                if travelling and npc.npc_id == actor
                else None,
                "travel_arrives_at": arrival
                if travelling and npc.npc_id == actor
                else None,
                "travel_started_at": now
                if travelling and npc.npc_id == actor
                else None,
                "travel_origin_x": origin.x if npc.npc_id == actor else None,
                "travel_target_x": max(32, destination.x - 48)
                if npc.npc_id == actor
                else None,
                "travel_route": route if travelling and npc.npc_id == actor else (),
            }
            updated_npcs.append(npc.model_copy(update=updates))
        updated_world = world.model_copy(
            update={"revision": world.revision + 1, "npcs": tuple(updated_npcs)}
        )
        return await self._save(
            state,
            candidate,
            world=updated_world,
            expected_world_revision=world.revision,
            require_day=case.day,
            require_npcs=(actor, recipient),
            require_player_idle=True,
            events=(
                self._event(
                    "social.encounter_planned",
                    encounter_id=str(encounter.id),
                    participant_ids=[actor, recipient],
                    location_id=destination.location_id,
                    route=list(route),
                    origin_x=origin.x,
                    destination_x=max(32, destination.x - 48),
                    arrival_at=arrival.isoformat(),
                ),
            ),
        )

    async def _arrive(self, state, world, encounter, case):
        if self.now() < encounter.arrival_at:
            return False
        actor, recipient = encounter.participant_ids
        positions = {npc.npc_id: npc for npc in world.npcs}
        if any(
            identifier not in positions
            or positions[identifier].social_encounter_id != encounter.id
            for identifier in encounter.participant_ids
        ):
            return await self._finish(
                state, world, encounter, "interrupted", "reservation_lost"
            )
        target = positions[recipient]
        if target.location_id != encounter.location_id:
            return await self._finish(
                state, world, encounter, "interrupted", "recipient_moved"
            )
        updated = encounter.model_copy(update={"phase": "talking"})
        updated_world = world.model_copy(
            update={
                "revision": world.revision + 1,
                "npcs": tuple(
                    npc.model_copy(
                        update={
                            "activity": "talking",
                            "location_id": target.location_id,
                            "x": max(32, target.x - 48),
                            "travel_destination_id": None,
                            "travel_arrives_at": None,
                        }
                    )
                    if npc.npc_id == actor
                    else npc
                    for npc in world.npcs
                ),
            }
        )
        return await self._save(
            state,
            replace_encounter(state, updated),
            world=updated_world,
            expected_world_revision=world.revision,
            require_day=case.day,
            require_npcs=encounter.participant_ids,
            require_player_idle=True,
            events=(
                self._event("social.encounter_started", encounter_id=str(encounter.id)),
            ),
        )

    async def _speak(self, state, world, encounter, case, game):
        positions = {npc.npc_id: npc for npc in world.npcs}
        if any(
            identifier not in positions
            or positions[identifier].social_encounter_id != encounter.id
            or positions[identifier].location_id != encounter.location_id
            for identifier in encounter.participant_ids
        ):
            return await self._finish(
                state, world, encounter, "interrupted", "copresence_lost"
            )
        if len(encounter.messages) >= 4:
            return await self._finish(state, world, encounter, "finished", "turn_limit")
        record = day_record(state, case.day)
        if record.speech_calls >= 16:
            return await self._finish(state, world, encounter, "finished", "budget")
        # Débito confirmado antes de chamar o provedor; cancelamento/restart também consome a tentativa.
        reserved = replace_day(
            state, record.model_copy(update={"speech_calls": record.speech_calls + 1})
        )
        if not await self._save(
            state,
            reserved,
            expected_world_revision=world.revision,
            require_day=case.day,
            require_npcs=encounter.participant_ids,
            require_player_idle=True,
        ):
            return False
        reserved_revision = state.revision + 1
        actor = encounter.participant_ids[len(encounter.messages) % 2]
        recipient = next(
            identifier
            for identifier in encounter.participant_ids
            if identifier != actor
        )
        profile = await self._characters.get(actor)
        member = next(item for item in game.characters if item.character_id == actor)
        if profile is None:
            return False
        own = tuple(
            entry
            for entry in state.knowledge
            if entry.owner_id == actor
            and entry.kind != "literal"
            and can_share(entry, state.relationships, actor, recipient)
        )
        # No máximo duas alegações por turno; prioridade para o tópico ou a resposta ao encontro.
        topics = sorted(
            own,
            key=lambda entry: (
                entry.id in encounter.topic_ids,
                recipient in entry.subject_ids,
                entry.created_at,
            ),
            reverse=True,
        )[:8]
        names = {item.id: item.name for item in await self._characters.list()}
        names["player"] = "Floriano"
        context = await self._knowledge.context(game.id, actor, recipient)
        topic_set = {str(entry.id) for entry in topics}
        context = {
            **context,
            "memorias_relevantes": [
                item
                for item in context.get("memorias_relevantes", ())
                if item.get("claim_id") in topic_set
            ],
        }
        instructions = self._instructions(
            profile,
            member,
            actor,
            recipient,
            names,
            context,
            topics,
            encounter,
            state,
            case,
        )
        try:
            async with asyncio.timeout(
                min(12, max(0.01, (encounter.deadline - self.now()).total_seconds()))
            ):
                with usage_scope(game.id, "social_speech", actor):
                    result = await generate_structured(
                        self._llm,
                        (ChatMessage(role="system", content=instructions),),
                        SpeechProposal,
                        max_attempts=1,
                    )
            if not result.ok:
                raise InvalidSocialProposal("invalid_social_proposal")
            proposal = result.value
            if not proposal.fala.strip() or len(set(proposal.claim_ids)) != len(
                proposal.claim_ids
            ):
                raise InvalidSocialProposal("Proposta vazia ou repetida.")
            allowed = {entry.id: entry for entry in topics}
            if any(identifier not in allowed for identifier in proposal.claim_ids):
                raise InvalidSocialProposal("Alegação inacessível.")
            if any(
                not expresses_claim(proposal.fala, allowed[i].proposition)
                for i in proposal.claim_ids
            ):
                raise InvalidSocialProposal(
                    "A fala não expressa o assunto selecionado."
                )
            markers = tuple(
                m
                for m in HarnessService._private_markers(profile, member)
                if m not in context.get("confidencias_autorizadas", ())
            )
            if not self._guard.inspect_output(proposal.fala, markers).allowed:
                raise InvalidSocialProposal("Fala rejeitada pela guarda.")
            # IDs e cadeia de fontes ficam nos dados; a fala pode parafrasear com voz própria.
            if grounding_issues(
                proposal.fala,
                {
                    **npc_interrogation_context(case, actor),
                    "memoria_social": context,
                },
                names,
            ):
                raise InvalidSocialProposal("ungrounded_social_speech")
        except (TimeoutError, InvalidSocialProposal):
            latest = await self._repository.get(game.id)
            latest_world = await self._world.get(game.id)
            if latest.revision == reserved_revision and latest_world is not None:
                return await self._finish(
                    latest,
                    latest_world,
                    encounter,
                    "failed",
                    "invalid_or_unavailable_generation",
                )
            return False
        latest = await self._repository.get(game.id)
        latest_world = await self._world.get(game.id)
        if (
            latest.revision != reserved_revision
            or latest_world is None
            or self.now() >= encounter.deadline
        ):
            return False
        current = current_encounter(latest)
        if current is None or current.id != encounter.id or current.phase != "talking":
            return False
        message = SocialMessage(
            id=uuid4(),
            sender_id=actor,
            content=proposal.fala.strip(),
            created_at=self.now(),
            intent=proposal.intent,
            claim_ids=proposal.claim_ids,
        )
        candidate = transmit(latest, message, recipient, case.day)
        updated = current.model_copy(update={"messages": (*current.messages, message)})
        candidate = replace_encounter(candidate, updated)
        finished = len(updated.messages) >= 4 or proposal.intent == "end"
        if finished:
            updated = updated.model_copy(
                update={
                    "phase": "finished",
                    "reason": "turn_limit"
                    if len(updated.messages) >= 4
                    else "speaker_ended",
                }
            )
            candidate = replace_encounter(candidate, updated)
            for speaker, listener in (
                updated.participant_ids,
                tuple(reversed(updated.participant_ids)),
            ):
                speech = [
                    item for item in updated.messages if item.sender_id == speaker
                ]
                if any(item.intent in ("confront", "accuse") for item in speech):
                    candidate = apply_relationship(
                        candidate, listener, speaker, updated.id, trust=-1, resentment=3
                    )
                elif any(
                    item.intent in ("warn", "correct", "defend", "confide")
                    and item.claim_ids
                    for item in speech
                ):
                    candidate = apply_relationship(
                        candidate, listener, speaker, updated.id, affinity=1
                    )
        events = (
            self._event(
                "social.message_spoken",
                encounter_id=str(updated.id),
                message_id=str(message.id),
                sender_id=actor,
                recipient_id=recipient,
                intent=message.intent,
            ),
        )
        if finished:
            events += (
                self._event(
                    "social.encounter_ended",
                    encounter_id=str(updated.id),
                    phase="finished",
                    reason=updated.reason,
                ),
            )
        return await self._save(
            latest,
            candidate,
            world=self._released_world(latest_world, updated) if finished else None,
            expected_world_revision=latest_world.revision,
            require_day=case.day,
            require_npcs=encounter.participant_ids,
            require_player_idle=True,
            events=events,
        )

    def _instructions(
        self,
        profile,
        member,
        actor,
        recipient,
        names,
        context,
        topics,
        encounter,
        state,
        case,
    ):
        from memorias_licantropicas.modules.investigation.night_story import (
            plot_context,
        )

        observations = {
            "seu_conflito_privado": plot_context(case, actor, names),
            **npc_interrogation_context(case, actor),
            "dia": case.day,
            "jornal": [
                {"dia": item.day, "manchete": item.headline, "noticia": item.body}
                for item in case.journal
            ],
            "seus_objetos": [
                ITEMS_BY_ID[identifier].model_dump()
                for identifier in INVENTORIES.get(actor, ())
            ],
            "posses_que_observou": [
                {
                    "pessoa": names.get(person, person),
                    "tipos": [ITEMS_BY_ID[item].name for item in INVENTORIES[person]],
                }
                for person in OBSERVED_PEOPLE.get(actor, ())
            ],
            "seus_depoimentos": [
                item.text for item in case.testimonies if item.witness_id == actor
            ],
        }
        claims = [
            {
                "id": str(entry.id),
                "proposicao": entry.proposition,
                "fonte_direta": names.get(entry.speaker_id, entry.speaker_id),
                "fonte_alegada": names.get(
                    entry.claimed_source_id, entry.claimed_source_id
                ),
                "tipo": entry.kind,
                "certeza": entry.confidence,
                "postura": entry.stance,
            }
            for entry in topics
        ]
        transcript = [
            {"quem": names.get(item.sender_id, item.sender_id), "fala": item.content}
            for item in encounter.messages
        ]
        data = {
            "sua_ficha_privada": HarnessService._private_context(profile, member),
            "interlocutor": names.get(recipient, recipient),
            "tom": social_tone(state, actor, recipient),
            "memoria_privada": context,
            "observacoes": observations,
            "alegacoes_compartilhaveis": claims,
            "falas_deste_encontro": transcript,
        }
        return social_instructions(data)
