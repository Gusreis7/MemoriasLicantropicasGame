"""Regras da exploração: o cliente envia intenção, o servidor calcula deslocamento."""
from datetime import timedelta
from memorias_licantropicas.contracts.errors import InteractionUnavailableError

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from memorias_licantropicas.contracts.errors import AccessDeniedError, ConflictError, NotFoundError
from memorias_licantropicas.contracts.model import GameState
from memorias_licantropicas.contracts.repository import CharacterRepository, GameRepository, DayPolicy
from memorias_licantropicas.contracts.investigation import InvestigationState
from memorias_licantropicas.modules.world.catalog import LOCATIONS, LOCATIONS_BY_ID
from memorias_licantropicas.modules.characters.catalog import supports_content_version
from memorias_licantropicas.modules.world.gate import RedisPlayerGate
from memorias_licantropicas.modules.world.model import WorldState
from memorias_licantropicas.modules.world.repository import RedisWorldRepository
from memorias_licantropicas.modules.world.schema import (
    MoveRequest, PlayerPublic, TravelRequest, VisibleNPC, WorldSnapshot,
)

WALK_SPEED = 210
MAX_MOVEMENT_SECONDS = 0.4
APPROACH_DISTANCE = 64
EXIT_DISTANCE = 56
ARRIVAL_INSET = 96


