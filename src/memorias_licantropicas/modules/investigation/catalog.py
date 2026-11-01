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

# Ordem estável: exclusivo, singular e três comuns. Não depende do sorteio.
INVENTORIES = {
    "bentinho": ("chave_santiago", "luvas_couro", "lenco", "botao", "pena"),
    "capitu": ("estojo_cartas", "fita_veludo", "lenco", "linha", "cera"),
    "escobar": ("prendedor_ancora", "luvas_couro", "botao", "cordel", "moeda"),
    "rubiao": ("relogio_quincas", "caderneta_verde", "fosforo", "papel", "remendo"),
    "virgilia": ("leque_vn", "fita_veludo", "linha", "papel", "pena"),
    "florenca": ("broche_andorinha", "fita_veludo", "cordel", "fosforo", "moeda"),
    "bacamarte": ("lente_hexagonal", "caderneta_verde", "cera", "remendo", "lenco"),
}

ORDER = tuple(INVENTORIES)
OBSERVED_PEOPLE = {
    npc: (ORDER[(index + 1) % len(ORDER)], ORDER[(index + 2) % len(ORDER)])
    for index, npc in enumerate(ORDER)
}

PREFERRED_VICTIMS = {
    "bentinho": "escobar", "capitu": "escobar", "escobar": "capitu",
    "rubiao": "virgilia", "virgilia": "rubiao", "florenca": "bacamarte",
}
