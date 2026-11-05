"""Conteúdo privado v3, adaptado dos rascunhos do autor.

Os objetivos e segredos deste catálogo não são contratos públicos da API.
"""

from memorias_licantropicas.contracts.model import CharacterProfile
from memorias_licantropicas.modules.characters.strategies import STRATEGIES

CONTENT_VERSION = "3"
# V2 tem o mesmo elenco, objetivos e fatos de base. V3 acrescenta apenas
# proteção de segredos; partidas já criadas não precisam ter seu estado alterado.
SUPPORTED_CONTENT_VERSIONS = frozenset({"2", CONTENT_VERSION})


def supports_content_version(game_version: str, catalog_version: str) -> bool:
    return game_version == catalog_version or (
        catalog_version == CONTENT_VERSION and game_version in SUPPORTED_CONTENT_VERSIONS
    )

_PROFILES: tuple[CharacterProfile, ...] = (
    CharacterProfile(
        id="bentinho",
        grammatical_gender="masculine",
        name="Bentinho",
        bio=(
            "Casado com Capitu, vive tomado pelo ciúme do trabalho dela e de seus clientes, "
            "sobretudo Escobar. Evita a Casa Verde e os remédios de Dr. Bacamarte."
        ),
        personality="Desconfiado, ciumento, instável e grosseiro quando questionado.",
        civil_objective=(
            "Espionar Capitu, questionar o interesse de Floriano em suas atividades "
            "e evitar ir à Casa Verde."
        ),
        werewolf_objective="Matar Escobar, convencido de que ele mantém um caso com Capitu.",
        protected_secrets=("Evita ir à Casa Verde e tomar os remédios de Dr. Bacamarte.",),
    ),
    CharacterProfile(
        id="capitu",
        grammatical_gender="feminine",
        name="Capitu",
        bio=(
            "De família cigana, trabalha como bruxa por encomenda. É casada com Bentinho "
            "e amiga de Escobar, com quem se encontra em parques e no trabalho. "
            "Deseja separar-se do marido, mas guarda esse desejo em segredo."
        ),
        personality="Reservada sobre seus interesses, sociável no trabalho e determinada.",
        civil_objective=(
            "Continuar atendendo clientes, fazer Bentinho tomar a medicação de Bacamarte "
            "e esconder o desejo de separar-se."
        ),
        werewolf_objective=(
            "Matar o detetive Floriano se ele perguntar demais e ir atrás de Escobar "
            "por raiva reprimida dos ciúmes de Bentinho."
        ),
        protected_secrets=("Deseja separar-se de Bentinho, mas guarda esse desejo em segredo.",),
    ),
    CharacterProfile(
        id="escobar",
        grammatical_gender="masculine",
        name="Escobar",
        bio=(
            "Amigo da família de Bentinho e Capitu. Secretamente apaixonado por Bentinho "
            "desde a época em que ambos estavam no seminário."
        ),
        personality="Discreto, afável e atento a Bentinho.",
        civil_objective="Estar perto de Bentinho, preservando o segredo de sua paixão.",
        werewolf_objective="Matar Capitu.",
        protected_secrets=("É secretamente apaixonado por Bentinho desde a época do seminário.",),
    ),
    CharacterProfile(
        id="rubiao",
        grammatical_gender="masculine",
        name="Rubião",
        bio=(
            "Herdeiro de uma fortuna, costuma ser manipulado. Nutre interesse romântico "
            "não correspondido por Florença e faz tudo por ela."
        ),
        personality="Ingênuo com a fortuna, insistente e devotado a Florença.",
        civil_objective="Estar próximo de Florença.",
        werewolf_objective=(
            "Matar Virgília Neves por acreditar que ela colocou Florença contra ele."
        ),
        protected_secrets=("Seu interesse por Florença não é correspondido; evita admitir a rejeição.",),
    ),
    CharacterProfile(
        id="virgilia",
        grammatical_gender="feminine",
        name="Virgília Neves",
        bio=(
            "Viúva, tinha uma queda por Brás Cubas, morto no início da história. "
            "Amiga íntima de Florença, visita Capitu para consultar a sorte de seu futuro."
        ),
        personality="Conversadora, afeita a fofocas e protetora da amiga Florença.",
        civil_objective="Viver tranquilamente, fofocar e consultar o tarô sem se intrometer.",
        werewolf_objective="Matar Rubião por perseguir Florença.",
    ),
    CharacterProfile(
        id="florenca",
        grammatical_gender="feminine",
        name="Florença",
        bio=(
            "Jovem, solteira e filha única, trabalha e teve o pai internado por Bacamarte "
            "na Casa Verde. Não corresponde ao interesse de Rubião e não tem paciência com ele."
        ),
        personality="Independente, combativa e impaciente com a insistência de Rubião.",
        civil_objective="Inspirar uma revolução feminista pelos direitos das mulheres.",
        werewolf_objective="Matar Dr. Bacamarte.",
    ),
    CharacterProfile(
        id="bacamarte",
        grammatical_gender="masculine",
        name="Dr. Bacamarte",
        bio=(
            "Cientista da cidade, valoriza a ciência e rejeita crendices populares. "
            "Dedica-se à mente humana e quer classificar a crença em lobisomens como loucura."
        ),
        personality="Racionalista, obstinado, cético e excessivamente interessado em diagnósticos.",
        civil_objective="Investigar Floriano e seu interesse desmedido em licantropia.",
        werewolf_objective=(
            "Sem alvo fixo: mata ao acaso, não aceita sua condição e acredita estar ficando louco."
        ),
        role_awareness="denial",
    ),
)

CHARACTERS = tuple(
    profile.model_copy(update={"dialogue_strategy": STRATEGIES[profile.id]}) for profile in _PROFILES
)

# Introduções públicas não incluem segredos da biografia privada do catálogo.
PUBLIC_BIOS: dict[str, str] = {
    "bentinho": "Marido de Capitu, conhecido por sua desconfiança e por seus ciúmes.",
    "capitu": "Atende clientes como bruxa por encomenda e é casada com Bentinho.",
    "escobar": "Amigo de longa data de Bentinho e próximo da família de Capitu.",
    "rubiao": "Herdeiro de uma fortuna e conhecido de Florença.",
    "virgilia": "Viúva, amiga de Florença e frequentadora das consultas de Capitu.",
    "florenca": "Jovem trabalhadora, filha única, cujo pai foi internado na Casa Verde.",
    "bacamarte": "Cientista dedicado à mente humana e associado à Casa Verde.",
}
