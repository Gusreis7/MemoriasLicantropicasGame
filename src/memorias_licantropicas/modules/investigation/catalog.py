"""Apetrechos privados: propriedade não é resposta pública de catálogo."""

from memorias_licantropicas.contracts.investigation import ItemDefinition


def _item(identifier, name, kind, description):
    return ItemDefinition(id=identifier, name=name, kind=kind, description=description)


ITEMS = (
    _item("chave_santiago", "Chave com medalhão Santiago", "unique", "Chave antiga presa a um medalhão gravado com o nome Santiago."),
    _item("estojo_cartas", "Estojo de cartas com olho de cobre", "unique", "Pequeno estojo de cartas marcado com um olho de cobre."),
    _item("prendedor_ancora", "Prendedor de gravata em âncora", "unique", "Prendedor de gravata em forma de âncora com esmalte verde."),
    _item("relogio_quincas", "Relógio com gravação Quincas", "unique", "Relógio de bolso cuja tampa interna traz a gravação Quincas."),
    _item("leque_vn", "Leque com monograma VN", "unique", "Leque de cor ametista com as iniciais VN bordadas."),
    _item("broche_andorinha", "Broche de andorinha", "unique", "Broche de metal em forma de andorinha com um pequeno ramo."),
    _item("lente_hexagonal", "Lente de armação hexagonal", "unique", "Lente de observação em uma pequena armação hexagonal de latão."),
    _item("rosario_seminario", "Rosário de contas irregulares", "unique", "Rosário com três contas de madeira mais claras e uma cruz remendada com fio azul."),
    _item("carta_santiago", "Papel de carta com selo Santiago", "unique", "Folha dobrada com selo Santiago e um recorte triangular feito à mão."),
    _item("pente_olho_cobre", "Pente com olho de cobre", "unique", "Pente de madeira avermelhada com um olho de cobre na haste e um dente reparado."),
    _item("sinete_lua", "Sinete da lua partida", "unique", "Pequeno sinete de latão com meia-lua atravessada por um sulco irregular."),
    _item("caderneta_seminario", "Caderneta de capa azul", "unique", "Caderneta antiga de capa azul, com uma âncora na lombada e três folhas costuradas à mão."),
    _item("abotoadeira_esmeralda", "Abotoadura de esmalte esmeralda", "unique", "Abotoadura de cobre com esmalte verde e uma pequena estrela gravada no verso."),
    _item("abotoadeira_sol", "Abotoadura de sol dourado", "unique", "Abotoadura de sol com um raio torto e uma minúscula marca Q na presilha."),
    _item("medalhao_quincas", "Medalhão de Quincas", "unique", "Medalhão oval com a palavra Quincas por dentro e uma emenda junto à argola."),
    _item("camafeu_vn", "Camafeu de iniciais VN", "unique", "Camafeu de pedra clara montado em metal ametista, com as iniciais VN no fecho."),
    _item("frasco_violeta", "Frasco de violeta lapidado", "unique", "Frasco de perfume de vidro violeta com tampa de sete faces e um pequeno V gravado."),
    _item("dedal_andorinha", "Dedal de andorinha", "unique", "Dedal de cobre com uma andorinha gravada e uma pequena abertura lateral consertada."),
    _item("fivela_manifesto", "Fivela da folha dobrada", "unique", "Fivela de metal em forma de folha dobrada, com uma andorinha minúscula na parte interna."),
    _item("estilete_casa_verde", "Estilete de cabo verde", "unique", "Instrumento de anotações com cabo verde, cabeça sextavada e duas incisões junto à ponta."),
    _item("selo_casa_verde", "Selo hexagonal da Casa Verde", "unique", "Carimbo de latão com borda hexagonal, cruz de linhas finas e uma falha no canto inferior."),
    _item("luvas_couro", "Luvas de couro", "singular", "Um par de luvas de couro escuro, de costura pouco comum."),
    _item("fita_veludo", "Fita de veludo vinho", "singular", "Fita de veludo vinho com acabamento estreito."),
    _item("caderneta_verde", "Caderneta verde", "singular", "Caderneta de capa verde, de um modelo encontrado em poucas mãos."),
    _item("lenco", "Lenço de algodão", "common", "Lenço simples de algodão, sem monograma."),
    _item("botao", "Botão de osso", "common", "Botão de osso claro com quatro furos."),
    _item("pena", "Pena de escrita", "common", "Pena usada para escrever, vendida nas papelarias do bairro."),
    _item("linha", "Linha escura", "common", "Novelo curto de linha escura de costura."),
    _item("cera", "Cera de vela", "common", "Pequeno fragmento de cera de vela comum."),
    _item("cordel", "Pedaço de cordel", "common", "Cordel de fibra vegetal usado em embrulhos."),
    _item("moeda", "Moeda de cobre", "common", "Moeda de cobre corrente, sem marca particular."),
    _item("fosforo", "Caixa de fósforos", "common", "Caixa de fósforos do tipo vendido em diversas vendas."),
    _item("papel", "Papel de embrulho", "common", "Retalho de papel pardo de embrulho."),
    _item("remendo", "Retalho de tecido", "common", "Pequeno remendo de tecido cru, sem inscrição."),
)
ITEMS_BY_ID = {item.id: item for item in ITEMS}

