"""Mestre de sessão com saída tipada e outbox retomável por conversa."""

from memorias_licantropicas.contracts.errors import (
    ConflictError,
    StorageUnavailableError,
)
from memorias_licantropicas.infrastructure.usage import usage_scope
from memorias_licantropicas.contracts.assessment import (
    AssessmentProposal,
    DialogueAssessment,
    PendingDialogueExchange,
)
from pydantic import ValidationError
from memorias_licantropicas.infrastructure.llm.structured import generate_structured
from memorias_licantropicas.prompts.session_master import assessment_prompt
from memorias_licantropicas.modules.session_master.validation import (
    admission_evidence,
    direct_admission,
    local_assessment,
    normalize,
    own_assertion_clauses,
    validate_assessment,
)

__all__ = [
    "SessionMasterService",
    "DialogueAssessment",
    "direct_admission",
    "local_assessment",
    "admission_evidence",
    "normalize",
    "own_assertion_clauses",
]
import logging

logger = logging.getLogger(__name__)


class SessionMasterService:
    def __init__(self, turns, games, memory, llm=None, redis=None, prefix="ml:v1"):
        self._turns, self._games, self._memory, self._llm = turns, games, memory, llm
        self._redis, self._prefix = redis, prefix

    async def publish_victory(self, state, game):
        """Redige a edição final antes do commit, sem alterar o resultado do motor."""
        from memorias_licantropicas.modules.session_master.editorial import (
            victory_article,
        )
        from memorias_licantropicas.modules.characters.catalog import CHARACTERS

        names = {profile.id: profile.name for profile in CHARACTERS}
        wolf = next(
            member.character_id
            for member in game.characters
            if member.role == "werewolf"
        )
        edition = await victory_article(state, names, wolf, self._llm)
        return state.model_copy(update={"journal": (*state.journal[:-1], edition)})

    def _key(self, game_id, conversation_id):
        return f"{self._prefix}:game:{{{game_id}}}:session-pending:{conversation_id}"

    async def assess(
        self,
        game_id,
        npc_id,
        conversation_id,
        incoming,
        outgoing,
        *,
        observations=None,
        profile=None,
    ):
        state = await self._turns.require_day_locked(game_id)
        base = local_assessment(incoming.content, outgoing.content, state.day)
        from memorias_licantropicas.modules.agents.support import is_courtesy_reply

        if is_courtesy_reply(incoming.content, outgoing.content):
            return base
        if self._llm is None:
            return base
        prompt = assessment_prompt(
            npc_id, state.day, incoming, outgoing, observations, profile
        )
        with usage_scope(game_id, "session_master", npc_id):
            result = await generate_structured(
                self._llm, prompt, AssessmentProposal, max_attempts=2
            )
        if not result.ok:
            logger.warning(
                "session_assessment_fallback game_id=%s code=%s",
                game_id,
                result.error_code,
            )
            return base.model_copy(
                update={
                    "source": "fallback",
                    "attempts": result.attempts,
                    "error_code": result.error_code,
                }
            )
        proposal = DialogueAssessment(
            **result.value.model_dump(), source="model", attempts=result.attempts
        )
        return validate_assessment(proposal, base, incoming, outgoing, state.day)

    async def can_disclose_role(self, game_id, npc_id, incoming, outgoing, assessment):
        game = await self._games.get(game_id)
        direct, _ = admission_evidence(outgoing.content, incoming.content, assessment)
        return bool(
            direct
            and assessment.own_assertion
            and any(
                m.character_id == npc_id and m.role == "werewolf"
                for m in game.characters
            )
        )

    async def persist_exchange(
        self, game_id, npc_id, conversation_id, incoming, outgoing, assessment
    ):
        pending = PendingDialogueExchange(
            game_id=game_id,
            npc_id=npc_id,
            conversation_id=conversation_id,
            incoming=incoming,
            outgoing=outgoing,
            assessment=assessment,
        )
        if self._redis is not None:
            await self._redis.set(
                self._key(game_id, conversation_id), pending.model_dump_json(), ex=86400
            )
        await self._complete(pending)

    async def _complete(self, pending: PendingDialogueExchange):
        await self._turns.apply_dialogue_assessment_locked(
            pending.game_id,
            pending.npc_id,
            pending.conversation_id,
            pending.incoming,
            pending.outgoing,
            pending.assessment,
        )
        await self._memory.append_messages(
            pending.game_id,
            pending.conversation_id,
            (pending.incoming, pending.outgoing),
        )
        if self._redis is not None:
            await self._redis.delete(
                self._key(pending.game_id, pending.conversation_id)
            )

    async def reconcile(self, game_id, conversation_id):
        if self._redis is None:
            return
        raw = await self._redis.get(self._key(game_id, conversation_id))
        if raw:
            try:
                pending = PendingDialogueExchange.model_validate_json(raw)
            except (ValidationError, ValueError, TypeError):
                raise StorageUnavailableError(
                    "Registro pendente de conversa inválido."
                ) from None
            if pending.game_id != game_id or pending.conversation_id != conversation_id:
                raise ConflictError("Registro pendente de conversa inconsistente.")
            await self._complete(pending)
