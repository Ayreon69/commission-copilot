"""Accès aux modèles de langage via l'API compatible OpenAI (Gemini par défaut ; Groq, OpenRouter, Mistral…).

Une interface minimale isole le reste du code du fournisseur : les tests la remplacent par un modèle scripté,
et une chaîne de repli bascule sur le modèle suivant quand un modèle est saturé ou à court de quota.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

import openai
from openai import OpenAI

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class LLMReply:
    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    model: str = ""
    # Message tel que renvoyé par le fournisseur, à lui renvoyer à l'identique au tour suivant : il peut contenir
    # des champs propres au fournisseur, comme les signatures de raisonnement de Gemini 3.
    raw_message: dict[str, Any] | None = None


@dataclass(frozen=True)
class TextChunk:
    """Fragment de texte reçu pendant la génération d'une réponse."""

    text: str


class LLMError(Exception):
    """Le modèle de langage n'a pas pu répondre : réseau, requête refusée ou erreur du fournisseur."""


class QuotaExceededError(LLMError):
    """Le quota du fournisseur est épuisé (erreur 429)."""


class ModelUnavailableError(LLMError):
    """Le modèle est momentanément indisponible : surcharge (503), panne ou délai dépassé."""


class LLMClient(Protocol):
    @property
    def model(self) -> str: ...

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMReply: ...


def reply_chunks(llm: LLMClient, messages: list[dict[str, Any]], tools: list[dict[str, Any]], *,
                 stream: bool) -> Iterator[TextChunk | LLMReply]:
    """Fragments de texte puis réponse complète. Un client sans streaming livre son texte en un seul fragment."""
    stream_method = getattr(llm, "stream", None)
    if stream and stream_method is not None:
        yield from stream_method(messages, tools)
        return
    reply = llm.complete(messages, tools)
    if reply.content:
        yield TextChunk(reply.content)
    yield reply


