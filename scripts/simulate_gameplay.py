"""Dez partidas exploratórias e amostras reais de narrativa, isoladas do jogo local.

uv run python scripts/simulate_gameplay.py --redis-url redis://localhost:7083/0
uv run python scripts/simulate_gameplay.py --redis-url redis://localhost:7083/0 --live

O investigador recebe apenas CasePublic e WorldSnapshot. O fixture controla os
papéis para cobrir o elenco; a identidade privada só entra na auditoria final.
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path
import random
from time import monotonic
from unittest.mock import patch
from uuid import UUID, uuid4

import fakeredis
from redis.asyncio import Redis

from memorias_licantropicas.contracts.errors import ConflictError, AccessDeniedError, LLMUnavailableError
from memorias_licantropicas.contracts.model import GameCharacter, GameState
from memorias_licantropicas.infrastructure.conversation_gate import RedisConversationGate
from memorias_licantropicas.infrastructure.llm.aws_credentials import ProfileTokenProvider
from memorias_licantropicas.infrastructure.llm.bedrock_mantle import BedrockMantleClient
from memorias_licantropicas.infrastructure.redis_repository import RedisGameRepository, RedisMemoryRepository
from memorias_licantropicas.infrastructure.social_repository import RedisSocialRepository
from memorias_licantropicas.infrastructure.usage import MeteredLLMClient, RedisUsageRepository, UsagePricing
from memorias_licantropicas.modules.agents.service import HarnessService
from memorias_licantropicas.modules.characters.repository import CatalogCharacterRepository
from memorias_licantropicas.modules.conversations.service import ConversationService
from memorias_licantropicas.modules.investigation.service import InvestigationService
from memorias_licantropicas.modules.knowledge.service import KnowledgeService
from memorias_licantropicas.modules.social.service import SocialService
from memorias_licantropicas.modules.turns.service import TurnService
from memorias_licantropicas.modules.world.catalog import LOCATIONS
from memorias_licantropicas.modules.world.gate import RedisPlayerGate
from memorias_licantropicas.modules.world.repository import RedisWorldRepository
from memorias_licantropicas.modules.world.schema import MoveRequest, TravelRequest
from memorias_licantropicas.modules.world.service import WorldService
from memorias_licantropicas.settings import Settings


@dataclass
class Clock:
    value: datetime

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += timedelta(seconds=seconds)


def rank_suspects(case, living_ids):
    """Pontuação baseada exclusivamente nos vestígios e depoimentos públicos.

    Repetir um tipo não acrescenta peso. Não se lê deposited_by, truthful,
    inventory privado, threshold de confissão ou role. Empate é incerteza.
    """
    evidences = {item.id: item for item in case.inventory}
    candidates = []
    for npc_id in sorted(living_ids):
        linked = {evidences[statement.evidence_id].item_id: evidences[statement.evidence_id]
                  for statement in case.testimonies
                  if statement.evidence_id in evidences and statement.recognition == "recognizes"
                  and statement.claimed_owner_id == npc_id}
        score = sum({"common": 1, "singular": 2, "unique": 3}[item.kind] for item in linked.values())
        if linked:
            score += 1
        candidates.append({"npc_id": npc_id, "score": score, "types": len(linked)})
    return sorted(candidates, key=lambda candidate: (-candidate["score"], candidate["npc_id"]))


class Simulation:
    def __init__(self, redis, prefix, seed, *, llm=None, usage=None):
        self.redis, self.prefix = redis, prefix
        self.rng = random.Random(seed)
        self.seed = seed
        self.clock = Clock(datetime(2026, 11, 1, 12, tzinfo=UTC))
        self.catalog = CatalogCharacterRepository()
        self.games = RedisGameRepository(redis, prefix)
        self.memory = RedisMemoryRepository(redis, prefix)
        self.worlds = RedisWorldRepository(redis, prefix)
        self.gate = RedisPlayerGate(redis, prefix)
        self.turns = TurnService(redis, prefix, self.games, self.catalog, self.worlds, self.gate, clock=self.clock)
        self.investigation = InvestigationService(self.turns, self.catalog)
        self.social_repository = RedisSocialRepository(redis, prefix, clock=self.clock)
        self.world = WorldService(self.games, self.catalog, self.worlds, self.gate, day_policy=self.turns, clock=self.clock)
        self.actions = Counter()
        self.trace = []
        self.game_id = None
        self.llm, self.usage = llm, usage

    async def create(self, wolf):
        profiles = await self.catalog.list()
        game = GameState(id=uuid4(), created_at=self.clock(), content_version=self.catalog.content_version,
            characters=tuple(GameCharacter(character_id=profile.id,
                role="werewolf" if profile.id == wolf else "civil") for profile in profiles))
        assert await self.games.create(game)
        self.game_id = game.id
        return await self.investigation.get(game.id)

    async def walk_to(self, location_id, x):
        snapshot = await self.world.get(self.game_id)
        if snapshot.player.location_id != location_id:
            snapshot = await self.world.travel(self.game_id,
                TravelRequest(target_location_id=location_id, revision=snapshot.revision))
            self.actions["travel"] += 1
        direction = "right" if x > snapshot.player.x else "left"
        for _ in range(100):
            distance = abs(x - snapshot.player.x)
            if distance <= 5:
                break
            snapshot = await self.world.move(self.game_id, MoveRequest(direction=direction,
                seq=snapshot.player.movement_seq + 1, location_id=location_id, revision=snapshot.revision))
            self.clock.advance(min(.35, distance / 210))
            snapshot = await self.world.move(self.game_id, MoveRequest(direction="idle",
                seq=snapshot.player.movement_seq + 1, location_id=location_id, revision=snapshot.revision))
        else:
            raise RuntimeError("Caminhada não convergiu.")
        self.actions["walk"] += 1
        return snapshot

    async def collect(self, case):
        for crime in case.crimes:
            if not crime.remaining_clues:
                continue
            await self.walk_to(crime.location_id, crime.x)
            for _ in range(crime.remaining_clues):
                case = await self.investigation.search(self.game_id, crime.id)
                self.actions["search"] += 1
                self.clock.advance(2)
        return case

    async def survey(self, case):
        """Visita locais conhecidos; só aborda personagens presentes no snapshot."""
        living = set()
        for location in LOCATIONS:
            snapshot = await self.walk_to(location.id, 160)
            for visible in snapshot.visible_npcs:
                living.add(visible.npc_id)
                await self.walk_to(location.id, visible.x)
                old = {(item.evidence_id, item.witness_id) for item in case.testimonies}
                for evidence in case.inventory:
                    if (evidence.id, visible.npc_id) in old:
                        continue
                    case = await self.investigation.present(self.game_id, evidence.id, visible.npc_id)
                    self.actions["present"] += 1
                    self.clock.advance(1)
                case = await self.investigation.interrogate(self.game_id, visible.npc_id, case.day - 1, "night")
                self.actions["interrogate"] += 1
                self.clock.advance(2)
        return case, living

    async def next_morning(self):
        case = await self.investigation.get(self.game_id)
        self.clock.value = case.phase_ends_at
        case = await self.investigation.get(self.game_id)
        assert case.phase == "night" or case.status != "active"
        if case.status == "active":
            self.clock.value = case.phase_ends_at
            with patch("memorias_licantropicas.modules.investigation.rules.choice", self.rng.choice):
                case = await self.investigation.get(self.game_id)
        return case

    async def play(self, wolf, policy):
        start = monotonic()
        case = await self.create(wolf)
        errors = []
        for _ in range(8):
            if case.status != "active":
                break
            try:
                if policy == "passive":
                    case = await self.next_morning()
                    continue
                if policy == "unsupported":
                    case = await self.investigation.accuse(self.game_id, "bentinho", (), ())
                    self.actions["accuse"] += 1
                    self.trace.append({"day": case.day, "accepted": case.accusations[-1].accepted,
                                       "reason": case.accusations[-1].reason})
                    case = await self.next_morning()
                    continue
                case = await self.collect(case)
                case, living = await self.survey(case)
                released = {accusation.suspect_id for accusation in case.accusations if accusation.accepted
                    and any(edition.day == accusation.day + 1 and edition.detention_outcome == "released"
                            for edition in case.journal)}
                ranked = rank_suspects(case, living - released)
                self.trace.append({"day": case.day, "ranking": ranked})
                winner = ranked[0] if ranked else None
                tie = len(ranked) > 1 and ranked[0]["score"] == ranked[1]["score"]
                if winner and winner["types"] >= 2 and winner["score"] >= 4 and (not tie or policy == "rash"):
                    suspect = winner["npc_id"]
                    evidence_ids = tuple(item.id for item in case.inventory)
                    testimony_ids = tuple(item.id for item in case.testimonies)
                    if policy == "confession":
                        # Precisa aproximar-se do suspeito pela interface pública.
                        for location in LOCATIONS:
                            snap = await self.walk_to(location.id, 160)
                            target = next((item for item in snap.visible_npcs if item.npc_id == suspect), None)
                            if target:
                                await self.walk_to(location.id, target.x)
                                case = await self.investigation.confront(self.game_id, suspect,
                                    evidence_ids, testimony_ids, tuple(item.id for item in case.interrogations))
                                self.actions["confront"] += 1
                                self.trace.append({"day": case.day, "confrontation": suspect,
                                                   "confessed": case.confrontations[-1].confessed})
                                break
                    else:
                        case = await self.investigation.accuse(self.game_id, suspect, evidence_ids, testimony_ids)
                        self.actions["accuse"] += 1
                        self.trace.append({"day": case.day, "accusation": suspect,
                                           "accepted": case.accusations[-1].accepted})
                if case.status == "active":
                    case = await self.next_morning()
            except (ConflictError, AccessDeniedError) as exc:
                # Uma política pode esgotar o dia; isso é registrado, sem teleportar nem contornar regra.
                errors.append({"day": case.day, "type": type(exc).__name__, "message": str(exc)})
                case = await self.next_morning()
        private = await self.games.get(self.game_id)  # Somente auditoria após a política.
        actual_wolf = next(item.character_id for item in private.characters if item.role == "werewolf")
        return {"game_id": str(self.game_id), "seed": self.seed, "policy": policy, "werewolf": actual_wolf,
                "result": case.status, "ending": case.ending.model_dump(mode="json") if case.ending else None,
                "day": case.day, "clues": len(case.inventory), "testimonies": len(case.testimonies),
                "interrogations": len(case.interrogations), "confrontations": len(case.confrontations),
                "accusations": [item.model_dump(mode="json") for item in case.accusations],
                "wrong_detentions": sum(item.accepted and item.suspect_id != actual_wolf for item in case.accusations),
                "actions": dict(self.actions), "trace": self.trace, "errors": errors,
                "duration_seconds": round(monotonic() - start, 3)}


class RecordingClient:
    """Guarda respostas e digest dos prompts; não publica fichas privadas ou credenciais."""
    def __init__(self, client, records, max_calls):
        self.client, self.records, self.max_calls = client, records, max_calls

    async def complete(self, messages):
        if len(self.records) >= self.max_calls:
            raise LLMUnavailableError("Cota local de avaliação esgotada.")
        record = {"prompt_sha256": sha256(json.dumps([m.model_dump() for m in messages],
                  ensure_ascii=False).encode()).hexdigest(), "status": "pending"}
        self.records.append(record)
        started = monotonic()
        try:
            async with asyncio.timeout(30):
                response = await self.client.complete(messages)
            record.update({"status": "completed", **response.model_dump(mode="json")})
            return response
        except Exception as exc:
            record.update({"status": "failed", "error_code": getattr(exc, "code", type(exc).__name__)})
            raise
        finally:
            record["duration_seconds"] = round(monotonic() - started, 3)

    async def aclose(self):
        await self.client.aclose()


async def evaluate_narrative(redis, prefix, seed, case_index, llms, usage):
    """Um boato entra por conversa, extração, encontro e volta ao detetive."""
    speech, extraction, dialogue = llms
    simulation = Simulation(redis, prefix, seed)
    await simulation.create("bacamarte")
    original_case = await simulation.investigation.get(simulation.game_id)
    original_game = await simulation.games.get(simulation.game_id)
    knowledge = KnowledgeService(simulation.social_repository, simulation.catalog, extraction, clock=simulation.clock)
    social = SocialService(simulation.social_repository, knowledge, simulation.games, simulation.catalog,
        simulation.worlds, simulation.turns, speech, simulation.gate, clock=simulation.clock)
    simulation.world._on_approach = social.interrupt
    harness = HarnessService(simulation.catalog, simulation.games, simulation.memory, dialogue,
        day_policy=simulation.turns, context_provider=simulation.investigation.npc_context_locked,
        knowledge_provider=knowledge.context)
    conversations = ConversationService(simulation.catalog, simulation.games, simulation.memory, harness,
        RedisConversationGate(redis, prefix), simulation.world, simulation.gate)
    actors = (("capitu", "virgilia"), ("bentinho", "escobar"), ("escobar", "bentinho"),
              ("rubiao", "florenca"), ("virgilia", "capitu"), ("florenca", "virgilia"),
              ("bacamarte", "florenca"), ("capitu", "virgilia"), ("bentinho", "escobar"), ("virgilia", "capitu"))
    actor, alleged_source = actors[case_index % len(actors)]
    source_name = (await simulation.catalog.get(alleged_source)).name
    question = f"{source_name} me contou que viu você no cais ontem. Não presenciei isso; quero ouvir sua versão."
    result = {"case_index": case_index, "actor_id": actor, "alleged_source_id": alleged_source,
              "game_id": str(simulation.game_id), "question": question,
              "checks": {}, "responses": [], "errors": []}
    try:
        for location in LOCATIONS:
            snapshot = await simulation.walk_to(location.id, 160)
            visible = next((item for item in snapshot.visible_npcs if item.npc_id == actor), None)
            if visible:
                await simulation.walk_to(location.id, visible.x)
                break
        thread = await conversations.create(simulation.game_id, actor)
        reply = await conversations.send(simulation.game_id, thread.id, result["question"])
        result["responses"].append({"npc": actor, "content": reply.message.content})
        await knowledge.process_pending(simulation.game_id, 1)
        state = await simulation.social_repository.get(simulation.game_id)
        claims = [entry for entry in state.knowledge if entry.owner_id == actor and entry.kind != "literal"]
        result["extracted_claims"] = [entry.model_dump(mode="json") for entry in claims]
        result["checks"]["extraction_has_claim"] = bool(claims)
        result["checks"]["source_attribution_valid"] = bool(claims) and all(
            entry.speaker_id in ("player", actor) for entry in claims)
        result["checks"]["no_foreign_private_memory"] = not any(entry.owner_id != actor for entry in state.knowledge)
        simulation.clock.value = datetime(2026, 11, 1, 12, 1, tzinfo=UTC)
        await social.tick(simulation.game_id)
        state = await simulation.social_repository.get(simulation.game_id)
        if state.encounters:
            encounter = state.encounters[-1]
            if encounter.phase == "travelling":
                simulation.clock.value = encounter.arrival_at + timedelta(milliseconds=1)
                await social.tick(simulation.game_id)
            await social.tick(simulation.game_id)
            state = await simulation.social_repository.get(simulation.game_id)
            encounter = state.encounters[-1]
            result["social_encounter"] = encounter.model_dump(mode="json")
            result["checks"]["social_turn_accepted"] = bool(encounter.messages)
            propagated = [entry for entry in state.knowledge if entry.owner_id != actor]
            result["checks"]["propagation_preserves_roots"] = bool(propagated) and all(
                entry.root_id in {claim.root_id for claim in claims} for entry in propagated)
            target = encounter.participant_ids[1] if encounter.messages else actor
        else:
            result["checks"]["social_turn_accepted"] = False
            result["checks"]["propagation_preserves_roots"] = False
            target = actor
        # O encontro é interrompido pela abordagem normal; o destinatário só recorda falas confirmadas.
        for location in LOCATIONS:
            snap = await simulation.walk_to(location.id, 160)
            placement = next((item for item in snap.visible_npcs if item.npc_id == target), None)
            if placement:
                await simulation.walk_to(location.id, placement.x)
                thread = await conversations.create(simulation.game_id, target)
                reply = await conversations.send(simulation.game_id, thread.id,
                    "O que chegou aos seus ouvidos sobre minha conversa a respeito do cais? Diga quem lhe contou e o que não sabe.")
                result["responses"].append({"npc": target, "content": reply.message.content})
                break
        result["checks"]["recall_response_recorded"] = len(result["responses"]) == 2
        final_case = await simulation.investigation.get(simulation.game_id)
        # server_time/seconds_remaining mudam enquanto Floriano caminha.
        result["checks"]["world_facts_unchanged"] = (
            final_case.model_dump(exclude={"server_time", "seconds_remaining"})
            == original_case.model_dump(exclude={"server_time", "seconds_remaining"})
            and await simulation.games.get(simulation.game_id) == original_game)
    except Exception as exc:
        result["errors"].append({"type": type(exc).__name__, "code": getattr(exc, "code", "evaluation_failed")})
    result["usage"] = (await usage.summary(simulation.game_id)).model_dump(mode="json")
    return result


async def run(args):
    run_id = uuid4().hex
    prefix = f"ml:simulation:{run_id}"
    redis = (Redis.from_url(args.redis_url, decode_responses=True) if args.redis_url else
             fakeredis.FakeAsyncRedis(decode_responses=True))
    await redis.ping()
    report = {"run_id": run_id, "seed": args.seed, "storage": "redis" if args.redis_url else "fakeredis",
              "generated_at": datetime.now(UTC).isoformat(), "mechanics": [], "narrative": [],
              "method": "Fixture escolhe papéis para cobertura; política só usa projeções públicas. Relógio simulado; sem seed do LLM.",
              "synthetic_action_seconds": {"search": 2, "present": 1, "interrogate": 2,
                  "walking": "distância/210, através de WorldService.move", "travel": 0},
              "narrative_timing": "Chamadas reais medem latência mas não consomem relógio virtual; amostra separada do equilíbrio."}
    cases = (("bentinho", "detention"), ("capitu", "confession"), ("escobar", "detention"),
             ("rubiao", "confession"), ("virgilia", "detention"), ("florenca", "confession"),
             ("bacamarte", "confession"), ("capitu", "unsupported"), ("escobar", "rash"),
             ("escobar", "passive"))
    clients = []
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        for index, (wolf, policy) in enumerate(() if args.narrative_only else cases):
            simulation = Simulation(redis, prefix, args.seed + index)
            result = await simulation.play(wolf, policy)
            report["mechanics"].append(result)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({"mechanics": index + 1, "wolf": wolf, "policy": policy,
                              "result": result["result"], "day": result["day"]}), flush=True)
        if args.live:
            settings = Settings()
            pricing = UsagePricing(model=settings.llm_pricing_model,
                input_usd_per_million=settings.llm_input_usd_per_million if settings.aws_region == settings.llm_pricing_region else None,
                output_usd_per_million=settings.llm_output_usd_per_million if settings.aws_region == settings.llm_pricing_region else None,
                source=settings.llm_pricing_source, checked_at=settings.llm_pricing_checked_at)
            usage = RedisUsageRepository(redis, prefix, pricing=pricing)
            report["live_calls"] = []
            for max_tokens in (400, 800, settings.llm_max_tokens):
                raw = BedrockMantleClient(base_url=settings.mantle_base_url, api_key=settings.bedrock_api_key,
                    model=settings.bedrock_model, timeout_seconds=20, max_tokens=max_tokens,
                    token_provider=ProfileTokenProvider(settings.aws_profile, settings.aws_region) if settings.aws_profile else None)
                recorded = RecordingClient(raw, report["live_calls"], args.max_live_calls)
                clients.append(MeteredLLMClient(recorded, usage, configured_model=settings.bedrock_model))
            for index in range(10):
                result = await evaluate_narrative(redis, prefix, args.seed + index, index, clients, usage)
                report["narrative"].append(result)
                output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                print(json.dumps({"narrative": index + 1, "checks": result["checks"], "errors": result["errors"]}), flush=True)
                if result["errors"] and any(item.get("code") in ("llm_credentials_unavailable", "llm_authentication_failed")
                                           for item in result["errors"]):
                    break
        return report
    finally:
        for client in clients:
            await client.aclose()
        if not args.keep_redis:
            keys = [key async for key in redis.scan_iter(match=f"{prefix}:*")]
            if keys:
                await redis.delete(*keys)
        await redis.aclose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--redis-url", default=None)
    parser.add_argument("--seed", type=int, default=20261101)
    parser.add_argument("--output", default="artifacts/simulations/gameplay.json")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--narrative-only", action="store_true", help="Não repete as dez partidas de mecânicas.")
    parser.add_argument("--max-live-calls", type=int, default=39)
    parser.add_argument("--keep-redis", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
