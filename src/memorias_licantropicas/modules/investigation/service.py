"""Casos de uso de pistas: autorização física e transições sob o relógio do motor."""

from math import ceil
from uuid import UUID, NAMESPACE_URL, uuid5

from memorias_licantropicas.contracts.errors import AccessDeniedError, ConflictError, NotFoundError
from memorias_licantropicas.contracts.investigation import CaseEvent, CaseTransition
from memorias_licantropicas.modules.investigation.catalog import INVENTORIES, ITEMS_BY_ID, OBSERVED_PEOPLE
from memorias_licantropicas.modules.investigation.rules import evaluate_accusation, find_evidence, make_testimony
from memorias_licantropicas.modules.investigation.schema import (
    AchievementPublic, AccusationPublic, CasePublic, CrimePublic, EndingPublic, EvidencePublic, JournalPublic, TestimonyPublic,
    ActivityClaimPublic, InterrogationPublic, ConfrontationPublic,
)


from memorias_licantropicas.modules.investigation.assembly_service import AssemblyServiceMixin


class InvestigationService(AssemblyServiceMixin):
    def __init__(self, turns, characters, memory=None):
        self._turns = turns
        self._characters = characters
        self._memory = memory

    async def _names(self):
        return {"bras_cubas": "Brás Cubas", **{profile.id: profile.name for profile in await self._characters.list()}}

    async def public(self, state) -> CasePublic:
        names, now = await self._names(), self._turns.now()
        ending = None
        if state.status != "active":
            if not state.crimes:
                raise ConflictError("O desfecho desta investigação está incompleto.")
            ending = EndingPublic(result=state.status, werewolf_id=state.crimes[0].killer_id,
                method=state.ending_method or ("detention" if state.status == "won" else "survival"),
                message=("A cidade expulsou Floriano. A investigação terminou em derrota." if state.ending_method == "player_expelled" else
                         "A assembleia expulsou o lobisomem. A cidade venceu a investigação." if state.ending_method == "assembly" else
                         "Confrontado com as provas, o lobisomem confessou e entregou-se ao delegado. "
                         "Floriano venceu a investigação." if state.ending_method == "confession" else
                         "A transformação na cela confirmou a acusação. A cidade expulsa o lobisomem. "
                         "Floriano venceu a investigação." if state.status == "won" else
                         "Nenhum civil sobreviveu às noites. A investigação de Floriano terminou em derrota."))
        return CasePublic(
            achievements=tuple(AchievementPublic(**a.model_dump()) for a in state.achievements),
            game_id=state.game_id, revision=state.revision, day=state.day, phase=state.phase, status=state.status,
            server_time=now, phase_ends_at=state.phase_ends_at,
            seconds_remaining=max(0, ceil((state.phase_ends_at - now).total_seconds())) if state.status == "active" else 0,
            journal=tuple(JournalPublic(illustration=entry.illustration, day=entry.day, headline=entry.headline, body=entry.body,
                victim_id=entry.victim_id, victim_name=names.get(entry.victim_id) if entry.victim_id else None,
                suspicious_death_count=entry.suspicious_death_count,
                location_id=entry.location_id, detention_outcome=entry.detention_outcome) for entry in state.journal),
            crimes=tuple(CrimePublic(id=crime.id, day=crime.day, victim_id=crime.victim_id,
                victim_name=names.get(crime.victim_id, crime.victim_id), location_id=crime.location_id, x=crime.x,
                remaining_clues=sum(not evidence.collected for evidence in crime.evidence)) for crime in state.crimes),
            inventory=tuple(EvidencePublic(id=evidence.id, crime_id=crime.id, item_id=evidence.item_id,
                name=ITEMS_BY_ID[evidence.item_id].name, kind=ITEMS_BY_ID[evidence.item_id].kind,
                description=evidence.description, examined=evidence.examined, inspection_text=evidence.inspection_text) for crime in state.crimes for evidence in crime.evidence if evidence.collected),
            testimonies=tuple(TestimonyPublic(id=record.id, day=record.day, evidence_id=record.evidence_id,
                witness_id=record.witness_id, witness_name=names.get(record.witness_id, record.witness_id),
                recognition=record.recognition, claimed_owner_id=record.claimed_owner_id, text=record.text)
                for record in state.testimonies),
            accusations=tuple(AccusationPublic(id=record.id, day=record.day, suspect_id=record.suspect_id,
                suspect_name=names.get(record.suspect_id, record.suspect_id), evidence_ids=record.evidence_ids,
                testimony_ids=record.testimony_ids, accepted=record.accepted, reason=record.reason)
                for record in state.accusations),
            detained_npc_id=state.detained_npc_id, ending=ending,
            assembly_session=({key:value for key,value in state.assembly_session.model_dump(mode="json").items()
                if key not in {"relationships", "argument_strength", "remaining_day_seconds"}} if state.assembly_session else None),
            assembly=state.assembly.model_dump(mode="json") if state.assembly else None,
            expelled_npc_ids=state.expelled_npc_ids,
            interrogations=tuple(InterrogationPublic(id=record.id, npc_id=record.npc_id,
                npc_name=names.get(record.npc_id, record.npc_id), day=record.day, period=record.period,
                location_id=record.location_id, companion_ids=record.companion_ids,
                activity=record.activity, text=record.text,
                observations=tuple(ActivityClaimPublic(**claim.model_dump()) for claim in record.observations))
                for record in state.interrogations),
            confrontations=tuple(ConfrontationPublic(id=record.id, npc_id=record.npc_id, day=record.day,
                evidence_ids=record.evidence_ids, testimony_ids=record.testimony_ids,
                interrogation_ids=record.interrogation_ids, confessed=record.confessed, text=record.text)
                for record in state.confrontations),
        )

    @staticmethod
    def _require_witness(state, game, world, npc_id):
        member = next((npc for npc in game.characters if npc.character_id == npc_id), None)
        if member is None:
            raise NotFoundError("Morador não encontrado nesta partida.")
        placement = next((npc for npc in world.npcs if npc.npc_id == npc_id), None)
        if (not member.alive or state.detained_npc_id == npc_id or placement is None
                or placement.activity in {"travelling", "talking"} or placement.location_id != world.player.location_id
                or abs(placement.x - world.player.x) > 64):
            raise AccessDeniedError("Aproxime-se de um morador vivo, livre e disponível para interrogá-lo.")

    async def interrogate(self, game_id: UUID, npc_id: str, day: int, period: str = "night") -> CasePublic:
        from memorias_licantropicas.modules.investigation.interrogation import make_interrogation, record_activities
        names = await self._names()
        def transition(state, game, world):
            self._require_witness(state, game, world, npc_id)
            if period not in {"day", "night"} or day < 0 or day > state.day or (period == "night" and day >= state.day):
                raise ConflictError("Escolha um período passado ou o dia atual para interrogar.")
            existing = next((record for record in state.interrogations
                             if record.npc_id == npc_id and record.day == day and record.period == period), None)
            if existing is not None:
                return CaseTransition(state=state)
            if period == "day" and day == state.day and not any(
                    record.day == day and record.period == period for record in state.activity_records):
                state = state.model_copy(update={"activity_records": (*state.activity_records,
                    *record_activities(game, world, day, period, self._turns.now(),
                        excluded_ids=(state.detained_npc_id,) if state.detained_npc_id else ()))})
            record = make_interrogation(state, game, npc_id, day, period, names, self._turns.now())
            return CaseTransition(state=state.model_copy(update={"interrogations": (*state.interrogations, record)}),
                events=(CaseEvent(type="character.interrogated", data={"interrogation_id": str(record.id),
                    "npc_id": npc_id, "day": day, "period": period}),))
        return await self.public(await self._turns.act(game_id, transition))

    async def confront(self, game_id: UUID, npc_id: str, evidence_ids=(), testimony_ids=(),
                       interrogation_ids=()) -> CasePublic:
        from memorias_licantropicas.modules.investigation.interrogation import make_confrontation
        def transition(state, game, world):
            self._require_witness(state, game, world, npc_id)
            record = make_confrontation(state, game, npc_id, tuple(dict.fromkeys(evidence_ids)),
                tuple(dict.fromkeys(testimony_ids)), tuple(dict.fromkeys(interrogation_ids)), self._turns.now())
            changes = {"confrontations": (*state.confrontations, record)}
            events = [CaseEvent(type="character.confronted", data={"confrontation_id": str(record.id),
                "npc_id": npc_id, "day": state.day, "confessed": record.confessed})]
            if record.confessed:
                changes.update(status="won", phase="finished", ending_method="confession", detained_npc_id=npc_id)
                events.extend((CaseEvent(type="werewolf.confessed", data={"character_id": npc_id, "day": state.day}),
                               CaseEvent(type="game.won", data={"werewolf_id": npc_id, "day": state.day,
                                                                "method": "confession"})))
            return CaseTransition(state=state.model_copy(update=changes), events=tuple(events))
        return await self.public(await self._turns.act(game_id, transition))

    async def assemble(self, game_id, suspect_id, evidence_ids=(), testimony_ids=()):
        from memorias_licantropicas.modules.investigation.assembly import convene
        def transition(state, game, world):
            record = convene(state, game, suspect_id, tuple(dict.fromkeys(evidence_ids)),
                             tuple(dict.fromkeys(testimony_ids)), self._turns.now())
            changes = {"assembly": record}
            if record.expelled and record.suspect_id != "player":
                changes["expelled_npc_ids"] = (*state.expelled_npc_ids, record.suspect_id)
            if record.outcome == "werewolf":
                changes.update(status="won", phase="finished", ending_method="assembly")
            elif record.outcome == "player_expelled":
                changes.update(status="lost", phase="finished", ending_method="player_expelled")
            return CaseTransition(state=state.model_copy(update=changes), events=(CaseEvent(
                type="assembly.resolved", data=record.model_dump(mode="json")),))
        return await self.public(await self._turns.act(game_id, transition))

    async def get(self, game_id: UUID) -> CasePublic:
        return await self.public(await self._turns.sync(game_id))

    async def search(self, game_id: UUID, crime_id: UUID) -> CasePublic:
        def transition(state, game, world):
            crime = next((crime for crime in state.crimes if crime.id == crime_id), None)
            if crime is None:
                raise NotFoundError("Cena do crime não encontrada nesta partida.")
            if world.player.location_id != crime.location_id or abs(world.player.x - crime.x) > 90:
                raise AccessDeniedError("Aproxime-se da cena do crime para procurar vestígios.")
            evidence = next((item for item in crime.evidence if not item.collected), None)
            if evidence is None:
                return CaseTransition(state=state)
            updated_crime = crime.model_copy(update={"evidence": tuple(
                item.model_copy(update={"collected": True}) if item.id == evidence.id else item for item in crime.evidence)})
            updated = state.model_copy(update={"crimes": tuple(updated_crime if item.id == crime.id else item for item in state.crimes)})
            return CaseTransition(state=updated, events=(CaseEvent(type="evidence.collected", data={
                "crime_id": str(crime.id), "evidence_id": str(evidence.id), "item_id": evidence.item_id,
                "location_id": crime.location_id, "day": state.day}),))
        return await self.public(await self._turns.act(game_id, transition))

    async def inspect(self, game_id: UUID, evidence_id: UUID) -> CasePublic:
        from memorias_licantropicas.modules.investigation.rules import inspect_evidence
        from memorias_licantropicas.modules.achievements.rules import award
        def transition(state, game, world):
            result = inspect_evidence(state, evidence_id, self._turns.now())
            evidence = find_evidence(result.state, evidence_id)
            updated = result.state
            if ITEMS_BY_ID[evidence.item_id].kind == "unique" and evidence.examined:
                updated = award(updated, "personal_trace", self._turns.now())
            events = result.events
            if len(updated.achievements) > len(state.achievements):
                events += (CaseEvent(type="achievement.unlocked", data={"achievement_id": "personal_trace"}),)
            return CaseTransition(state=updated, events=events)
        return await self.public(await self._turns.act(game_id, transition))

    async def present(self, game_id: UUID, evidence_id: UUID, npc_id: str) -> CasePublic:
        names = await self._names()
        def transition(state, game, world):
            evidence = find_evidence(state, evidence_id)
            member = next((npc for npc in game.characters if npc.character_id == npc_id), None)
            if member is None or npc_id not in INVENTORIES:
                raise NotFoundError("Testemunha não encontrada nesta partida.")
            placement = next((npc for npc in world.npcs if npc.npc_id == npc_id), None)
            if (not member.alive or state.detained_npc_id == npc_id or placement is None
                    or placement.location_id != world.player.location_id or abs(placement.x - world.player.x) > 64):
                raise AccessDeniedError("Aproxime-se de uma testemunha viva e livre para apresentar o objeto.")
            existing = next((record for record in state.testimonies
                             if record.witness_id == npc_id
                             and find_evidence(state, record.evidence_id).item_id == evidence.item_id), None)
            focused = {**state.active_evidence_by_npc, npc_id: evidence.id}
            if existing is not None:
                return CaseTransition(state=state.model_copy(update={"active_evidence_by_npc": focused}))
            record = make_testimony(state, game, evidence, npc_id, names, self._turns.now())
            return CaseTransition(state=state.model_copy(update={"testimonies": (*state.testimonies, record),
                                                 "active_evidence_by_npc": focused}),
                events=(CaseEvent(type="evidence.presented", data={"evidence_id": str(evidence.id),
                    "testimony_id": str(record.id), "witness_id": npc_id, "day": state.day}),))
        state = await self._turns.act(game_id, transition)
        if self._memory is not None:
            conversation = await self._memory.get_player_conversation(game_id, npc_id)
            evidence = find_evidence(state, evidence_id)
            testimony = next(record for record in state.testimonies if record.witness_id == npc_id
                and find_evidence(state, record.evidence_id).item_id == evidence.item_id)
            if conversation is not None:
                from memorias_licantropicas.contracts.model import ConversationMessage
                shown = ITEMS_BY_ID[evidence.item_id]
                # Um retry repete o mesmo par, com os mesmos IDs, data e objeto original.
                original = find_evidence(state, testimony.evidence_id)
                action = ConversationMessage(id=uuid5(NAMESPACE_URL, f'present:{testimony.id}:player'),
                    sender_id='player', content=f'Mostro-lhe {shown.name}: {original.description}', created_at=testimony.created_at)
                response = ConversationMessage(id=uuid5(NAMESPACE_URL, f'present:{testimony.id}:npc'),
                    sender_id=npc_id, content=testimony.text, created_at=testimony.created_at)
                await self._memory.append_messages(game_id, conversation.id, (action, response))
        return await self.public(state)

    async def accuse(self, game_id: UUID, suspect_id: str, evidence_ids, testimony_ids) -> CasePublic:
        def transition(state, game, world):
            if any(record.day == state.day for record in state.accusations):
                raise ConflictError("O delegado recebe uma tentativa de acusação por dia.")
            if state.detained_npc_id is not None:
                raise ConflictError("Já existe uma pessoa sob custódia para esta noite.")
            member = next((npc for npc in game.characters if npc.character_id == suspect_id), None)
            if member is None:
                raise NotFoundError("Acusado não encontrado nesta partida.")
            if not member.alive or suspect_id in state.expelled_npc_ids:
                raise AccessDeniedError("Não é possível deter uma pessoa morta.")
            record = evaluate_accusation(state, suspect_id, tuple(dict.fromkeys(evidence_ids)),
                                         tuple(dict.fromkeys(testimony_ids)), self._turns.now())
            updated = state.model_copy(update={"accusations": (*state.accusations, record),
                                               "detained_npc_id": suspect_id if record.accepted else None})
            events = [CaseEvent(type="accusation.reviewed", data={"accusation_id": str(record.id),
                "suspect_id": suspect_id, "accepted": record.accepted, "day": state.day})]
            if record.accepted:
                events.append(CaseEvent(type="character.detained", data={"character_id": suspect_id, "day": state.day}))
            return CaseTransition(state=updated, events=tuple(events))
        return await self.public(await self._turns.act(game_id, transition, start_night_on_detention=True))

    async def npc_context_locked(self, game_id: UUID, npc_id: str) -> dict:
        """Chamador mantém player_gate; não oferece informação privada de outros papéis."""
        state = await self._turns.require_day_locked(game_id)
        if npc_id not in INVENTORIES:
            raise NotFoundError("Ficha de objetos não encontrada.")
        from memorias_licantropicas.modules.investigation.interrogation import COOPERATION
        from memorias_licantropicas.modules.investigation.interrogation import make_interrogation
        game = await self._turns._games.get(game_id) if hasattr(self._turns, '_games') else getattr(self._turns, 'game', None)
        names = await self._names()
        memories = []
        if game is not None:
            periods = sorted({(r.day, r.period) for r in state.activity_records if r.npc_id == npc_id})
            for day, period in periods[-8:]:
                declared = make_interrogation(state, game, npc_id, day, period, names, self._turns.now())
                memories.append({'dia': day, 'periodo': period, 'local_id': declared.location_id,
                    'companhias': declared.companion_ids, 'atividade': declared.activity,
                    'lembranca': declared.text})
        last = None
        last_id = state.active_evidence_by_npc.get(npc_id)
        if last_id:
            focused = find_evidence(state, last_id)
            testimony = next((t for t in reversed(state.testimonies) if t.witness_id == npc_id
                and find_evidence(state, t.evidence_id).item_id == focused.item_id), None)
            last = {"evidence_id": str(focused.id), "item_id": focused.item_id,
                    "nome": ITEMS_BY_ID[focused.item_id].name, "descricao": focused.description,
                    "fala_registrada": testimony.text if testimony else None}
        from memorias_licantropicas.modules.investigation.night_story import plot_context
        return {
            "seu_conflito_privado": plot_context(state,npc_id,names),
            "ultimo_objeto_apresentado": last,
            "suas_atividades": memories,
            "cooperacao_com_investigacao": COOPERATION.get(npc_id, "Ajude a esclarecer o crime com o que sabe."),
            "dia": state.day,
            "fase": state.phase,
            "proprios_apetrechos": [ITEMS_BY_ID[item_id].model_dump() for item_id in INVENTORIES[npc_id]],
            "posses_observadas": [{"personagem_id": person,
                "observacao": "Já viu esta pessoa usar objetos destes tipos; isso não identifica a procedência de um vestígio comum.",
                "objetos": [ITEMS_BY_ID[item_id].model_dump() for item_id in INVENTORIES[person]]}
                for person in OBSERVED_PEOPLE[npc_id]],
            "jornal_publico": [{"dia": edition.day, "manchete": edition.headline, "noticia": edition.body}
                               for edition in state.journal],
            "seus_depoimentos_registrados": [{"evidence_id": str(record.evidence_id), "fala": record.text,
                "item_id": find_evidence(state, record.evidence_id).item_id,
                "nome": ITEMS_BY_ID[find_evidence(state, record.evidence_id).item_id].name,
                                               "reconhecimento": record.recognition}
                                              for record in state.testimonies if record.witness_id == npc_id],
            "suas_versoes_de_interrogatorio": [{"dia": record.day, "periodo": record.period,
                "local_id": record.location_id, "companhias": record.companion_ids, "fala": record.text,
                "observacoes": [claim.model_dump() for claim in record.observations]}
                for record in state.interrogations if record.npc_id == npc_id],
            "seus_confrontos": [{"fala": record.text, "dia": record.day}
                                for record in state.confrontations if record.npc_id == npc_id],
            "regra_de_dialogo": "Reconhecimento de posse observada não confirma quem deixou o objeto. "
                                "Falas não criam pistas ou alteram depoimentos registrados pelo motor.",
        }
