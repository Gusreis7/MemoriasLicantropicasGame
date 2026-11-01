"""Cinco locais e posições iniciais independentes do sorteio."""

from datetime import UTC, datetime
from uuid import UUID

from memorias_licantropicas.modules.world.model import WorldNPC, WorldPlayer, WorldState
from memorias_licantropicas.modules.world.schema import LocationExit, LocationPublic


def _exit(side, destination, arrival):
    return LocationExit(side=side, target_location_id=destination, arrival_side=arrival)

LOCATIONS: tuple[LocationPublic, ...] = (
    LocationPublic(id="praca_verde", name="Praça Verde", background="/assets/locations/praca_verde.png", exits=(
        _exit("left", "cabana_capitu", "right"), _exit("left", "cafe_largo", "right"),
        _exit("right", "casa_verde", "left"), _exit("right", "cais_lanternas", "left"),
    )),
    LocationPublic(id="cabana_capitu", name="Cabana da Capitu", background="/assets/locations/cabana_capitu.png", exits=(
        _exit("right", "praca_verde", "left"), _exit("left", "cafe_largo", "left"),
    )),
    LocationPublic(id="casa_verde", name="Casa Verde", background="/assets/locations/casa_verde.png", exits=(
        _exit("left", "praca_verde", "right"), _exit("right", "cais_lanternas", "right"),
    )),
    LocationPublic(id="cafe_largo", name="Café do Largo", background="/assets/locations/cafe_largo.png", exits=(
        _exit("right", "praca_verde", "left"), _exit("left", "cabana_capitu", "left"),
    )),
    LocationPublic(id="cais_lanternas", name="Cais das Lanternas", background="/assets/locations/cais_lanternas.png", exits=(
        _exit("left", "praca_verde", "right"), _exit("right", "casa_verde", "right"),
    )),
)
LOCATIONS_BY_ID = {location.id: location for location in LOCATIONS}


def fit_world_to_locations(world: WorldState) -> WorldState:
    """Projeta coordenadas de partidas antigas no cenário compacto, sem novo sorteio.

    O GET não grava: a próxima ação CAS persiste a projeção na mesma revisão.
    Os limites amplos no modelo de persistência permitem ler mundos de 1920px.
    """
    def bounded(x, location_id):
        return min(LOCATIONS_BY_ID[location_id].width - 32, max(32, x))

    return world.model_copy(update={
        "player": world.player.model_copy(update={"x": bounded(world.player.x, world.player.location_id)}),
        "npcs": tuple(npc.model_copy(update={"x": bounded(npc.x, npc.location_id)}) for npc in world.npcs),
    })

INITIAL_NPCS: tuple[WorldNPC, ...] = (
    WorldNPC(npc_id="rubiao", location_id="praca_verde", x=440),
    WorldNPC(npc_id="capitu", location_id="cabana_capitu", x=440),
    WorldNPC(npc_id="virgilia", location_id="cabana_capitu", x=900),
    WorldNPC(npc_id="bacamarte", location_id="casa_verde", x=460),
    WorldNPC(npc_id="bentinho", location_id="cafe_largo", x=460),
    WorldNPC(npc_id="escobar", location_id="cafe_largo", x=900),
    WorldNPC(npc_id="florenca", location_id="cais_lanternas", x=480),
)


def make_initial_world(game_id: UUID) -> WorldState:
    """Usado no bootstrap atômico da partida pela composição/repository de games."""
    return WorldState(
        game_id=game_id,
        player=WorldPlayer(last_updated_at=datetime.now(UTC)),
        npcs=INITIAL_NPCS,
    )
