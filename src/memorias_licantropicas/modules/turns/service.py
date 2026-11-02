"""Cinco minutos de dia, noite não jogável e acontecimentos autoritativos."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from memorias_licantropicas.contracts.errors import ConflictError, NotFoundError, StorageUnavailableError
from memorias_licantropicas.contracts.investigation import (
    CaseEvent, CaseTransition, InvestigationState, JournalEdition,
)
from memorias_licantropicas.contracts.model import GameState
from memorias_licantropicas.modules.turns.repository import RedisTurnRepository
from memorias_licantropicas.modules.world.model import WorldState


class TurnService:
    def __init__(self, redis, prefix, games, characters, world_repository, player_gate,
                 clock: Callable[[], datetime] | None = None,
                 day_seconds: float = 300, night_seconds: float = 8):
        if day_seconds <= 0 or night_seconds <= 0:
            raise ValueError("As durações das fases devem ser positivas.")
        self._repository = RedisTurnRepository(redis, prefix)
        self._games = games
        self._characters = characters
        self._world = world_repository
        self._gate = player_gate
        self._clock = clock or (lambda: datetime.now(UTC))
        self._day_seconds = day_seconds
        self._night_seconds = night_seconds

    def now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("O relógio do ciclo precisa de timezone.")
        return now.astimezone(UTC)

    def _validate_snapshot(self, game, world, state) -> None:
        if game is None:
            raise NotFoundError("Partida não encontrada.")
        if game.content_version != self._characters.content_version:
            raise ConflictError("A partida usa uma versão anterior de personagens.")
        if world is None:
            raise ConflictError("Esta partida não possui mundo visual.")
        if state is not None and state.status != game.status:
            raise StorageUnavailableError("Estado da partida e do ciclo inconsistentes.")

    async def _load(self, game_id: UUID) -> tuple[GameState, WorldState, InvestigationState | None]:
        game = await self._games.get(game_id)
        world = await self._world.get(game_id)
        state = await self._repository.get(game_id)
        self._validate_snapshot(game, world, state)
        return game, world, state

    async def sync(self, game_id: UUID) -> InvestigationState:
        game, world, state = await self._repository.read_snapshot(game_id)
        self._validate_snapshot(game, world, state)
        if state is not None and (state.status != "active" or state.phase == "finished"
                                  or self.now() < state.phase_ends_at):
            return state
        # Só a inicialização ou uma fase vencida exigem reserva. Leituras de um
        # dia em curso continuam disponíveis durante a inferência de uma fala.
        async with self._gate.hold(game_id):
            return await self._sync_locked(game_id)

    async def _sync_locked(self, game_id: UUID) -> InvestigationState:
        from memorias_licantropicas.modules.investigation.rules import make_initial_investigation

        game, world, state = await self._load(game_id)
        now = self.now()
        if state is None:
            state = make_initial_investigation(game, now, day_seconds=self._day_seconds)
            if game.status != "active":
                state = state.model_copy(update={"status": game.status, "phase": "finished"})
            await self._repository.commit(
                previous=None, state=state, previous_game=game, game=game,
                previous_world=world, world=world, occurred_at=now,
                events=(CaseEvent(type="investigation.initialized", data={"legacy": True, "day": state.day}),),
            )
        # Uma noite mata no máximo um civil. Uma detenção inocente pode proteger
        # a última vítima uma vez; depois ela é solta. O catch-up termina no fim.
        for _ in range(2 * len(game.characters) + 4):
            if state.status != "active" or state.phase == "finished" or now < state.phase_ends_at:
                return state
            boundary = state.phase_ends_at
            if state.phase == "day":
                from memorias_licantropicas.modules.investigation.interrogation import record_activities
                records = state.activity_records
                if not any(record.day == state.day and record.period == "day" for record in records):
                    records += record_activities(game, world, state.day, "day", boundary,
                        excluded_ids=(state.detained_npc_id,) if state.detained_npc_id else ())
                updated = state.model_copy(update={
                    "revision": state.revision + 1, "phase": "night",
                    "phase_ends_at": boundary + timedelta(seconds=self._night_seconds),
                    "activity_records": records,
                })
                updated_world = world.model_copy(update={"revision": world.revision + 1,
                    "player": world.player.model_copy(update={"direction": "idle", "last_updated_at": boundary})})
                next_game = game
                events = (CaseEvent(type="night.started", data={"day": state.day}),)
            else:
                updated, next_game, updated_world, events = await self._resolve_night(state, game, world, boundary)
            await self._repository.commit(
                previous=state, state=updated, previous_game=game, game=next_game,
                previous_world=world, world=updated_world, events=events, occurred_at=boundary,
            )
            state, game, world = updated, next_game, updated_world
        raise StorageUnavailableError("O ciclo ultrapassou o limite de recuperação.")

    async def _resolve_night(self, state, game, world, boundary):
        from memorias_licantropicas.modules.investigation.rules import choose_victim, make_crime

        werewolf = next(member.character_id for member in game.characters if member.role == "werewolf")
        day = state.day + 1
        detention = "none"
        victim_id = None
        location_id = None
        crimes = state.crimes
        activity_records = state.activity_records
        events = []
        if state.detained_npc_id == werewolf:
            status = "won"
            detention = "transformed"
            headline = "Lobisomem revela-se na cela; cidade está livre da ameaça"
            body = ("A transformação do detido foi testemunhada na delegacia. "
                    "O lobisomem foi expulso da cidade, encerrando o caso de Floriano.")
            events.append(CaseEvent(type="werewolf.expelled", data={"character_id": werewolf, "day": day}))
        else:
            victim_id = choose_victim(game, detained_npc_id=state.detained_npc_id)
            if victim_id is not None:
                victim = next((member for member in game.characters if member.character_id == victim_id), None)
                if (victim is None or not victim.alive or victim.role != "civil"
                        or victim_id == state.detained_npc_id):
                    raise StorageUnavailableError("Vítima inválida na resolução noturna.")
                placement = next((npc for npc in world.npcs if npc.npc_id == victim_id), None)
                location_id = placement.location_id if placement else "praca_verde"
                crime = make_crime(game, state.day, victim_id, location_id, boundary)
                from memorias_licantropicas.modules.investigation.interrogation import record_activities
                activity_records += record_activities(game, world, state.day, "night", boundary,
                    source="night_resolution", crime=crime,
                    excluded_ids=(state.detained_npc_id,) if state.detained_npc_id else ())
                crimes += (crime,)
                game = game.model_copy(update={"characters": tuple(
                    member.model_copy(update={"alive": False}) if member.character_id == victim_id else member
                    for member in game.characters)})
                profile = await self._characters.get(victim_id)
                name = profile.name if profile else victim_id
                headline = f"Morte de {name} abala a cidade"
                body = f"{name} foi encontrado sem vida. Floriano investiga os vestígios deixados no local."
                events.append(CaseEvent(type="character.killed", data={
                    "victim_id": victim_id, "killer_id": werewolf, "crime_id": str(crime.id),
                    "location_id": location_id, "day": state.day,
                }))
            else:
                headline = "Cidade amanhece sem novas vítimas"
                body = "O Clarim do Rio não registra novas mortes nesta manhã. A investigação continua."
            if state.detained_npc_id:
                detention = "released"
                body += " O detido não se transformou e foi solto pela manhã."
                events.append(CaseEvent(type="suspect.released", data={
                    "character_id": state.detained_npc_id, "day": day,
                }))
            status = "active" if any(member.role == "civil" and member.alive for member in game.characters) else "lost"
            if status == "lost":
                body += " Não restam civis vivos; o caso de Floriano terminou em derrota."
        edition = JournalEdition(day=day, headline=headline, body=body, victim_id=victim_id,
                                 location_id=location_id, detention_outcome=detention)
        game = game.model_copy(update={"status": status})
        updated = state.model_copy(update={
            "revision": state.revision + 1, "day": day,
            "phase": "day" if status == "active" else "finished", "status": status,
            "phase_ends_at": boundary + timedelta(seconds=self._day_seconds) if status == "active" else boundary,
            "crimes": crimes, "journal": state.journal + (edition,), "detained_npc_id": None,
            "activity_records": activity_records,
            "ending_method": "detention" if status == "won" else "survival" if status == "lost" else None,
        })
        world = world.model_copy(update={"revision": world.revision + 1,
            "npcs": tuple(placement for placement in world.npcs
                          if status != "won" or placement.npc_id != werewolf),
            "player": world.player.model_copy(update={"location_id": "praca_verde", "x": 160,
                "facing": "right", "direction": "idle", "last_updated_at": boundary})})
        events.extend((
            CaseEvent(type="night.resolved", data={"day": state.day, "victim_id": victim_id,
                                                  "detention_outcome": detention}),
            CaseEvent(type="journal.published", data={"day": day, "headline": headline,
                "victim_id": victim_id, "location_id": location_id, "detention_outcome": detention}),
        ))
        if status != "active":
            events.append(CaseEvent(type=f"game.{status}", data={"day": day, "werewolf_id": werewolf}))
        return updated, game, world, tuple(events)

    async def require_day_locked(self, game_id: UUID) -> InvestigationState:
        state = await self._sync_locked(game_id)
        if state.status != "active" or state.phase != "day":
            raise ConflictError("A investigação está indisponível nesta fase.")
        return state

    async def assert_dialogue_open(self, game_id: UUID) -> None:
        """Checagem após inferência: o chamador já mantém a reserva do jogador."""
        state = await self._repository.get(game_id)
        if (state is None or state.status != "active" or state.phase != "day"
                or self.now() >= state.phase_ends_at):
            raise ConflictError("O dia terminou; consulte a próxima edição do jornal.")

    async def act(self, game_id: UUID, transition) -> InvestigationState:
        async with self._gate.hold(game_id):
            state = await self.require_day_locked(game_id)
            game, world, _ = await self._load(game_id)
            result = transition(state, game, world)
            if not isinstance(result, CaseTransition):
                raise TypeError("A ação exige uma transição de investigação.")
            confession = self._validated_confession(state, result, game)
            if (result.state.game_id != state.game_id or result.state.day != state.day
                    or (not confession and (result.state.phase != state.phase or result.state.status != state.status))
                    or result.state.phase_ends_at != state.phase_ends_at):
                raise ValueError("Uma ação diurna não pode mudar o relógio ou o resultado.")
            if result.state == state and not result.events:
                return state
            updated = result.state.model_copy(update={"revision": state.revision + 1})
            updated_game = game.model_copy(update={"status": "won"}) if confession else game
            updated_world = world
            if confession:
                updated_world = world.model_copy(update={"revision": world.revision + 1,
                    "npcs": tuple(npc for npc in world.npcs if npc.npc_id != updated.detained_npc_id),
                    "player": world.player.model_copy(update={"direction": "idle", "last_updated_at": self.now()})})
            await self._repository.commit(
                previous=state, state=updated, previous_game=game, game=updated_game,
                previous_world=world, world=updated_world, events=result.events, occurred_at=self.now(),
            )
            return updated

    @staticmethod
    def _validated_confession(state, result, game):
        """Exceção estreita: reavaliar as provas antes de permitir fim diurno."""
        candidate = result.state
        if candidate.status == state.status and candidate.phase == state.phase:
            return False
        if not (candidate.status == "won" and candidate.phase == "finished"
                and candidate.ending_method == "confession"
                and len(candidate.confrontations) == len(state.confrontations) + 1):
            return False
        record = candidate.confrontations[-1]
        if not record.confessed or candidate.detained_npc_id != record.npc_id:
            return False
        from memorias_licantropicas.modules.investigation.interrogation import make_confrontation
        expected = make_confrontation(state, game, record.npc_id, record.evidence_ids,
            record.testimony_ids, record.interrogation_ids, record.created_at)
        if expected.model_dump(exclude={"id"}) != record.model_dump(exclude={"id"}):
            return False
        canonical = state.model_copy(update={"status": "won", "phase": "finished",
            "ending_method": "confession", "detained_npc_id": record.npc_id,
            "confrontations": (*state.confrontations, record)})
        return candidate == canonical and any(event.type == "werewolf.confessed"
            and event.data.get("character_id") == record.npc_id for event in result.events)
