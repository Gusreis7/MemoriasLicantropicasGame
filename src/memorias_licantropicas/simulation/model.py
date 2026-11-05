"""Dublês offline e cota explícita para execução opcional com provedor real."""

from collections import Counter
import json
from typing import Literal

from memorias_licantropicas.contracts.errors import LLMUnavailableError
from memorias_licantropicas.contracts.model import LLMResponse

Fault = Literal["none", "invalid_json_once", "invalid_json_always", "authentication"]


class OfflineSessionModel:
    """Deterministic provider double reading only the prompt supplied to each role.

    Exact authorized quotations make provenance testable. No repository access,
    hidden-role inference, fake tool execution or API key lives in this double.
    """

    def __init__(self, fault: Fault = "none"):
        self.fault = fault
        self.calls = Counter()
        self.injected_faults = 0

    @staticmethod
    def _payload(messages):
        for message in reversed(messages):
            if message.role == "user":
                try:
                    return json.loads(message.content)
                except (ValueError, TypeError):
                    continue
        return {}

    @staticmethod
    def _context(messages, marker):
        for message in messages:
            if marker in message.content:
                return json.loads(message.content.split(marker, 1)[1])
        return {}

    @staticmethod
    def task_for(messages):
        instructions = "\n".join(
            message.content for message in messages if message.role == "system"
        )
        if "task:npc_dialogue" in instructions or "Ficha privada:\n" in instructions:
            task = "npc_dialogue"
        elif (
            "task:session_assessment" in instructions
            or "mestre privado de uma investigação" in instructions
        ):
            task = "session_assessment"
        elif (
            "task:knowledge_extraction" in instructions
            or "Extraia alegações" in instructions
        ):
            task = "knowledge_extraction"
        elif (
            "task:social_speech" in instructions
            or "Dados autorizados:\n" in instructions
        ):
            task = "social_speech"
        elif (
            "task:editorial" in instructions
            or "pequeno artigo de opinião" in instructions
        ):
            task = "editorial"
        elif "assembleia breve" in instructions:
            task = "assembly_debate"
        else:
            raise AssertionError("Simulation received an unidentified LLM task")
        return task

    async def complete(self, messages):
        task = self.task_for(messages)
        self.calls[task] += 1
        if task == "npc_dialogue" and self.fault == "authentication":
            self.injected_faults += 1
            raise LLMUnavailableError(
                "Offline authentication fixture", code="llm_authentication_failed"
            )
        if task == "npc_dialogue" and (
            self.fault == "invalid_json_always"
            or self.fault == "invalid_json_once"
            and not self.injected_faults
        ):
            self.injected_faults += 1
            return LLMResponse(
                content='{"fala":',
                model="offline-session-double",
                input_tokens=0,
                output_tokens=0,
            )
        payload = self._payload(messages)
        if task == "npc_dialogue":
            private = self._context(messages, "Ficha privada:\n")
            observations = private.get("observacoes_autorizadas", {})
            focused = observations.get("ultimo_objeto_apresentado") or {}
            supports = observations.get("apoios_de_conversa", ())
            speech = focused.get("fala_registrada")
            if not speech and supports:
                speech = (
                    supports[0].get("texto")
                    or supports[0].get("text")
                    or supports[0].get("fala")
                )
            if not speech:
                own = observations.get("suas_atividades", ())
                speech = own[-1].get("lembranca") if own else None
            speech = (
                speech
                or "Bom dia, detetive. Quero ajudar; diga qual assunto deseja esclarecer."
            )
            content = json.dumps({"fala": speech}, ensure_ascii=False)
        elif task == "session_assessment":
            speech = payload.get("personagem", "")
            useful = any(
                word in speech.casefold()
                for word in ("reconheço", "já vi", "estava", "contas", "selo")
            )
            content = json.dumps(
                {
                    "kind": "conversation",
                    "issues": [],
                    "useful": useful,
                    "useful_quote": speech if useful else "",
                },
                ensure_ascii=False,
            )
        elif task == "knowledge_extraction":
            claims = [
                {
                    "message_id": item["message_id"],
                    "source_span": item["text"],
                    "proposition": item["text"],
                    "subject_ids": [],
                    "claimed_source_id": None,
                    "kind": "report",
                    "disposition": "neutral",
                    "parent_claim_ids": [],
                }
                for item in payload.get("messages", ())
                if 8 <= len(item["text"]) <= 1200
            ]
            content = json.dumps({"claims": claims[:8]}, ensure_ascii=False)
        elif task == "social_speech":
            authorized = self._context(messages, "Dados autorizados:\n")
            available = authorized.get("alegacoes_compartilhaveis", ())
            claim = available[0] if available else None
            speech = (
                claim["proposicao"]
                if claim
                else "Ainda tenho dúvidas sobre o que aconteceu; prefiro ouvir as pessoas."
            )
            content = json.dumps(
                {
                    "fala": speech,
                    "intent": "repeat" if claim else "ask",
                    "claim_ids": [claim["id"]] if claim else [],
                },
                ensure_ascii=False,
            )
        elif task == "assembly_debate":
            content = json.dumps(
                {"messages": payload["falas_publicas"], "argument_strength": 0.5},
                ensure_ascii=False,
            )
        else:
            speech = (
                "A cidade deve a Floriano o alívio de ver encerrada esta ameaça. "
                "Celebramos sua persistência, sem esquecer o luto que nenhuma vitória apaga. "
                "Os fatos confirmados encerram a investigação, e os moradores podem voltar a respirar."
            )
            content = json.dumps({"opinion": speech}, ensure_ascii=False)
        # Explicit character-count approximation, not tokenizer/provider measurements.
        input_tokens = sum(len(message.content) for message in messages) // 4
        return LLMResponse(
            content=content,
            model="offline-session-double",
            input_tokens=input_tokens,
            output_tokens=max(1, len(content) // 4),
        )

    async def aclose(self):
        return None


class BudgetedSessionModel:
    """Live adapter used only after explicit CLI opt-in, with a run-wide call cap."""

    def __init__(self, client, max_calls):
        if max_calls < 1:
            raise ValueError("A positive provider-call budget is required")
        self.client, self.max_calls = client, max_calls
        self.calls = Counter()
        self.injected_faults = 0
        self.exhausted = False

    async def complete(self, messages):
        if sum(self.calls.values()) >= self.max_calls:
            self.exhausted = True
            raise LLMUnavailableError(
                "Simulation provider-call budget exhausted", code="llm_unavailable"
            )
        self.calls[OfflineSessionModel.task_for(messages)] += 1
        return await self.client.complete(messages)

    async def aclose(self):
        await self.client.aclose()