# Os cinco IDs originais são preservados. Cada ficha ganha mais dois objetos pessoais.
# Consumo por tipo: regras não dependem da posição do objeto na tupla.
INVENTORIES = {
    "bentinho": ("chave_santiago", "luvas_couro", "lenco", "botao", "pena"),
    "capitu": ("estojo_cartas", "fita_veludo", "lenco", "linha", "cera"),
    "escobar": ("prendedor_ancora", "luvas_couro", "botao", "cordel", "moeda"),
    "rubiao": ("relogio_quincas", "caderneta_verde", "fosforo", "papel", "remendo"),
    "virgilia": ("leque_vn", "fita_veludo", "linha", "papel", "pena"),
    "florenca": ("broche_andorinha", "fita_veludo", "cordel", "fosforo", "moeda"),
    "bacamarte": ("lente_hexagonal", "caderneta_verde", "cera", "remendo", "lenco"),
}

PERSONAL_EXTRAS = {
    "bentinho": ("rosario_seminario", "carta_santiago"),
    "capitu": ("pente_olho_cobre", "sinete_lua"),
    "escobar": ("caderneta_seminario", "abotoadeira_esmeralda"),
    "rubiao": ("abotoadeira_sol", "medalhao_quincas"),
    "virgilia": ("camafeu_vn", "frasco_violeta"),
    "florenca": ("dedal_andorinha", "fivela_manifesto"),
    "bacamarte": ("estilete_casa_verde", "selo_casa_verde"),
}
INVENTORIES = {person: (*original, *PERSONAL_EXTRAS[person]) for person, original in INVENTORIES.items()}


def items_of_kind(person, kind):
    return tuple(identifier for identifier in INVENTORIES[person] if ITEMS_BY_ID[identifier].kind == kind)


# A marca pertence ao objeto; o exame não dá o nome de quem o deixou na cena.
INSPECTION_DETAILS = {
    "chave_santiago": "O medalhão traz um S com o último traço duplicado; há uma emenda antiga na argola.",
    "estojo_cartas": "O olho de cobre é preso por três rebites desiguais; a dobradiça tem um reparo em X.",
    "prendedor_ancora": "Um dos braços da âncora é mais curto; o esmalte verde foi reposto apenas nessa ponta.",
    "relogio_quincas": "A gravação Quincas tem um Q atravessado; a tampa foi ajustada à mão.",
    "leque_vn": "O fio do monograma VN passa duas vezes no mesmo ponto; uma vareta tem uma emenda de cobre.",
    "broche_andorinha": "A andorinha tem uma asa mais alta e o ramo conserva uma solda irregular.",
    "lente_hexagonal": "Uma face da armação tem duas incisões paralelas; a solda foi feita com excesso de estanho.",
    "rosario_seminario": "As três contas claras foram talhadas à mão; o remendo azul atravessa duas vezes o braço da cruz.",
    "carta_santiago": "O selo Santiago tem uma falha na borda; o recorte triangular coincide com a dobra antiga do papel.",
    "pente_olho_cobre": "O dente reparado é preso por uma lasca em meia-lua; o olho de cobre tem uma pupila dupla.",
    "sinete_lua": "A falha do sinete interrompe a meia-lua em dois pontos, produzindo uma impressão individualizável.",
    "caderneta_seminario": "A âncora da lombada tem um braço riscado; as três folhas foram costuradas com linha de duas cores.",
    "abotoadeira_esmeralda": "A estrela do verso tem uma ponta quebrada; o esmalte verde conserva uma bolha junto ao fecho.",
    "abotoadeira_sol": "O raio torto foi dobrado e endireitado; a marca Q tem um corte oblíquo junto à haste.",
    "medalhao_quincas": "A emenda da argola invade a letra Q; a tampa conserva uma pequena marca de lima.",
    "camafeu_vn": "O N no fecho foi regravado sobre um traço antigo; a pedra tem uma veia em forma de forquilha.",
    "frasco_violeta": "A tampa de sete faces tem uma quina cortada; o V gravado continua pelo bordo do vidro.",
    "dedal_andorinha": "A abertura consertada atravessa uma das asas da andorinha; a solda tem duas gotas alinhadas.",
    "fivela_manifesto": "A dobra da folha é assimétrica; a andorinha interna tem o bico regravado fora do eixo.",
    "estilete_casa_verde": "As duas incisões têm profundidades diferentes; o encaixe do cabo foi reparado com uma cunha de cobre.",
    "selo_casa_verde": "A falha no canto inferior atravessa duas linhas da cruz, deixando uma impressão impossível de confundir com um selo inteiro.",
}

ORDER = tuple(INVENTORIES)
OBSERVED_PEOPLE = {
    npc: tuple(ORDER[(index + step) % len(ORDER)] for step in (1, 2, 3))
    for index, npc in enumerate(ORDER)
}

PREFERRED_VICTIMS = {
    "bentinho": "escobar", "capitu": "escobar", "escobar": "capitu",
    "rubiao": "virgilia", "virgilia": "rubiao", "florenca": "bacamarte",
}
