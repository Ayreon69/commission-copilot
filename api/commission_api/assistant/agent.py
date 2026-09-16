"""Boucle d'appel d'outils : le modèle choisit les calculs à lancer, le moteur les exécute."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ..schemas import ChatMessage
from .guard import unverified_amounts
from .llm import LLMClient, ToolCall
from .tools import Toolbox, ToolError

logger = logging.getLogger(__name__)

FALLBACK_ANSWER = (
    "Je n'ai pas réussi à terminer l'analyse en un nombre raisonnable d'étapes. "
    "Pouvez-vous reformuler ou préciser la question ?"
)


@dataclass(frozen=True)
class ToolTrace:
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]
    ok: bool


@dataclass(frozen=True)
class AssistantAnswer:
    content: str
    tool_calls: tuple[ToolTrace, ...]
    unverified_amounts: tuple[str, ...]
    model: str  # modèle qui a produit la réponse finale (il peut changer en cours de route en cas de repli)


class Assistant:
    def __init__(self, llm: LLMClient, toolbox: Toolbox, system_prompt: str, knowledge: str,
                 max_tool_rounds: int = 4):
        self.llm = llm
        self.toolbox = toolbox
        self.system_prompt = system_prompt
        self.knowledge = knowledge
        self.max_tool_rounds = max_tool_rounds

    @property
    def model(self) -> str:
        return self.llm.model

    def answer(self, history: Sequence[ChatMessage]) -> AssistantAnswer:
        messages: list[dict[str, Any]] = [{"role": "system", "content": self.system_prompt}]
        messages += [{"role": message.role, "content": message.content} for message in history]
        traces: list[ToolTrace] = []
        answered_by = self.llm.model

        for round_index in range(self.max_tool_rounds + 1):
            # Au dernier tour, plus d'outils : le modèle doit conclure avec les résultats déjà obtenus.
            tools = self.toolbox.definitions if round_index < self.max_tool_rounds else []
            reply = self.llm.complete(messages, tools)
            answered_by = reply.model or answered_by
            if not reply.tool_calls:
                return self._finish(reply.content, traces, history, answered_by)
            if not tools:
                break  # le modèle réclame encore des outils alors qu'ils ne lui sont plus proposés

            messages.append(reply.raw_message or _assistant_message(reply.content, reply.tool_calls))
            for call in reply.tool_calls:
                trace = self._run(call)
                traces.append(trace)
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": call.name,
                    "content": json.dumps(trace.result, ensure_ascii=False),
                })

        logger.warning("Boucle d'outils interrompue après %d tours", self.max_tool_rounds)
        return self._finish(FALLBACK_ANSWER, traces, history, answered_by)

    def _run(self, call: ToolCall) -> ToolTrace:
        started = time.perf_counter()
        try:
            result, ok = self.toolbox.execute(call.name, call.arguments), True
        except ToolError as exc:
            result, ok = {"error": str(exc)}, False
        logger.info("Outil %s : %s en %.0f ms", call.name, "succès" if ok else "erreur",
                    (time.perf_counter() - started) * 1000)
        return ToolTrace(call.name, call.arguments, result, ok)

    def _finish(self, content: str, traces: list[ToolTrace], history: Sequence[ChatMessage],
                model: str) -> AssistantAnswer:
        # Les réponses précédentes de l'assistant ne sont pas des sources : cela blanchirait un montant inventé.
        texts = [self.knowledge, *(m.content for m in history if m.role == "user")]
        flagged = unverified_amounts(content, texts, [trace.result for trace in traces])
        if flagged:
            logger.warning("Montants sans source dans la réponse : %s", ", ".join(flagged))
        return AssistantAnswer(content, tuple(traces), tuple(flagged), model)


def _assistant_message(content: str, calls: Sequence[ToolCall]) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": content,
        "tool_calls": [
            {"id": call.id, "type": "function",
             "function": {"name": call.name, "arguments": json.dumps(call.arguments, ensure_ascii=False)}}
            for call in calls
        ],
    }
