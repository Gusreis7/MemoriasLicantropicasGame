"""Cinco locais e posições iniciais independentes do sorteio."""

from datetime import UTC, datetime
from uuid import UUID

from memorias_licantropicas.modules.world.model import WorldNPC, WorldPlayer, WorldState
from memorias_licantropicas.modules.world.schema import LocationPublic

LOCATIONS: tuple[LocationPublic, ...] = (
    LocationPublic(id="praca_verde", name="Praça Verde", background="/assets/locations/praca_verde.png"),
    LocationPublic(id="cabana_capitu", name="Cabana da Capitu", background="/assets/locations/cabana_capitu.png"),
    LocationPublic(id="casa_verde", name="Casa Verde", background="/assets/locations/casa_verde.png"),
    LocationPublic(id="cafe_largo", name="Café do Largo", background="/assets/locations/cafe_largo.png"),
    LocationPublic(id="cais_lanternas", name="Cais das Lanternas", background="/assets/locations/cais_lanternas.png"),
)
LOCATIONS_BY_ID = {location.id: location for location in LOCATIONS}

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