class OpenAICompatibleClient:
    def __init__(self, *, base_url: str, api_key: str, model: str, reasoning_effort: str | None = None,
                 max_tokens: int = 4096, timeout_s: float = 60, max_retries: int = 1):
        self._client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout_s, max_retries=max_retries)
        self.model = model
        self._reasoning_effort = reasoning_effort
        self._max_tokens = max_tokens

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMReply:
        with self._translated_errors():
            response = self._client.chat.completions.create(model=self.model, messages=messages,
                                                            **self._options(tools))
        if not response.choices:
            raise LLMError(f"{self.model} : réponse vide")
        if response.usage:
            logger.info("%s : %s jetons en entrée, %s en sortie", self.model,
                        response.usage.prompt_tokens, response.usage.completion_tokens)
        message = response.choices[0].message
        return self._reply(message.content or "", message.model_dump(exclude_none=True))

    def stream(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Iterator[TextChunk | LLMReply]:
        content: list[str] = []
        calls: dict[int, dict[str, Any]] = {}
        with self._translated_errors():
            chunks = self._client.chat.completions.create(model=self.model, messages=messages, stream=True,
                                                          **self._options(tools))
            for chunk in chunks:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta.content:
                    content.append(delta.content)
                    yield TextChunk(delta.content)
                for call in delta.tool_calls or []:
                    part = call.model_dump(exclude_none=True)
                    _deep_merge(calls.setdefault(_call_slot(calls, part), {}), part)

        raw: dict[str, Any] = {"role": "assistant"}
        if content:
            raw["content"] = "".join(content)
        if calls:
            raw["tool_calls"] = [calls[index] for index in sorted(calls)]
        yield self._reply(raw.get("content", ""), raw)

    def _options(self, tools: list[dict[str, Any]]) -> dict[str, Any]:
        options: dict[str, Any] = {"max_tokens": self._max_tokens}
        if tools:
            options |= {"tools": tools, "tool_choice": "auto"}
        if self._reasoning_effort:
            options["reasoning_effort"] = self._reasoning_effort
        return options

    def _reply(self, content: str, raw: dict[str, Any]) -> LLMReply:
        calls: list[ToolCall] = []
        for index, raw_call in enumerate(raw.get("tool_calls", [])):
            function = raw_call.get("function")
            if not function:
                continue
            raw_call["id"] = raw_call.get("id") or f"call{index:05d}"  # même identifiant dans le message et l'outil
            raw_call.setdefault("type", "function")
            arguments = _parse_arguments(function.get("arguments"))
            calls.append(ToolCall(raw_call["id"], function.get("name", ""), arguments))
        return LLMReply(content, tuple(calls), self.model, raw)

    @contextmanager
    def _translated_errors(self) -> Iterator[None]:
        try:
            yield
        except openai.RateLimitError as exc:
            raise QuotaExceededError(f"{self.model} : quota atteint") from exc
        except (openai.InternalServerError, openai.APIConnectionError) as exc:
            logger.warning("%s indisponible : %s", self.model, exc)
            raise ModelUnavailableError(f"{self.model} : indisponible") from exc
        except openai.APIError as exc:
            logger.error("Échec de l'appel à %s : %s", self.model, exc)
            raise LLMError(f"{self.model} : {exc}") from exc


class FallbackLLM:
    """Essaie les modèles dans l'ordre. Un modèle épuisé ou surchargé est mis de côté quelque temps.

    Les erreurs définitives (requête refusée, clé invalide) ne déclenchent pas de repli : un autre modèle du même
    fournisseur échouerait de la même façon. En streaming, le repli n'est possible qu'avant le premier fragment reçu.
    """

    def __init__(self, clients: Sequence[LLMClient], cooldown_s: float = 60, unavailable_cooldown_s: float = 15,
                 clock: Callable[[], float] = time.monotonic):
        if not clients:
            raise ValueError("Au moins un modèle doit être configuré")
        self._clients = list(clients)
        self._cooldown_s = cooldown_s
        self._unavailable_cooldown_s = unavailable_cooldown_s
        self._clock = clock
        self._resting_until: dict[int, float] = {}

    @property
    def model(self) -> str:
        return self._clients[0].model

    @property
    def models(self) -> list[str]:
        return [client.model for client in self._clients]

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMReply:
        return next(self._with_fallback(lambda client: iter([client.complete(messages, tools)])))

    def stream(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Iterator[TextChunk | LLMReply]:
        yield from self._with_fallback(lambda client: reply_chunks(client, messages, tools, stream=True))

    def _with_fallback(self, call: Callable[[LLMClient], Iterator[T]]) -> Iterator[T]:
        now = self._clock()
        only_quota_errors = True
        for index, client in enumerate(self._clients):
            if self._resting_until.get(index, 0) > now:
                continue
            produced = False
            try:
                for item in call(client):
                    produced = True
                    yield item
                return
            except QuotaExceededError:
                if produced:
                    raise
                logger.warning("Quota atteint pour %s : bascule sur le modèle suivant", client.model)
                self._resting_until[index] = now + self._cooldown_s
            except ModelUnavailableError:
                if produced:
                    raise
                logger.warning("%s indisponible : bascule sur le modèle suivant", client.model)
                self._resting_until[index] = now + self._unavailable_cooldown_s
                only_quota_errors = False
        if only_quota_errors:
            raise QuotaExceededError("Quota gratuit atteint sur tous les modèles configurés")
        raise ModelUnavailableError("Aucun modèle configuré n'est disponible pour le moment")


def _call_slot(calls: dict[int, dict[str, Any]], part: dict[str, Any]) -> int:
    """Position de l'appel d'outil auquel appartient un fragment reçu en streaming."""
    index = part.pop("index", None)
    if index is not None:
        return index
    call_id = part.get("id")
    for existing_index, existing in calls.items():
        if call_id and existing.get("id") == call_id:
            return existing_index
    return len(calls) if call_id or not calls else max(calls)


def _deep_merge(target: dict[str, Any], part: dict[str, Any]) -> None:
    for key, value in part.items():
        if key == "arguments" and isinstance(value, str):
            target[key] = target.get(key, "") + value  # les arguments arrivent en morceaux de JSON à recoller
        elif isinstance(value, dict):
            _deep_merge(target.setdefault(key, {}), value)
        else:
            target[key] = value


def _parse_arguments(raw: Any) -> dict[str, Any]:
    # Des arguments illisibles deviennent un dictionnaire vide : la validation de l'outil renverra au modèle
    # une erreur explicite qu'il pourra corriger.
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        logger.warning("Arguments d'outil illisibles : %r", raw)
        return {}
    return parsed if isinstance(parsed, dict) else {}
