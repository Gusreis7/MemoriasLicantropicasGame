"""Identity-bound queries of the game table. Models never receive Redis credentials."""

from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from src.contracts.table import TableStatement
from src.textutils import normalize, word_tokens, has_any_phrase


@dataclass(frozen=True)
class PersonaTableAgent:
    """The server fixes actor and recipient; query arguments cannot change either."""

    knowledge: object
    game_id: object
    npc_id: str
    recipient_id: str = "player"

    @property
    def tools(self):
        return (
            {"name": "consultar_fofocas_compartilhaveis", "arguments": ("assunto",)},
            {"name": "consultar_relacao", "arguments": ("pessoa",)},
            {"name": "consultar_confidencias_autorizadas", "arguments": ("assunto",)},
        )

    async def shared_knowledge(self):
        return await self.knowledge.shared_entries(self.game_id, self.npc_id, self.recipient_id)

    async def relationships(self):
        context = await self.knowledge.context(self.game_id, self.npc_id, self.recipient_id)
        return tuple(context["vinculos_conhecidos"])

    async def query(self, question, now, *, excluded_statement_ids=()):
        text = normalize(question)
        tokens = set(word_tokens(text))
        profiles = await self.knowledge._characters.list()
        names = {profile.id: profile.name for profile in profiles}
        entries = await self.shared_knowledge()
        own_topics = tuple(entry for entry in entries if entry.origin == "authored")
        targets = {identifier for identifier, name in names.items()
                   if identifier != self.npc_id and normalize(name.replace("Dr. ", "").split()[0]) in tokens}

        def statement(kind, body, *, subject=None, root=None, sources=(), day=0):
            root = root or uuid5(NAMESPACE_URL, f"{self.game_id}:{self.npc_id}:{kind}:{subject}:{body}")
            # A correction can share its rumor root while citing a new source
            # version. Keep that provenance root, but do not silence the update.
            version = ':' + ':'.join(sorted(str(source) for source in sources)) if sources else ''
            return TableStatement(
                id=uuid5(NAMESPACE_URL, f"{self.game_id}:disclosure:{self.npc_id}:{self.recipient_id}:{root}:{kind}{version}"),
                kind=kind, speaker_id=self.npc_id, recipient_id=self.recipient_id,
                subject_id=subject, day=max(0, day or 0), source_ids=sources,
                root_id=root, text=body, created_at=now,
            )

        secret_request = bool(tokens & {"segredo", "segredos", "intimidade", "confidencia", "confidencias", "separar", "separacao", "apaixonado", "apaixonada", "amor", "ama"})
        if secret_request:
            private = tuple(entry for entry in own_topics if entry.visibility == "private")
            if private:
                return tuple(statement("secret", entry.proposition, root=entry.root_id,
                                       sources=(entry.id,), subject=self.npc_id, day=entry.day)
                             for entry in private[:2])
            return (statement("public_fact", "Prefiro preservar minha intimidade. Posso conversar sobre o que é público."),)

        if has_any_phrase(text, ("acredita em lobisomem", "acredita em lobisomens")):
            belief = ("Procuro explicações verificáveis para os acontecimentos; não tomo uma crença por prova."
                      if self.npc_id == "bacamarte" else "Tenho minhas dúvidas sobre a fera; prefiro ouvir o que as testemunhas realmente viram.")
            return (statement("public_fact", belief),)

        suspects = bool(tokens & {"suspeita", "suspeito", "suspeitos", "desconfia", "culpado", "culpada", "inimigo", "inimigos", "acusa", "acusaria", "lobisomem"})
        relation_question = has_any_phrase(text, ("acha de", "pensa de", "sente por", "relacao com", "gosta de", "odeia"))
        gossip_question = bool(tokens & {"fofoca", "fofocas", "rumor", "rumores", "ouviu", "conte", "contar", "sabe", "amizade", "casamento", "seminario", "tratamento", "medicacao", "pai"})
        if suspects or relation_question:
            relations = await self.relationships()
            candidates = [relation for relation in relations
                          if relation["target_id"] not in (self.npc_id, "player", "bras_cubas")
                          and (not targets or relation["target_id"] in targets)]
            candidates.sort(key=lambda value: (max(value["resentment"], value["suspicion"], -value["trust"], -value["affinity"]), value["target_id"]), reverse=True)
            hostile = [relation for relation in candidates if max(relation["resentment"], relation["suspicion"], -relation["trust"], -relation["affinity"]) >= 25]
            if hostile:
                chosen = hostile[0]
                target = chosen["target_id"]
                label = chosen.get("sentiment_label", "desconfiança")
                # The source is a personal interpretation, never a fabricated observation.
                body = f"Desconfio de {names[target]}. Minha impressão vem de {label}; não é prova de crime. Floriano pode investigar essa pessoa."
                source = uuid5(NAMESPACE_URL, f"{self.game_id}:relationship:{self.npc_id}:{target}")
                return (statement("suspicion", body, subject=target,
                                  root=uuid5(NAMESPACE_URL, f"{self.game_id}:relational-suspicion:{self.npc_id}:{target}"), sources=(source,)),)
            if relation_question and targets:
                target = sorted(targets)[0]
                related = [entry for entry in own_topics if target in entry.subject_ids and entry.visibility != "private"]
                if related:
                    entry = related[0]
                    return (statement("gossip", entry.proposition, subject=target, root=entry.root_id, sources=(entry.id,), day=entry.day),)
                return (statement("public_fact", f"Não tenho nada concreto a acrescentar sobre {names[target]}.", subject=target),)
            if suspects:
                return (statement("public_fact", "Não tenho uma suspeita pessoal que possa sustentar. Podemos comparar o que cada pessoa declarou."),)

        if gossip_question:
            public = [entry for entry in entries if entry.visibility != "private" and (not targets or targets & set(entry.subject_ids))]
            keywords = tokens - {"o", "a", "de", "que", "voce", "sabe", "sobre", "me", "conte", "fofoca", "fofocas"}
            public.sort(key=lambda entry: (len(keywords & set(word_tokens(normalize(entry.proposition)))), entry.origin == "authored", str(entry.id)), reverse=True)
            if public:
                candidates = tuple(statement("gossip", entry.proposition, root=entry.root_id,
                                       sources=(entry.id,), subject=sorted(targets)[0] if targets else None, day=entry.day)
                                   for entry in public)
                fresh = tuple(item for item in candidates if item.id not in excluded_statement_ids)
                # Return known candidates when exhausted so the caller can distinguish
                # exhaustion from a topic for which this persona never knew a fact.
                return fresh[:2] or candidates[:2]
            return (statement("public_fact", "Não conheço um relato sobre isso que possa compartilhar."),)
        return ()


async def prepare_knowledge_turn(knowledge_service, game_id, npc_id, recipient_id, question, now, *, excluded_statement_ids=()):
    return await PersonaTableAgent(knowledge_service, game_id, npc_id, recipient_id).query(question, now, excluded_statement_ids=excluded_statement_ids)
