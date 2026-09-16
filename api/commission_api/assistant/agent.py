"""Boucle d'appel d'outils : le modèle choisit les calculs à lancer, le moteur les exécute.

`events()` produit le déroulé au fil de l'eau (texte, appels d'outils, réponse finale) pour le streaming ;
`answer()` attend simplement la réponse finale.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any

from commission_engine.models import RULE_LABELS

from ..schemas import ChatMessage
from .guard import Citation, rule_citations, unknown_products, unverified_amounts
from .llm import LLMClient, LLMError, LLMReply, TextChunk, ToolCall, reply_chunks
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
    citations: tuple[Citation, ...] = ()
    unknown_rules: tuple[str, ...] = ()
    unknown_products: tuple[str, ...] = ()


@dataclass(frozen=True)
class TextDelta:
    """Texte généré par le modèle. Un texte qui précède des appels d'outils n'est pas la réponse finale."""

    text: str


@dataclass(frozen=True)
class ToolStarted:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolFinished:
    trace: ToolTrace


@dataclass(frozen=True)
class Completed:
    answer: AssistantAnswer


AgentEvent = TextDelta | ToolStarted | ToolFinished | Completed


class Assistant:
    def __init__(self, llm: LLMClient, toolbox: Toolbox, system_prompt: str, knowledge: str,
                 max_tool_rounds: int = 4):
        self.llm = llm
        self.toolbox = toolbox
        self.system_prompt = system_prompt
        self.knowledge = knowledge
        self.max_tool_rounds = max_tool_rounds
        catalog = toolbox.service.catalog
        self._product_labels = [product.label for product in catalog.products.values()]
        self._other_names = list(catalog.insurers.values())

    @property
    def model(self) -> str:
        return self.llm.model

    def answer(self, history: Sequence[ChatMessage]) -> AssistantAnswer:
        for event in self.events(history, stream=False):
            if isinstance(event, Completed):
                return event.answer
        raise AssertionError("inaccessible")

    def events(self, history: Sequence[ChatMessage], *, stream: bool = True) -> Iterator[AgentEvent]:
        messages: list[dict[str, Any]] = [{"role": "system", "content": self.system_prompt}]
        messages += [{"role": message.role, "content": message.content} for message in history]
        traces: list[ToolTrace] = []
        answered_by = self.llm.model

        for round_index in range(self.max_tool_rounds + 1):
            # Au dernier tour, plus d'outils : le modèle doit conclure avec les résultats déjà obtenus.
            tools = self.toolbox.definitions if round_index < self.max_tool_rounds else []
            reply: LLMReply | None = None
            for item in reply_chunks(self.llm, messages, tools, stream=stream):
                if isinstance(item, TextChunk):
                    yield TextDelta(item.text)
                else:
                    reply = item
            if reply is None:
                raise LLMError("Réponse vide du modèle")

            answered_by = reply.model or answered_by
            if not reply.tool_calls:
                yield Completed(self._finish(reply.content, traces, history, answered_by))
                return
            if not tools:
                break  # le modèle réclame encore des outils alors qu'ils ne lui sont plus proposés

            messages.append(reply.raw_message or _assistant_message(reply.content, reply.tool_calls))
            for call in reply.tool_calls:
                yield ToolStarted(call.name, call.arguments)
                trace = self._run(call)
                traces.append(trace)
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": call.name,
                    "content": json.dumps(trace.result, ensure_ascii=False),
                })
                yield ToolFinished(trace)

        logger.warning("Boucle d'outils interrompue après %d tours", self.max_tool_rounds)
        yield Completed(self._finish(FALLBACK_ANSWER, traces, history, answered_by))

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
        payloads = [trace.result for trace in traces]
        # Les réponses précédentes de l'assistant ne sont pas des sources : cela blanchirait un montant inventé.
        texts = [self.knowledge, *(m.content for m in history if m.role == "user")]
        flagged_amounts = unverified_amounts(content, texts, payloads)
        citations, unknown_rules = rule_citations(content, payloads, RULE_LABELS)
        flagged_products = unknown_products(content, self._product_labels, self._other_names)
        for label, values in (("Montants sans source", flagged_amounts), ("Règles inexistantes", unknown_rules),
                              ("Produits inexistants", flagged_products)):
            if values:
                logger.warning("%s dans la réponse : %s", label, ", ".join(values))
        return AssistantAnswer(content, tuple(traces), tuple(flagged_amounts), model, tuple(citations),
                               tuple(unknown_rules), tuple(flagged_products))


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