class WorldService:
    def __init__(self, games: GameRepository, characters: CharacterRepository,
                 repository: RedisWorldRepository, gate: RedisPlayerGate,
                 clock: Callable[[], datetime] | None = None, day_policy: DayPolicy | None = None,
                 on_approach: Callable[[UUID, str], Awaitable[None]] | None = None, social_repository=None):
        self._games = games
        self._characters = characters
        self._repository = repository
        self._gate = gate
        self._clock = clock or (lambda: datetime.now(UTC))
        self._day_policy = day_policy
        self._on_approach = on_approach
        self._social_repository = social_repository

    async def _load(self, game_id: UUID) -> tuple[GameState, WorldState]:
        game = await self._games.get(game_id)
        if game is None:
            raise NotFoundError("Partida não encontrada.")
        if not supports_content_version(game.content_version, self._characters.content_version):
            raise ConflictError("A partida usa uma versão anterior de personagens.")
        world = await self._repository.get(game_id)
        if world is None:
            raise ConflictError("Esta partida não possui mundo visual; crie uma nova partida.")
        return game, world

    async def _snapshot(self, game: GameState, world: WorldState,
                        case: InvestigationState | None = None) -> WorldSnapshot:
        cast = {character.character_id: character for character in game.characters}
        visible_ids = {placement.npc_id for placement in world.npcs
                       if placement.location_id == world.player.location_id
                       and placement.activity != "travelling"
                       and placement.npc_id in cast and cast[placement.npc_id].alive
                       and (case is None or placement.npc_id != case.detained_npc_id)}
        from memorias_licantropicas.modules.world.motion import project_npc
        speech = {}
        if self._social_repository:
            social = await self._social_repository.get(game.id)
            for encounter in social.encounters:
                if encounter.location_id == world.player.location_id:
                    for message in encounter.messages:
                        age = (self._clock() - message.created_at).total_seconds()
                        if 0 <= age <= 12:
                            speech[message.sender_id] = message.content
        visible = []
        presences = []
        for placement in world.npcs:
            member = cast.get(placement.npc_id)
            if member is None or not member.alive or (case and placement.npc_id in case.expelled_npc_ids):
                continue
            if case and placement.npc_id == case.detained_npc_id:
                continue
            if placement.activity == "travelling" and (not placement.travel_started_at or not placement.travel_route):
                continue
            projected_location, projected_x = project_npc(placement, self._clock())
            profile = await self._characters.get(placement.npc_id)
            presences.append({"npc_id": placement.npc_id, "name": profile.name if profile else placement.npc_id,
                "location_id": projected_location, "activity": placement.activity,
                "destination_id": placement.travel_destination_id if placement.activity == "travelling" else None})
            if projected_location != world.player.location_id:
                continue
            if case is not None and placement.npc_id == case.detained_npc_id:
                continue
            profile = await self._characters.get(placement.npc_id)
            if profile is None:
                raise ConflictError("Ficha do personagem indisponível.")
            visible.append(VisibleNPC(
                npc_id=profile.id, name=profile.name, x=projected_x, sprite_id=profile.id,
                can_approach=placement.activity != "travelling" and (case is None or case.phase == "day") and abs(placement.x - world.player.x) <= APPROACH_DISTANCE,
                activity=placement.activity,
                speech=speech.get(profile.id) if abs(projected_x - world.player.x) <= 180 else None,
                social_partner_id=(placement.social_partner_id if placement.activity == "talking"
                                   and placement.social_partner_id in visible_ids else None),
            ))
        return WorldSnapshot(
            game_id=world.game_id, world_version=world.world_version, revision=world.revision,
            location=LOCATIONS_BY_ID[world.player.location_id],
            player=PlayerPublic(location_id=world.player.location_id, x=world.player.x,
                                facing=world.player.facing, movement_seq=world.player.movement_seq),
            visible_npcs=tuple(visible), npc_presences=tuple(presences),
            travel_targets=tuple(location.id for location in LOCATIONS if location.id != world.player.location_id),
        )

    async def get(self, game_id: UUID) -> WorldSnapshot:
        case = await self._day_policy.sync(game_id) if self._day_policy else None
        game, world = await self._load(game_id)
        return await self._snapshot(game, world, case)

    async def move(self, game_id: UUID, body: MoveRequest) -> WorldSnapshot:
        async with self._gate.hold(game_id):
            case = await self._day_policy.require_day_locked(game_id) if self._day_policy else None
            game, world = await self._load(game_id)
            if body.revision != world.revision or body.location_id != world.player.location_id:
                raise ConflictError("Local ou revisão desatualizado; consulte o mundo atual.")
            if body.seq <= world.player.movement_seq:
                raise ConflictError("Sequência de movimento já processada ou desatualizada.")
            now = self._clock()
            elapsed = min(MAX_MOVEMENT_SECONDS, max(0, (now - world.player.last_updated_at).total_seconds()))
            direction = -1 if world.player.direction == "left" else 1 if world.player.direction == "right" else 0
            location = LOCATIONS_BY_ID[world.player.location_id]
            x = min(location.width - 32, max(32, world.player.x + direction * WALK_SPEED * elapsed))
            player = world.player.model_copy(update={
                "x": x, "direction": body.direction, "movement_seq": body.seq,
                "facing": body.direction if body.direction != "idle" else world.player.facing,
                "last_updated_at": now,
            })
            updated = world.model_copy(update={"revision": world.revision + 1, "player": player})
            if not await self._repository.save(updated, expected_revision=world.revision):
                raise ConflictError("O mundo mudou; consulte a revisão atual.")
            return await self._snapshot(game, updated, case)

    async def travel(self, game_id: UUID, body: TravelRequest) -> WorldSnapshot:
        async with self._gate.hold(game_id):
            case = await self._day_policy.require_day_locked(game_id) if self._day_policy else None
            game, world = await self._load(game_id)
            if body.revision != world.revision:
                raise ConflictError("Revisão desatualizada; consulte o mundo atual.")
            if body.target_location_id == world.player.location_id and body.exit_side is None:
                raise ConflictError("O jogador já está neste local.")
            arrival_side = "left"
            spawn_x = 160
            if body.exit_side is not None:
                origin = LOCATIONS_BY_ID[world.player.location_id]
                at_edge = (world.player.x <= EXIT_DISTANCE if body.exit_side == "left"
                           else world.player.x >= origin.width - EXIT_DISTANCE)
                if not at_edge:
                    raise AccessDeniedError("Aproxime-se da saída para seguir por este caminho.")
                if body.target_location_id == origin.id:
                    arrival_side = "right" if body.exit_side == "left" else "left"
                else:
                    route = next((route for route in origin.exits
                                  if route.side == body.exit_side
                                  and route.target_location_id == body.target_location_id), None)
                    if route is None:
                        raise AccessDeniedError("Este destino não está ligado à saída escolhida.")
                    arrival_side = route.arrival_side
                target = LOCATIONS_BY_ID[body.target_location_id]
                spawn_x = ARRIVAL_INSET if arrival_side == "left" else target.width - ARRIVAL_INSET
            now = self._clock()
            player = world.player.model_copy(update={
                "location_id": body.target_location_id, "x": spawn_x, "direction": "idle",
                "facing": "right" if arrival_side == "left" else "left", "last_updated_at": now,
            })
            updated = world.model_copy(update={"revision": world.revision + 1, "player": player})
            event = {
                "id": str(uuid4()), "type": "player.travelled", "occurred_at": now.isoformat(),
                "source": "world", "data": {
                    "player_id": "player", "from_location_id": world.player.location_id,
                    "to_location_id": body.target_location_id,
                    "exit_side": body.exit_side,
                    "arrival_side": arrival_side if body.exit_side else None,
                },
            }
            if not await self._repository.save(updated, expected_revision=world.revision, event=event):
                raise ConflictError("O mundo mudou; consulte a revisão atual.")
            return await self._snapshot(game, updated, case)

    async def assert_can_talk(self, game_id: UUID, npc_id: str) -> None:
        """Não adquire reserva: o chamador mantém a reserva de ação durante o diálogo."""
        if self._day_policy:
            case = await self._day_policy.require_day_locked(game_id)
            if case.detained_npc_id == npc_id:
                raise InteractionUnavailableError("npc_detained")
        game, world = await self._load(game_id)
        npc = next((member for member in game.characters if member.character_id == npc_id), None)
        if npc is None:
            raise NotFoundError("Persona não encontrada nesta partida.")
        if not npc.alive:
            raise InteractionUnavailableError("npc_unavailable")
        placement = next((member for member in world.npcs if member.npc_id == npc_id), None)
        if placement is None or placement.location_id != world.player.location_id:
            raise InteractionUnavailableError("npc_away")
        if placement.activity == "travelling":
            raise InteractionUnavailableError("npc_travelling")
        if abs(placement.x - world.player.x) > APPROACH_DISTANCE:
            raise InteractionUnavailableError("npc_too_far")
        if self._on_approach is not None:
            await self._on_approach(game_id, npc_id)

        # A reserva da ação protege a transição; o prazo protege também a leitura
        # entre mensagens, quando nenhuma inferência mantém o player gate.
        world = await self._repository.get(game_id)
        expiry = self._clock() + timedelta(seconds=90)
        if self._day_policy:
            expiry = min(expiry, case.phase_ends_at)
        if any(n.npc_id == npc_id and n.player_engaged_until and n.player_engaged_until >= expiry - timedelta(seconds=25) for n in world.npcs):
            return
        updated = world.model_copy(update={"revision": world.revision + 1, "npcs": tuple(
            n.model_copy(update={"player_engaged_until": expiry}) if n.npc_id == npc_id
            else n.model_copy(update={"player_engaged_until": None}) if n.player_engaged_until else n
            for n in world.npcs)})
        if not await self._repository.save(updated, expected_revision=world.revision):
            raise ConflictError("O mundo mudou durante a abordagem; tente novamente.")

    async def release_dialogue(self, game_id, npc_id):
        world = await self._repository.get(game_id)
        if world is None or not any(n.npc_id == npc_id and n.player_engaged_until for n in world.npcs):
            return
        updated = world.model_copy(update={"revision": world.revision + 1, "npcs": tuple(
            n.model_copy(update={"player_engaged_until": None}) if n.npc_id == npc_id else n for n in world.npcs)})
        if not await self._repository.save(updated, expected_revision=world.revision):
            raise ConflictError("O mundo mudou ao encerrar a conversa.")
