"""Papel editorial do mestre: compor somente fatos já resolvidos pelo motor."""

from src.contracts.investigation import JournalEdition
from src.modules.characters.catalog import CHARACTERS
from src.modules.characters.language import participle
from src.contracts.generation import EditorialProposal
from src.infrastructure.llm.structured import generate_structured
from src.prompts.editorial import EDITORIAL_INSTRUCTIONS


def word(identifier, masculine, feminine):
    return participle(
        next((p for p in CHARACTERS if p.id == identifier), None), masculine, feminine
    )


def final_edition(state, names, *, method=None, werewolf_id=None, detention="none"):
    method = method or state.ending_method
    person = names.get(werewolf_id, werewolf_id or "a pessoa investigada")
    if state.status == "won":
        headline = "Floriano vence: a cidade está livre do lobisomem"
        fact = {
            "detention": f"{person} se transformou na cela, diante da polícia. {person} foi {word(werewolf_id, 'expulso', 'expulsa')} da cidade.",
            "confession": f"{person} admitiu sua participação nos ataques e se entregou ao delegado.",
            "assembly": f"A assembleia confirmou a identidade do lobisomem. {person} foi {word(werewolf_id, 'expulso', 'expulsa')} da cidade.",
        }.get(method, "A investigação confirmou a identidade do lobisomem.")
        body = f"{fact} Floriano encerra o caso. O Clarim do Rio celebra o alívio dos moradores."
    elif method == "player_expelled":
        headline = "Floriano é expulso: a investigação termina sem solução"
        body = "A maioria dos moradores expulsou Floriano. O caso termina em derrota do detetive; o perigo permanece."
    else:
        from src.modules.investigation.rules import (
            werewolf_cast_victims,
        )

        victims = werewolf_cast_victims(state.crimes, set(names), werewolf_id)
        headline = "Floriano não chegou a tempo: a besta-fera venceu"
        losses = (
            f"Quatro dos sete moradores foram mortos pelo lobisomem. "
            if len(victims) >= 4
            else "Não restam civis vivos e livres para continuar a investigação. "
        )
        body = (
            losses
            + "Floriano não conseguiu deter a fera a tempo. A investigação termina em derrota; "
            "a besta-fera ganhou, e os sobreviventes ficam à mercê da noite. "
            "O Clarim do Rio publica esta edição em luto pelas vítimas e pela esperança perdida da cidade."
        )
    last = (
        state.crimes[-1]
        if state.status == "lost"
        and state.crimes
        and state.crimes[-1].day == state.day - 1
        else None
    )
    return JournalEdition(
        victim_id=last.victim_id if last else None,
        location_id=last.location_id if last else None,
        day=state.day,
        illustration="victory" if state.status == "won" else "crime_street",
        headline=headline,
        body=body,
        suspicious_death_count=len(state.crimes),
        detention_outcome=detention,
    )


def morning_edition(day, crimes, new_crimes, names, detention="none", detainee_id=None):
    count = len(crimes)
    if new_crimes:
        people = " e ".join(names.get(c.victim_id, c.victim_id) for c in new_crimes)
        headline = f"Já são {count} mortes suspeitas: a cidade exige respostas"
        body = f"{people}: a manhã revelou {len(new_crimes)} nova" + (
            " morte suspeita." if len(new_crimes) == 1 else "s mortes suspeitas."
        )
        body += " A autoria de cada crime ainda é investigada. Floriano compara as cenas, os vestígios e as versões dos moradores."
        primary = new_crimes[0]
        location = primary.location_id
        victim = primary.victim_id
    else:
        headline = f"Sem nova vítima; {count} mortes suspeitas seguem sob investigação"
        body = "A cidade amanhece sem nova morte. Uma noite de silêncio não encerra o caso; Floriano prossegue com a investigação."
        victim = None
        location = None
    if detainee_id and detention == "released":
        body += f" {names.get(detainee_id, detainee_id)} não se transformou e foi {word(detainee_id, 'solto', 'solta')} pela manhã."
    illustration = (
        "quiet"
        if not location
        else "crime_docks"
        if location == "cais_lanternas"
        else "crime_garden"
        if location in {"casa_verde", "cabana_capitu"}
        else "crime_street"
    )
    return JournalEdition(
        day=day,
        headline=headline,
        body=body,
        illustration=illustration,
        victim_id=victim,
        location_id=location,
        suspicious_death_count=count,
        detention_outcome=detention,
    )


SIGNATURE = "Leonidas Soares, diretor do Clarim do Rio"


def victory_facts(state, names, werewolf_id):
    person = names.get(werewolf_id, werewolf_id)
    victims = [
        names.get(c.victim_id, c.victim_id)
        for c in state.crimes
        if c.killer_id == werewolf_id and c.cause == "werewolf"
    ]
    deaths = (
        f"As mortes atribuídas à fera são: {', '.join(victims)} ({len(victims)})."
        if victims
        else "Não há mortes atribuídas à fera nos registros desta investigação."
    )
    action = {
        "detention": "Floriano levou à detenção da pessoa investigada; a transformação na cela confirmou sua identidade e a polícia a expulsou da cidade.",
        "confession": "A investigação de Floriano levou à confissão e à entrega ao delegado.",
        "assembly": "Floriano sustentou a acusação perante a assembleia, que confirmou a identidade da fera e decidiu por sua expulsão.",
    }.get(
        state.ending_method,
        "Floriano concluiu a investigação e confirmou a identidade da fera.",
    )
    return f"{person} era o lobisomem. {action} {deaths}"


async def victory_article(state, names, werewolf_id, llm=None):
    """Fatos canônicos e assinatura fixa; o mestre escreve a opinião breve."""
    import json
    import logging
    from src.contracts.model import ChatMessage
    from src.infrastructure.usage import usage_scope
    from src.modules.agents.guard import DialogueGuard

    edition = state.journal[-1]
    facts = victory_facts(state, names, werewolf_id)
    opinion = (
        "A cidade deve a Floriano o alívio de ver encerrada esta ameaça. "
        "Celebramos sua persistência, sem esquecer o luto que nenhuma vitória apaga."
    )
    if llm is not None:
        payload = {
            "fatos_confirmados": facts,
            "dia": state.day,
            "vestigios_recolhidos": sum(
                e.collected for c in state.crimes for e in c.evidence
            ),
            "depoimentos_registrados": len(state.testimonies),
        }
        with usage_scope(state.game_id, "session_master"):
            result = await generate_structured(
                llm,
                (
                    ChatMessage(role="system", content=EDITORIAL_INSTRUCTIONS),
                    ChatMessage(
                        role="user", content=json.dumps(payload, ensure_ascii=False)
                    ),
                ),
                EditorialProposal,
                max_attempts=1,
            )
        if result.ok and DialogueGuard().inspect_output(result.value.opinion).allowed:
            opinion = result.value.opinion
        else:
            logging.getLogger(__name__).warning(
                "victory_editorial_fallback code=%s",
                result.error_code or "unsafe_output",
            )

    return edition.model_copy(update={"body": f"{facts}\n\n{opinion}\n\n{SIGNATURE}"})
