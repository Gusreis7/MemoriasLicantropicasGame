"""Cinco minutos de dia, noite não jogável e acontecimentos autoritativos."""

import json

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from src.contracts.errors import ConflictError, NotFoundError, StorageUnavailableError
from src.contracts.investigation import (
    CaseEvent, CaseTransition, InvestigationState, JournalEdition,
)
from src.contracts.model import GameState
from src.modules.characters.language import participle
from src.modules.characters.catalog import supports_content_version
from src.modules.turns.repository import RedisTurnRepository
from src.modules.world.model import WorldState


class TurnService:
    def __init__(self, redis, prefix, games, characters, world_repository, player_gate,
                 clock: Callable[[], datetime] | None = None,
                 day_seconds: float = 300, night_seconds: float = 8, victory_editor=None):
        if day_seconds <= 0 or night_seconds <= 0:
            raise ValueError("As durações das fases devem ser positivas.")
        self._victory_editor = victory_editor
        self._repository = RedisTurnRepository(redis, prefix)
        self._games = games
        self._characters = characters
        self._world = world_repository
        self._gate = player_gate
        self._clock = clock or (lambda: datetime.now(UTC))
        self._day_seconds = day_seconds
        self._night_seconds = night_seconds

    async def _edit_victory(self, previous, state, game):
        if previous.status != 'won' and state.status == 'won' and self._victory_editor:
            return await self._victory_editor(state, game)
        return state

    def now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("O relógio do ciclo precisa de timezone.")
        return now.astimezone(UTC)

    def _validate_snapshot(self, game, world, state) -> None:
        if game is None:
            raise NotFoundError("Partida não encontrada.")
        if not supports_content_version(game.content_version, self._characters.content_version):
            raise ConflictError("A partida usa uma versão anterior de personagens.")
        if world is None:
            raise ConflictError("Esta partida não possui mundo visual.")
        if state is None:
            raise StorageUnavailableError("Ciclo da partida ausente; crie uma nova partida.")
        if state.status != game.status:
            raise StorageUnavailableError("Estado da partida e do ciclo inconsistentes.")

    async def _load(self, game_id: UUID) -> tuple[GameState, WorldState, InvestigationState | None]:
        game = await self._games.get(game_id)
        world = await self._world.get(game_id)
        state = await self._repository.get(game_id)
        self._validate_snapshot(game, world, state)
        return game, world, state

    async def sync(self, game_id: UUID) -> InvestigationState:
        game, world, state = await self._repository.read_snapshot(game_id)
        self._validate_snapshot(game, world, state)
        assembly_expired = bool(state and state.assembly_session and state.assembly_session.phase == "debate"
            and self.now() >= state.assembly_session.deadline)
        if state is not None and not assembly_expired and (state.status != "active" or state.phase == "finished"
                                  or self.now() < state.phase_ends_at):
            return state
        # Só uma fase vencida exige reserva. Leituras de um
        # dia em curso continuam disponíveis durante a inferência de uma fala.
        async with self._gate.hold(game_id):
            return await self._sync_locked(game_id)

    async def _sync_locked(self, game_id: UUID) -> InvestigationState:
        game, world, state = await self._load(game_id)
        now = self.now()
        if (state.assembly_session and state.assembly_session.phase == "debate"
                and now >= state.assembly_session.deadline):
            from src.modules.investigation.assembly import resolve_transition, apply_assembly_effects
            result = resolve_transition(state, game, now)
            updated = result.state.model_copy(update={"revision": state.revision + 1})
            updated, next_game, next_world = apply_assembly_effects(updated, game, world, now)
            updated = await self._edit_victory(state, updated, next_game)
            await self._repository.commit(previous=state,state=updated,previous_game=game,game=next_game,
                previous_world=world,world=next_world,events=result.events,occurred_at=now)
            state,game,world=updated,next_game,next_world
        # Duas causas de morte; cada noite poupada obriga ataque na seguinte.
        for _ in range(4 * len(game.characters) + 8):
            if state.status != "active" or state.phase == "finished" or now < state.phase_ends_at:
                return state
            boundary = state.phase_ends_at
            if state.phase == "day":
                from src.modules.investigation.interrogation import record_activities
                records = state.activity_records
                if not any(record.day == state.day and record.period == "day" for record in records):
                    records += record_activities(game, world, state.day, "day", boundary,
                        excluded_ids=(state.detained_npc_id,) if state.detained_npc_id else ())
                updated = state.model_copy(update={
                    "revision": state.revision + 1, "phase": "night",
                    "phase_ends_at": boundary + timedelta(seconds=self._night_seconds),
                    "activity_records": records,
                })
                updated_world = world.model_copy(update={"revision": world.revision + 1,
                    "player": world.player.model_copy(update={"direction": "idle", "last_updated_at": boundary})})
                next_game = game
                events = (CaseEvent(type="night.started", data={"day": state.day}),)
            else:
                updated, next_game, updated_world, events = await self._resolve_night(state, game, world, boundary)
            updated = await self._edit_victory(state, updated, next_game)
            await self._repository.commit(
                previous=state, state=updated, previous_game=game, game=next_game,
                previous_world=world, world=updated_world, events=events, occurred_at=boundary,
            )
            state, game, world = updated, next_game, updated_world
        raise StorageUnavailableError("O ciclo ultrapassou o limite de recuperação.")

    async def skip_day(self, game_id: UUID, day: int) -> InvestigationState:
        """Resolve uma noite e abre a manhã agora, em uma única transação."""
        from src.modules.investigation.interrogation import record_activities

        async with self._gate.hold(game_id):
            state = await self.require_day_locked(game_id)
            if state.day != day:
                raise ConflictError("O dia já mudou; consulte a edição atual do jornal.")
            game, world, _ = await self._load(game_id)
            now = self.now()
            records = state.activity_records
            if not any(record.day == day and record.period == "day" for record in records):
                records += record_activities(game, world, day, "day", now,
                    excluded_ids=(state.detained_npc_id,) if state.detained_npc_id else ())
            night = state.model_copy(update={"phase": "night", "phase_ends_at": now,
                                             "activity_records": records})
            updated, next_game, next_world, events = await self._resolve_night(night, game, world, now)
            updated = await self._edit_victory(state, updated, next_game)
            await self._repository.commit(
                previous=state, state=updated, previous_game=game, game=next_game,
                previous_world=world, world=next_world, occurred_at=now,
                events=(CaseEvent(type="day.skipped", data={"day": day}),
                        CaseEvent(type="night.started", data={"day": day, "reason": "day_skipped"}),
                        *events),
            )
            return updated

    async def _resolve_night(self, state, game, world, boundary):
        from src.modules.investigation.rules import (
            choose_victim, make_crime, werewolf_cast_victims, WEREWOLF_DEFEAT_THRESHOLD,
        )
        from src.modules.investigation.night_story import resolve_story
        from src.modules.investigation.interrogation import record_activities
        from src.modules.session_master.editorial import morning_edition, final_edition

        wolf = next(member.character_id for member in game.characters if member.role == "werewolf")
        names = {profile.id: profile.name for profile in await self._characters.list()}
        day, events, fresh = state.day + 1, [], []
        records = state.activity_records
        table = state.table
        story = state.night_story
        detention = 'transformed' if state.detained_npc_id == wolf else 'released' if state.detained_npc_id else 'none'
        if detention == 'transformed':
            status = 'won'
            events.append(CaseEvent(type='werewolf.expelled',data={'character_id':wolf,'day':day}))
        else:
            previous_plot=story.plot if story else None
            story, attacks = resolve_story(state, game, choose_victim)
            for killer, victim_id, cause in attacks:
                victim=next((m for m in game.characters if m.character_id==victim_id),None)
                if victim is None or not victim.alive or victim.role!='civil' or victim_id==state.detained_npc_id:
                    raise StorageUnavailableError('Vítima inválida na resolução noturna.')
                placement=next((npc for npc in world.npcs if npc.npc_id==victim_id),None)
                location=placement.location_id if placement else 'praca_verde'
                crime=make_crime(game,state.day,victim_id,location,boundary,killer_id=killer,cause=cause)
                fresh.append(crime)
                game=game.model_copy(update={'characters':tuple(m.model_copy(update={'alive':False})
                     if m.character_id==victim_id else m for m in game.characters)})
                events.append(CaseEvent(type='character.killed',data={'victim_id':victim_id,'killer_id':killer,
                     'crime_id':str(crime.id),'location_id':location,'day':state.day,'cause':cause}))
            # Um único retrato do período noturno; os dois ataques conservam cenas próprias.
            records += record_activities(game,world,state.day,'night',boundary,source='night_resolution',
                crimes=tuple(fresh),excluded_ids=(state.detained_npc_id,) if state.detained_npc_id else ())
            from src.modules.table.rules import make_night_record, append_night
            table = append_night(table, make_night_record(game, world, state.day, boundary,
                crimes=tuple(fresh), excluded_ids=tuple(person for person in (*state.expelled_npc_ids, state.detained_npc_id) if person)))
            if story.plot and story.plot.status=='frustrated' and (not previous_plot or previous_plot.status!='frustrated'):
                events.append(CaseEvent(type='civil_plot.frustrated',data={'character_id':story.plot.planner_id,
                    'target_id':story.plot.target_id,'stress':story.plot.stress,'day':state.day}))
            if detention=='released':
                events.append(CaseEvent(type='suspect.released',data={'character_id':state.detained_npc_id,'day':day}))
            victims = werewolf_cast_victims((*state.crimes, *fresh),
                {m.character_id for m in game.characters}, wolf)
            defeated = len(victims) >= WEREWOLF_DEFEAT_THRESHOLD
            status='lost' if defeated or not any(m.role=='civil' and m.alive and m.character_id not in state.expelled_npc_ids for m in game.characters) else 'active'
        crimes=(*state.crimes,*fresh)
        method='detention' if status=='won' else 'survival' if status=='lost' else None
        updated=state.model_copy(update={'revision':state.revision+1,'day':day,
            'phase':'day' if status=='active' else 'finished','status':status,
            'phase_ends_at':boundary+timedelta(seconds=self._day_seconds) if status=='active' else boundary,
            'crimes':crimes,'detained_npc_id':None,'activity_records':records,'ending_method':method,'night_story':story,'table':table})
        edition=(final_edition(updated,names,werewolf_id=wolf,detention=detention) if status!='active' else
                 morning_edition(day,crimes,fresh,names,detention,state.detained_npc_id))
        updated=updated.model_copy(update={'journal':(*state.journal,edition)})
        game=game.model_copy(update={'status':status})
        living={m.character_id for m in game.characters if m.alive}
        world=world.model_copy(update={'revision':world.revision+1,
            'npcs':tuple(n for n in world.npcs if n.npc_id in living and not(status=='won' and n.npc_id==wolf)),
            'player':world.player.model_copy(update={'location_id':'praca_verde','x':160,
                    'facing':'right','direction':'idle','last_updated_at':boundary})})
        victims=[c.victim_id for c in fresh]
        events.extend((CaseEvent(type='night.resolved',data={'day':state.day,'victim_id':victims[0] if victims else None,
                       'victim_ids':victims,'detention_outcome':detention}),
            CaseEvent(type='journal.published',data={'day':day,'headline':edition.headline,
                       'victim_ids':victims,'detention_outcome':detention})))
        if status!='active':events.append(CaseEvent(type=f'game.{status}',data={'day':day,'werewolf_id':wolf}))
        return updated,game,world,tuple(events)

    async def require_day_locked(self, game_id: UUID, *, allow_assembly=False) -> InvestigationState:
        state = await self._sync_locked(game_id)
        if state.assembly_session and state.assembly_session.phase == "debate" and not allow_assembly:
            raise ConflictError("A assembleia está em andamento; conclua a votação.")
        if state.status != "active" or state.phase != "day":
            raise ConflictError("A investigação está indisponível nesta fase.")
        return state

    async def assert_dialogue_open(self, game_id: UUID) -> None:
        """Checagem após inferência: o chamador já mantém a reserva do jogador."""
        state = await self._repository.get(game_id)
        if (state is None or state.status != "active" or state.phase != "day"
                or self.now() >= state.phase_ends_at
                or (state.assembly_session and state.assembly_session.phase == "debate")):
            raise ConflictError("O dia terminou; consulte a próxima edição do jornal.")

    async def act(self, game_id: UUID, transition, *, start_night_on_detention: bool = False, allow_assembly=False) -> InvestigationState:
        async with self._gate.hold(game_id):
            return await self.act_locked(game_id, transition, start_night_on_detention=start_night_on_detention, allow_assembly=allow_assembly)

    async def apply_dialogue_assessment_locked(self, game_id, npc_id, conversation_id, incoming, outgoing, assessment):
        from uuid import NAMESPACE_URL, uuid5
        from src.modules.session_master.rules import dialogue_transition
        state = await self._repository.get(game_id)
        identifier = str(uuid5(NAMESPACE_URL, f'dialogue:{outgoing.id}'))
        if state is not None and any(e.get('id') == identifier for e in state.dialogue_events):
            return state
        return await self.act_locked(game_id, lambda state, game, world: dialogue_transition(
            state, game, npc_id, conversation_id, incoming, outgoing, assessment, self.now()))

    async def act_locked(self, game_id: UUID, transition, *, start_night_on_detention: bool = False, allow_assembly=False) -> InvestigationState:
        """Chamador mantém player_gate; compartilhado por ações e mestre da sessão."""
        state = await self.require_day_locked(game_id, allow_assembly=allow_assembly)
        game, world, _ = await self._load(game_id)
        result = transition(state, game, world)
        if not isinstance(result, CaseTransition):
            raise TypeError("A ação exige uma transição de investigação.")
        starts_night = (start_night_on_detention and state.detained_npc_id is None
                        and result.state.detained_npc_id is not None)
        if starts_night:
            new_accusations = result.state.accusations[len(state.accusations):]
            detention = next((record for record in new_accusations
                              if record.day == state.day and record.suspect_id == result.state.detained_npc_id
                              and record.accepted), None)
            if (len(new_accusations) != 1 or detention is None
                    or result.state.phase != state.phase or result.state.status != state.status
                    or result.state.phase_ends_at != state.phase_ends_at):
                raise ValueError("Somente uma acusação aceita pode adiantar a noite.")
        from src.modules.investigation.assembly import validate_session_transition
        session_change = validate_session_transition(state, result.state, game)
        assembly = result.state.assembly is not None and state.assembly is None
        if assembly and not session_change:
            from src.modules.investigation.assembly import convene
            record = result.state.assembly
            expected = convene(state, game, record.nominated_id or record.suspect_id, record.evidence_ids, record.testimony_ids, record.created_at)
            changes = {"assembly": expected}
            if expected.expelled and expected.suspect_id != "player":
                changes["expelled_npc_ids"] = (*state.expelled_npc_ids, expected.suspect_id)
            if expected.outcome == "werewolf":
                changes.update(status="won", phase="finished", ending_method="assembly")
            elif expected.outcome == "player_expelled":
                changes.update(status="lost", phase="finished", ending_method="player_expelled")
            if result.state != state.model_copy(update=changes):
                raise ValueError("Transição de assembleia inválida.")
        confession = self._validated_confession(state, result, game)
        if (result.state.game_id != state.game_id or result.state.day != state.day
                or (not confession and not assembly and not starts_night
                    and (result.state.phase != state.phase or result.state.status != state.status))
                or (result.state.phase_ends_at != state.phase_ends_at and not starts_night and not session_change)):
            raise ValueError("Uma ação diurna não pode mudar o relógio ou o resultado.")
        if result.state == state and not result.events:
            return state
        updated = result.state.model_copy(update={"revision": state.revision + 1})
        updated_world = world
        events = result.events
        occurred_at = self.now()
        if starts_night:
            from src.modules.investigation.interrogation import record_activities
            records = state.activity_records
            if not any(record.day == state.day and record.period == "day" for record in records):
                records += record_activities(game, world, state.day, "day", occurred_at)
            updated = updated.model_copy(update={
                "phase": "night", "phase_ends_at": occurred_at + timedelta(seconds=self._night_seconds),
                "activity_records": records,
            })
            updated_world = world.model_copy(update={
                "revision": world.revision + 1,
                "player": world.player.model_copy(update={"direction": "idle", "last_updated_at": occurred_at}),
            })
            events += (CaseEvent(type="night.started", data={"day": state.day, "reason": "accepted_detention"}),)
        if confession:
            from src.modules.session_master.editorial import final_edition
            winner_id=next(m.character_id for m in game.characters if m.role=='werewolf')
            names={p.id:p.name for p in await self._characters.list()}
            updated=updated.model_copy(update={'journal':(*updated.journal,final_edition(updated,names,werewolf_id=winner_id))})
        updated_game = game.model_copy(update={"status": "won"}) if confession else game
        if confession:
            updated_world = world.model_copy(update={"revision": world.revision + 1,
                "npcs": tuple(npc for npc in world.npcs if npc.npc_id != updated.detained_npc_id and npc.npc_id not in updated.expelled_npc_ids),
                "player": world.player.model_copy(update={"direction": "idle", "last_updated_at": self.now()})})
        if assembly:
            from src.modules.investigation.assembly import apply_assembly_effects
            updated, updated_game, updated_world = apply_assembly_effects(updated, game, updated_world, occurred_at)
        updated = await self._edit_victory(state, updated, updated_game)
        await self._repository.commit(
            previous=state, state=updated, previous_game=game, game=updated_game,
            previous_world=world, world=updated_world, events=events, occurred_at=occurred_at,
        )
        return updated

    @staticmethod
    def _validated_confession(state, result, game):
        """Exceção estreita: reavaliar as provas antes de permitir fim diurno."""
        candidate = result.state
        if candidate.status == state.status and candidate.phase == state.phase:
            return False
        if not (candidate.status == "won" and candidate.phase == "finished"
                and candidate.ending_method == "confession"
                and len(candidate.confrontations) == len(state.confrontations) + 1):
            return False
        if len(candidate.dialogue_events) == len(state.dialogue_events) + 1:
            from datetime import datetime
            from src.contracts.model import ConversationMessage
            from src.modules.session_master.service import DialogueAssessment
            from src.modules.session_master.rules import dialogue_transition
            record = candidate.dialogue_events[-1]
            try:
                instant = datetime.fromisoformat(record['created_at'])
                incoming = ConversationMessage(id=record['incoming_id'], sender_id='player', content=record['incoming'], created_at=instant)
                outgoing = ConversationMessage(id=record['outgoing_id'], sender_id=record['npc_id'], content=record['outgoing'], created_at=instant,
                    narrative_authorized=bool(record.get('narrative_authorized', False)), useful=bool(record.get('useful',False)))
                expected = dialogue_transition(state, game, record['npc_id'], UUID(record['conversation_id']), incoming, outgoing,
                    DialogueAssessment.model_validate_json(json.dumps(record['assessment'])), instant)
                return expected.state == candidate and any(e.type == 'werewolf.confessed' for e in expected.events)
            except (KeyError, ValueError, TypeError):
                return False
        record = candidate.confrontations[-1]
        if not record.confessed or candidate.detained_npc_id != record.npc_id:
            return False
        from src.modules.investigation.interrogation import make_confrontation
        expected = make_confrontation(state, game, record.npc_id, record.evidence_ids,
            record.testimony_ids, record.interrogation_ids, record.created_at)
        if expected.model_dump(exclude={"id"}) != record.model_dump(exclude={"id"}):
            return False
        canonical = state.model_copy(update={"status": "won", "phase": "finished",
            "ending_method": "confession", "detained_npc_id": record.npc_id,
            "confrontations": (*state.confrontations, record)})
        return candidate == canonical and any(event.type == "werewolf.confessed"
            and event.data.get("character_id") == record.npc_id for event in result.events)
