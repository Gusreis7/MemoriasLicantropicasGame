"""Execute partidas completas pelos mesmos services usados pelo servidor.

O jogador recebe exclusivamente CasePublic/WorldSnapshot/MessageReply. O LLM
local é um dublê explícito: valida encadeamento, nunca qualidade narrativa Qwen.
Fixtures de PRNG/relógio tornam a mecânica reproduzível sem fabricar resultados.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
import random
from typing import Literal
from unittest.mock import patch
from uuid import UUID, uuid4

import fakeredis
from redis.asyncio import Redis

from memorias_licantropicas.contracts.errors import (
    AccessDeniedError,
    ConflictError,
    LLMUnavailableError,
)
from memorias_licantropicas.infrastructure.conversation_gate import (
    RedisConversationGate,
)
from memorias_licantropicas.infrastructure.redis_repository import (
    RedisGameRepository,
    RedisMemoryRepository,
)
from memorias_licantropicas.infrastructure.social_repository import (
    RedisSocialRepository,
)
from memorias_licantropicas.infrastructure.usage import (
    MeteredLLMClient,
    RedisUsageRepository,
    UsagePricing,
)
from memorias_licantropicas.modules.agents.service import HarnessService
from memorias_licantropicas.modules.characters.repository import (
    CatalogCharacterRepository,
)
from memorias_licantropicas.modules.conversations.service import ConversationService
from memorias_licantropicas.modules.games.service import GameService
from memorias_licantropicas.modules.investigation.service import InvestigationService
from memorias_licantropicas.modules.knowledge.service import KnowledgeService
from memorias_licantropicas.modules.session_master.service import SessionMasterService
from memorias_licantropicas.modules.social.service import SocialService
from memorias_licantropicas.modules.turns.service import TurnService
from memorias_licantropicas.modules.world.catalog import LOCATIONS
from memorias_licantropicas.modules.world.gate import RedisPlayerGate
from memorias_licantropicas.modules.world.repository import RedisWorldRepository
from memorias_licantropicas.modules.world.schema import MoveRequest, TravelRequest
from memorias_licantropicas.modules.world.service import WorldService

from memorias_licantropicas.simulation.model import (
    BudgetedSessionModel,
    Fault,
    OfflineSessionModel,
)

Policy = Literal["investigator", "assembly", "rash", "passive"]
POLICIES: tuple[Policy, ...] = ("investigator", "assembly", "rash", "passive")
# unittest.mock patches are process-global. Serializing fixtures prevents mixing PRNGs.
_fixture_lock = asyncio.Lock()


@dataclass
class Clock:
    value: datetime

    def __call__(self):
        return self.value

    def advance(self, seconds: float):
        self.value += timedelta(seconds=seconds)


def public_ranking(case, living_ids):
    """Only public item kinds, attribution and distinct sources influence ranking."""
    evidence = {item.id: item for item in case.inventory}
    ranked = []
    released = {
        item.suspect_id
        for item in case.accusations
        if item.accepted
        and any(
            edition.day == item.day + 1 and edition.detention_outcome == "released"
            for edition in case.journal
        )
    }
    for npc_id in sorted(set(living_ids) - released - set(case.expelled_npc_ids)):
        linked = {}
        witnesses = set()
        for testimony in case.testimonies:
            item = evidence.get(testimony.evidence_id)
            if (
                item
                and testimony.recognition == "recognizes"
                and testimony.claimed_owner_id == npc_id
            ):
                linked[item.item_id] = item
                witnesses.add(testimony.witness_id)
        score = sum(
            {"common": 1, "singular": 2, "unique": 5}[item.kind]
            for item in linked.values()
        )
        ranked.append(
            {
                "npc_id": npc_id,
                "score": score,
                "types": len(linked),
                "sources": len(witnesses),
            }
        )
    return sorted(
        ranked, key=lambda item: (-item["score"], -item["sources"], item["npc_id"])
    )


class SessionSimulation:
    """Own real services; feed only public snapshots into investigator decisions."""

    def __init__(
        self,
        redis,
        prefix: str,
        seed: int,
        *,
        fault: Fault = "none",
        live_model=None,
        pricing=None,
    ):
        self.redis, self.prefix, self.seed = redis, prefix, seed
        self.rng = random.Random(seed)
        self.clock = Clock(datetime(2026, 11, 5, 12, tzinfo=UTC))
        self.catalog = CatalogCharacterRepository()
        self.games = RedisGameRepository(redis, prefix)
        self.memory = RedisMemoryRepository(redis, prefix)
        self.worlds = RedisWorldRepository(redis, prefix)
        self.gate = RedisPlayerGate(redis, prefix)
        self.turns = TurnService(
            redis,
            prefix,
            self.games,
            self.catalog,
            self.worlds,
            self.gate,
            clock=self.clock,
        )
        self.investigation = InvestigationService(self.turns, self.catalog, self.memory)
        self.game_service = GameService(self.catalog, self.games, day_policy=self.turns)
        self.social_repository = RedisSocialRepository(redis, prefix, clock=self.clock)
        self.model = live_model or OfflineSessionModel(fault)
        self.mode = "live" if live_model is not None else "offline"
        self.initial_calls = self.model.calls.copy()
        self.initial_faults = self.model.injected_faults
        self.usage = RedisUsageRepository(
            redis,
            prefix,
            pricing=pricing or UsagePricing(model="offline-session-double"),
        )
        self.llm = MeteredLLMClient(
            self.model, self.usage, configured_model=self.usage.pricing.model
        )
        self.knowledge = KnowledgeService(
            self.social_repository, self.catalog, self.llm, clock=self.clock
        )
        self.social = SocialService(
            self.social_repository,
            self.knowledge,
            self.games,
            self.catalog,
            self.worlds,
            self.turns,
            self.llm,
            self.gate,
            clock=self.clock,
        )
        self.world = WorldService(
            self.games,
            self.catalog,
            self.worlds,
            self.gate,
            clock=self.clock,
            day_policy=self.turns,
            on_approach=self.social.interrupt,
            social_repository=self.social_repository,
        )
        self.master = SessionMasterService(
            self.turns, self.games, self.memory, self.llm, redis, prefix
        )
        self.turns._victory_editor = self.master.publish_victory
        self.traces = []
        self.harness = HarnessService(
            self.catalog,
            self.games,
            self.memory,
            self.llm,
            day_policy=self.turns,
            context_provider=self.investigation.npc_context_locked,
            knowledge_provider=self.knowledge.context,
            session_master=self.master,
            trace_sink=self.record_trace,
        )
        self.conversations = ConversationService(
            self.catalog,
            self.games,
            self.memory,
            self.harness,
            RedisConversationGate(redis, prefix),
            self.world,
            self.gate,
        )
        self.investigation._social_repository = self.social_repository
        self.investigation._assembly_llm = self.llm
        self.actions = Counter()
        self.trace = []
        self.game_id = None
        self.conversation_ids = set()
        self.errors = []

    async def record_trace(self, trace):
        self.traces.append(
            trace.model_dump(mode="json")
            if hasattr(trace, "model_dump")
            else dict(trace)
        )

    def _record(self, action, **detail):
        self.actions[action] += 1
        self.trace.append({"action": action, **detail})

    async def walk_to(self, location_id, x):
        snapshot = await self.world.get(self.game_id)
        if snapshot.player.location_id != location_id:
            snapshot = await self.world.travel(
                self.game_id,
                TravelRequest(
                    target_location_id=location_id, revision=snapshot.revision
                ),
            )
            self._record("travel", location_id=location_id)
        for _ in range(100):
            distance = abs(x - snapshot.player.x)
            if distance <= 5:
                self._record(
                    "walk",
                    location_id=location_id,
                    movement_seq=snapshot.player.movement_seq,
                )
                return snapshot
            direction = "right" if x > snapshot.player.x else "left"
            snapshot = await self.world.move(
                self.game_id,
                MoveRequest(
                    direction=direction,
                    seq=snapshot.player.movement_seq + 1,
                    location_id=location_id,
                    revision=snapshot.revision,
                ),
            )
            self.clock.advance(min(0.35, distance / 210))
            snapshot = await self.world.move(
                self.game_id,
                MoveRequest(
                    direction="idle",
                    seq=snapshot.player.movement_seq + 1,
                    location_id=location_id,
                    revision=snapshot.revision,
                ),
            )
        raise RuntimeError("Walking did not converge through WorldService")

    async def speak(self, npc_id, question):
        conversation = await self.conversations.create(self.game_id, npc_id)
        self.conversation_ids.add(conversation.id)
        try:
            reply = await self.conversations.send(
                self.game_id, conversation.id, question
            )
            self._record("dialogue", npc_id=npc_id, useful=reply.message.useful)
            history = await self.conversations.history(self.game_id, conversation.id)
            if not any(message.id == reply.message.id for message in history.messages):
                raise AssertionError("LLM reply missing from persisted public history")
            return reply.message
        except LLMUnavailableError as error:
            self.errors.append(
                {"action": "dialogue", "code": error.code, "npc_id": npc_id}
            )
            self._record("dialogue_error", code=error.code)
            return None
        finally:
            await self.conversations.close(self.game_id, conversation.id)
            self.clock.advance(2)

    async def collect(self, case):
        for crime in case.crimes:
            if not crime.remaining_clues:
                continue
            await self.walk_to(crime.location_id, crime.x)
            for _ in range(crime.remaining_clues):
                case = await self.investigation.search(self.game_id, crime.id)
                self._record("search", day=case.day)
                self.clock.advance(1)
        for evidence in case.inventory:
            if not evidence.examined:
                case = await self.investigation.inspect(self.game_id, evidence.id)
                self._record("inspect", kind=evidence.kind)
        return case

    async def survey(self, case, *, passive=False):
        living = set()
        for location in LOCATIONS:
            snapshot = await self.walk_to(location.id, 160)
            for visible in snapshot.visible_npcs:
                living.add(visible.npc_id)
                await self.walk_to(location.id, visible.x)
                await self.speak(
                    visible.npc_id,
                    "Onde estava ontem à noite, com quem e o que fazia?",
                )
                if passive:
                    return await self.investigation.get(self.game_id), living
                known = {
                    (item.evidence_id, item.witness_id) for item in case.testimonies
                }
                for evidence in case.inventory:
                    if (evidence.id, visible.npc_id) not in known:
                        case = await self.investigation.present(
                            self.game_id, evidence.id, visible.npc_id
                        )
                        self._record(
                            "present", npc_id=visible.npc_id, kind=evidence.kind
                        )
                        self.clock.advance(1)
                await self.speak(
                    visible.npc_id,
                    "Sobre o último objeto que mostrei, o que você reconhece?",
                )
                case = await self.investigation.get(self.game_id)
                if any(
                    record.npc_id == visible.npc_id
                    and record.day == case.day - 1
                    and record.period == "night"
                    for record in case.interrogations
                ):
                    self._record(
                        "interrogate", npc_id=visible.npc_id, source="dialogue"
                    )
                await self.knowledge.process_pending(self.game_id, case.day)
        return await self.investigation.get(self.game_id), living

    async def socialize(self, case):
        start = case.phase_ends_at - timedelta(seconds=300)
        due = next(
            (
                start + timedelta(seconds=offset)
                for offset in (60, 120, 180, 240)
                if self.clock() <= start + timedelta(seconds=offset)
            ),
            None,
        )
        if due is None:
            return
        self.clock.value = due
        for _ in range(7):
            await self.social.tick(self.game_id)
            self._record("social_tick", day=case.day)
            social = await self.social_repository.get(self.game_id)
            active = next(
                (
                    encounter
                    for encounter in social.encounters
                    if encounter.phase in {"travelling", "talking"}
                ),
                None,
            )
            if active is None:
                continue
            if active.phase == "travelling":
                self.clock.value = max(
                    self.clock(), active.arrival_at + timedelta(milliseconds=1)
                )
            else:
                self.clock.advance(0.1)

    async def next_morning(self):
        case = await self.investigation.get(self.game_id)
        previous_day = case.day
        for _ in range(3):
            if case.status != "active":
                return case
            self.clock.value = max(self.clock(), case.phase_ends_at)
            case = await self.investigation.get(self.game_id)
            if case.day > previous_day:
                self._record("morning", day=case.day, crimes=len(case.crimes))
                return case
        raise AssertionError("TurnService did not advance the night")

    async def play(self, policy: Policy = "investigator"):
        async with _fixture_lock:
            return await self._play(policy)

    async def _play(self, policy):
        # Only entropy/time boundaries are replaced; all decisions and transitions are real.
        game_uuid = UUID(int=self.rng.getrandbits(128), version=4)
        with ExitStack() as fixtures:
            fixtures.enter_context(
                patch(
                    "memorias_licantropicas.modules.games.service.choice",
                    self.rng.choice,
                )
            )
            fixtures.enter_context(
                patch(
                    "memorias_licantropicas.modules.games.service.uuid4",
                    return_value=game_uuid,
                )
            )
            time_fixture = fixtures.enter_context(
                patch("memorias_licantropicas.modules.games.service.datetime")
            )
            time_fixture.now.side_effect = lambda _tz=UTC: self.clock()
            fixtures.enter_context(
                patch(
                    "memorias_licantropicas.modules.investigation.rules.choice",
                    self.rng.choice,
                )
            )
            fixtures.enter_context(
                patch(
                    "memorias_licantropicas.modules.investigation.night_story.choice",
                    self.rng.choice,
                )
            )
            fixtures.enter_context(
                patch(
                    "memorias_licantropicas.modules.investigation.night_story.token_hex",
                    side_effect=lambda size: self.rng.getrandbits(size * 8)
                    .to_bytes(size, "big")
                    .hex(),
                )
            )
            game = await self.game_service.create()
            self.game_id = game.id
            self._record("create_game")
            case = await self.investigation.get(game.id)
            for _ in range(16):
                if case.status != "active":
                    break
                try:
                    if policy != "passive":
                        case = await self.collect(case)
                    case, living = await self.survey(case, passive=policy == "passive")
                    if case.status != "active":
                        break
                    await self.socialize(case)
                    case = await self.investigation.get(game.id)
                    if policy != "passive":
                        ranked = public_ranking(case, living)
                        self.trace.append(
                            {
                                "action": "public_ranking",
                                "day": case.day,
                                "ranking": ranked,
                            }
                        )
                        candidate = ranked[0] if ranked else None
                        if candidate and candidate["score"] > 0:
                            evidence_ids = tuple(item.id for item in case.inventory)
                            testimony_ids = tuple(item.id for item in case.testimonies)
                            review = await self.investigation.review_accusation(
                                game.id,
                                candidate["npc_id"],
                                evidence_ids,
                                testimony_ids,
                            )
                            self._record("review", ready=review.ready)
                            if (
                                policy == "assembly"
                                and review.ready
                                and case.assembly is None
                            ):
                                case = await self.investigation.open_assembly(
                                    game.id,
                                    candidate["npc_id"],
                                    evidence_ids,
                                    testimony_ids,
                                    "As marcas examinadas e os relatos independentes sustentam esta suspeita; peço que comparem os registros.",
                                )
                                self._record("assembly_open")
                                case = await self.investigation.resolve_assembly(
                                    game.id,
                                    "Vamos decidir com os registros que apresentei, sem transformar ciúme em prova.",
                                )
                                self._record(
                                    "assembly_resolve", outcome=case.assembly["outcome"]
                                )
                            elif review.ready or policy == "rash":
                                case = await self.investigation.accuse(
                                    game.id,
                                    candidate["npc_id"],
                                    evidence_ids,
                                    testimony_ids,
                                )
                                self._record(
                                    "accuse", accepted=case.accusations[-1].accepted
                                )
                    if case.status == "active":
                        case = await self.next_morning()
                except (ConflictError, AccessDeniedError) as error:
                    self.errors.append(
                        {"action": "policy", "code": type(error).__name__}
                    )
                    case = await self.next_morning()
            if case.status not in {"won", "lost"}:
                raise AssertionError(
                    "Session simulation exhausted its limit without a terminal outcome"
                )
            # Private role access occurs only after the public policy has terminated.
            audit = await self.games.get(game.id)
            wolf = next(
                member.character_id
                for member in audit.characters
                if member.role == "werewolf"
            )
            social = await self.social_repository.get(game.id)
            histories = [
                await self.conversations.history(game.id, identifier)
                for identifier in self.conversation_ids
            ]
            usage = await self.usage.summary(game.id)
            return {
                "seed": self.seed,
                "game_id": str(game.id),
                "policy": policy,
                "mode": self.mode,
                "werewolf_audit_after_game": wolf,
                "result": case.status,
                "day": case.day,
                "ending_method": case.ending.method if case.ending else None,
                "actions": dict(self.actions),
                "errors": self.errors,
                "npc_encounters": len(social.encounters),
                "npc_social_messages": sum(
                    len(encounter.messages) for encounter in social.encounters
                ),
                "knowledge_entries": len(social.knowledge),
                "persisted_player_messages": sum(
                    len(history.messages) for history in histories
                ),
                "graph_traces": len(self.traces),
                "graph_nodes": sorted(
                    {node for item in self.traces for node in item.get("nodes", ())}
                ),
                "llm_calls_by_task": dict(self.model.calls - self.initial_calls),
                "injected_faults": self.model.injected_faults - self.initial_faults,
                "usage": usage.model_dump(mode="json"),
                "trace": self.trace,
            }


async def run_sessions(
    count=100,
    seed=20261105,
    redis_url=None,
    *,
    faults=True,
    live_model=None,
    pricing=None,
):
    if not 1 <= count <= 1000:
        raise ValueError("Choose between one and 1000 sessions")
    run_id = uuid4().hex
    prefix = f"ml:session-simulation:{run_id}"
    redis = (
        Redis.from_url(redis_url, decode_responses=True)
        if redis_url
        else fakeredis.FakeAsyncRedis(decode_responses=True)
    )
    results = []
    try:
        await redis.ping()
        for index in range(count):
            fault: Fault = (
                (
                    "invalid_json_once"
                    if index % 10 == 7
                    else "invalid_json_always"
                    if index % 10 == 8
                    else "authentication"
                    if index % 10 == 9
                    else "none"
                )
                if faults
                else "none"
            )
            simulation = SessionSimulation(
                redis,
                prefix,
                seed + index,
                fault=fault,
                live_model=live_model,
                pricing=pricing,
            )
            result = await simulation.play(POLICIES[index % len(POLICIES)])
            results.append(result)
        return {
            "mode": "live" if live_model else "offline",
            "seed": seed,
            "sessions": results,
            "summary": {
                "games": len(results),
                "terminal_games": sum(
                    item["result"] in {"won", "lost"} for item in results
                ),
                "outcomes": dict(Counter(item["result"] for item in results)),
                "policies": {
                    policy: dict(
                        Counter(
                            item["result"]
                            for item in results
                            if item["policy"] == policy
                        )
                    )
                    for policy in POLICIES
                },
                "werewolves": dict(
                    Counter(item["werewolf_audit_after_game"] for item in results)
                ),
                "calls": sum(
                    sum(item["llm_calls_by_task"].values()) for item in results
                ),
                "real_aws_calls": sum(live_model.calls.values()) if live_model else 0,
                "actual_aws_cost_usd": None if live_model else "0",
                "known_estimated_cost_usd": str(
                    sum(
                        Decimal(item["usage"]["totals"]["known_estimated_cost_usd"])
                        for item in results
                    )
                ),
                "budget_exhausted": live_model.exhausted if live_model else False,
                "token_method": "provider usage metadata"
                if live_model
                else "offline character-count approximation len(text)//4; not Qwen tokenizer usage",
                "quality_scope": "live model, controlled-clock player policy; billing is only an estimate"
                if live_model
                else "mechanics, contracts and persistence only; no measurement of real Qwen narrative quality",
            },
        }
    finally:
        keys = [key async for key in redis.scan_iter(match=f"{prefix}:*")]
        if keys:
            await redis.delete(*keys)
        await redis.aclose()
