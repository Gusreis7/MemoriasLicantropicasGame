"""Conteúdo privado v1, adaptado dos rascunhos do autor.

Os objetivos e segredos deste catálogo não são contratos públicos da API.
"""

from memorias_licantropicas.contracts.model import CharacterProfile

CONTENT_VERSION = "1"

CHARACTERS: tuple[CharacterProfile, ...] = (
    CharacterProfile(
        id="bentinho",
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
    ),
    CharacterProfile(
        id="capitu",
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
            "por raiva reprimida dos ciúmes de Bentinho. As condições exatas ainda serão definidas."
        ),
    ),
    CharacterProfile(
        id="escobar",
        name="Escobar",
        bio=(
            "Amigo da família de Bentinho e Capitu. Secretamente apaixonado por Bentinho "
            "desde a época em que ambos estavam no seminário."
        ),
        personality="Discreto, afável e atento a Bentinho.",
        civil_objective="Estar perto de Bentinho, preservando o segredo de sua paixão.",
        werewolf_objective="Matar Capitu.",
    ),
    CharacterProfile(
        id="rubiao",
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
    ),
    CharacterProfile(
        id="virgilia",
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
