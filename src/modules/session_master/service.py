"""Mestre de sessão com saída tipada e outbox retomável por conversa."""

from src.contracts.errors import (
    ConflictError,
    StorageUnavailableError,
)
from src.infrastructure.usage import usage_scope
from src.contracts.assessment import (
    AssessmentProposal,
    DialogueAssessment,
    PendingDialogueExchange,
)
from pydantic import ValidationError
from src.infrastructure.llm.structured import generate_structured
from src.prompts.session_master import assessment_prompt
from src.modules.session_master.validation import (
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
import asyncio
import hashlib
import json
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from src.contracts.investigation import JournalEdition
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class PreparedEditorial(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    game_id: UUID
    source_revision: int = Field(ge=0)
    source_day: int = Field(ge=1)
    suspect_id: str
    fingerprint: str
    edition: JournalEdition


class SessionMasterService:
    def __init__(self, turns, games, memory, llm=None, redis=None, prefix="ml:v1"):
        self._turns, self._games, self._memory, self._llm = turns, games, memory, llm
        self._redis, self._prefix = redis, prefix
        self._editorial_tasks = {}
        self._ready_editorials = {}
        self._editorial_slots = asyncio.Semaphore(2)
        self._closing = False

    @staticmethod
    def _editorial_inputs(state, game):
        from src.modules.characters.catalog import CHARACTERS
        from src.modules.session_master.editorial import victory_facts
        names = {profile.id: profile.name for profile in CHARACTERS}
        wolf = next(member.character_id for member in game.characters if member.role == "werewolf")
        payload = {"facts": victory_facts(state, names, wolf), "day": state.day,
                   "method": state.ending_method,
                   "clues": sum(e.collected for c in state.crimes for e in c.evidence),
                   "testimonies": len(state.testimonies)}
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        return names, wolf, fingerprint

    def _editorial_key(self, game_id):
        return f"{self._prefix}:game:{{{game_id}}}:prepared-victory-editorial"

    def prepare_detention_editorial(self, state, game):
        """Schedule only after the detention commit; never await model work here.

        Every detention takes the same public path. Only the private job inspects
        the role, and its result cannot be read through the public investigation.
        """
        if self._closing:
            return
        old = self._editorial_tasks.get(game.id)
        if old is not None:
            old.cancel()
        self._ready_editorials.pop(game.id, None)
        if old is None and len(self._editorial_tasks) >= 128:
            return
        task = asyncio.create_task(self._prepare_editorial(state, game))
        self._editorial_tasks[game.id] = task
        def completed(done):
            if self._editorial_tasks.get(game.id) is done:
                self._editorial_tasks.pop(game.id, None)
            if not done.cancelled():
                error = done.exception()
                if error is not None:
                    logger.warning("victory_editorial_task_failed code=%s", type(error).__name__)
        task.add_done_callback(completed)

    async def _prepare_editorial(self, source, game):
        from src.modules.session_master.editorial import final_edition, victory_article
        names, wolf, _ = self._editorial_inputs(source, game)
        if (source.phase != "night" or source.status != "active"
                or source.detained_npc_id != wolf or self._llm is None):
            return
        # Detaining the actual wolf has a deterministic next-morning outcome.
        # Only this unpublished projection is sent to the editorial renderer.
        projected = source.model_copy(update={"day": source.day + 1, "revision": source.revision + 1,
            "phase": "finished", "status": "won", "ending_method": "detention", "detained_npc_id": None})
        projected = projected.model_copy(update={"journal": (*source.journal,
            final_edition(projected, names, werewolf_id=wolf, detention="transformed"))})
        _, _, fingerprint = self._editorial_inputs(projected, game)
        try:
            # Budget includes queue time; a delayed provider must not outlive
            # the suspense window or accumulate unlimited generation work.
            async with asyncio.timeout(6):
                async with self._editorial_slots:
                    current = await self._turns._repository.get(game.id)
                    remaining = (source.phase_ends_at - self._turns.now()).total_seconds()
                    if (current is None or current.revision != source.revision
                            or current.phase != 'night' or current.status != 'active'
                            or current.detained_npc_id != wolf or remaining <= 1):
                        return
                    async with asyncio.timeout(min(6, remaining - .25)):
                        edition = await victory_article(projected, names, wolf, self._llm)
            latest = await self._turns._repository.get(game.id)
            if (latest is None or latest.revision != source.revision or latest.day != source.day
                    or latest.phase != "night" or latest.status != "active"
                    or latest.detained_npc_id != wolf):
                return
            record = PreparedEditorial(game_id=game.id, source_revision=source.revision,
                source_day=source.day, suspect_id=wolf, fingerprint=fingerprint, edition=edition)
            if self._redis is not None:
                await self._redis.set(self._editorial_key(game.id), record.model_dump_json(), ex=3600)
            self._ready_editorials[game.id] = record
            if len(self._ready_editorials) > 128:
                self._ready_editorials.pop(next(iter(self._ready_editorials)))
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.warning("victory_editorial_background_fallback code=%s", type(error).__name__)

    async def publish_victory(self, state, game):
        """Use already prepared opinion, or publish canonical facts immediately."""
        from src.modules.session_master.editorial import victory_article
        names, wolf, fingerprint = self._editorial_inputs(state, game)
        fallback = await victory_article(state, names, wolf, None)
        record = self._ready_editorials.get(game.id)
        if record is None and self._redis is not None and state.ending_method == "detention":
            try:
                # Optional cache reads must not turn a model outage into a long
                # player reservation. The authoritative fallback is already ready.
                async with asyncio.timeout(.05):
                    raw = await self._redis.get(self._editorial_key(game.id))
                record = PreparedEditorial.model_validate_json(raw) if raw else None
            except (TimeoutError, RedisError, ValidationError, ValueError, TypeError):
                record = None
        valid = (record is not None and state.ending_method == "detention"
                 and record.game_id == game.id and record.suspect_id == wolf
                 and record.source_day + 1 == state.day
                 and record.source_revision + 1 == state.revision
                 and record.fingerprint == fingerprint)
        pending = self._editorial_tasks.get(game.id)
        if pending is not None:
            # No result should continue spending tokens after its publication
            # opportunity. Cancellation is requested without awaiting the task.
            pending.cancel()
        # Keep headline, day, illustration and all canonical fields from the
        # actual resolved edition; the prepared job contributes its body only.
        edition = fallback.model_copy(update={"body": record.edition.body}) if valid else fallback
        return state.model_copy(update={"journal": (*state.journal[:-1], edition)})

    async def aclose(self):
        self._closing = True
        tasks = tuple(self._editorial_tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._editorial_tasks.clear()
        self._ready_editorials.clear()

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
        from src.modules.agents.support import is_courtesy_reply

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
