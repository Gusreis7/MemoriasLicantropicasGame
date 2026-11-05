"""Casos de uso da sessão curta; inferência nunca mantém o Redis bloqueado."""
from datetime import timedelta
from src.contracts.errors import ConflictError
from src.contracts.investigation import CaseEvent,CaseTransition
from src.modules.investigation.assembly import open_session,enrich_debate,resolve_transition


class AssemblyServiceMixin:
    async def open_assembly(self,game_id,suspect_id,evidence_ids=(),testimony_ids=(),speech=''):
        state=await self._turns.sync(game_id)
        if state.phase!='day' or state.status!='active':
            raise ConflictError('A assembleia exige um dia em andamento.')
        if state.assembly_session and state.assembly_session.phase=='debate':
            session=state.assembly_session
            if (session.suspect_id==suspect_id and session.opening_speech==speech.strip()
                    and set(session.evidence_ids)==set(evidence_ids) and set(session.testimony_ids)==set(testimony_ids)):
                return await self.public(state)
            raise ConflictError('Retome a assembleia que já está aberta.')
        game,world,_=await self._turns._load(game_id)
        from src.modules.knowledge.rules import initial_relationships
        social_repo=getattr(self,'_social_repository',None)
        social=await social_repo.get(game_id) if social_repo else None
        relationships=social.relationships if social and social.relationships else initial_relationships(tuple(m.character_id for m in game.characters))
        now=self._turns.now()
        session=open_session(state,game,suspect_id,evidence_ids,testimony_ids,speech,now,relationships)
        session=await enrich_debate(getattr(self,'_assembly_llm',None),game_id,state,game,session)
        def transition(current,game,world):
            if current.revision!=state.revision:
                raise ConflictError('O caso mudou enquanto a assembleia era preparada; tente novamente.')
            # Generation time is outside the debating window, but cannot extend a day already over.
            started=self._turns.now()
            if started>=current.phase_ends_at:
                raise ConflictError('O dia terminou antes da abertura da assembleia.')
            opened=session.model_copy(update={'opened_at':started,'deadline':started+timedelta(seconds=60),
                'remaining_day_seconds':(current.phase_ends_at-started).total_seconds()})
            updated=current.model_copy(update={'assembly_session':opened,
                'phase_ends_at':opened.deadline+timedelta(seconds=opened.remaining_day_seconds)})
            return CaseTransition(state=updated,events=(CaseEvent(type='assembly.opened',data={'session_id':str(opened.id),'suspect_id':suspect_id}),))
        return await self.public(await self._turns.act(game_id,transition))

    async def resolve_assembly(self,game_id,reply=''):
        # GET/sync resolves an expired session; retry returns the same completed record.
        state=await self._turns.sync(game_id)
        if state.assembly is not None:
            return await self.public(state)
        def transition(current,game,world):
            return resolve_transition(current,game,self._turns.now(),reply)
        return await self.public(await self._turns.act(game_id,transition,allow_assembly=True))
