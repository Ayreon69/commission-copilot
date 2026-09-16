"""Accès aux modèles de langage via l'API compatible OpenAI (Gemini par défaut ; Groq, OpenRouter, Mistral…).

Une interface minimale isole le reste du code du fournisseur : les tests la remplacent par un modèle scripté,
et une chaîne de repli bascule sur le modèle suivant quand un quota gratuit est épuisé.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import openai
from openai import OpenAI

logger = logging.getLogger(__name__)


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


class OpenAICompatibleClient:
    def __init__(self, *, base_url: str, api_key: str, model: str, reasoning_effort: str | None = None,
                 max_tokens: int = 4096, timeout_s: float = 60, max_retries: int = 1):
        self._client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout_s, max_retries=max_retries)
        self.model = model
        self._reasoning_effort = reasoning_effort
        self._max_tokens = max_tokens

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMReply:
        options: dict[str, Any] = {"max_tokens": self._max_tokens}
        if tools:
            options |= {"tools": tools, "tool_choice": "auto"}
        if self._reasoning_effort:
            options["reasoning_effort"] = self._reasoning_effort
        try:
            response = self._client.chat.completions.create(model=self.model, messages=messages, **options)
        except openai.RateLimitError as exc:
            raise QuotaExceededError(f"{self.model} : quota atteint") from exc
        except (openai.InternalServerError, openai.APIConnectionError) as exc:
            logger.warning("%s indisponible : %s", self.model, exc)
            raise ModelUnavailableError(f"{self.model} : indisponible") from exc
        except openai.APIError as exc:
            logger.error("Échec de l'appel à %s : %s", self.model, exc)
            raise LLMError(f"{self.model} : {exc}") from exc

        if not response.choices:
            raise LLMError(f"{self.model} : réponse vide")
        if response.usage:
            logger.info("%s : %s jetons en entrée, %s en sortie", self.model,
                        response.usage.prompt_tokens, response.usage.completion_tokens)

        message = response.choices[0].message
        raw = message.model_dump(exclude_none=True)
        calls: list[ToolCall] = []
        for index, (call, raw_call) in enumerate(zip(message.tool_calls or [], raw.get("tool_calls", []),
                                                     strict=False)):
            function = getattr(call, "function", None)
            if function is None:
                continue
            call_id = call.id or f"call{index:05d}"
            raw_call["id"] = call_id  # l'identifiant doit être le même dans le message et dans la réponse d'outil
            calls.append(ToolCall(call_id, function.name, _parse_arguments(function.arguments)))
        return LLMReply(message.content or "", tuple(calls), self.model, raw)


class FallbackLLM:
    """Essaie les modèles dans l'ordre. Un modèle épuisé ou surchargé est mis de côté quelque temps.

    Les erreurs définitives (requête refusée, clé invalide) ne déclenchent pas de repli : un autre modèle du même
    fournisseur échouerait de la même façon.
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
        now = self._clock()
        only_quota_errors = True
        for index, client in enumerate(self._clients):
            if self._resting_until.get(index, 0) > now:
                continue
            try:
                return client.complete(messages, tools)
            except QuotaExceededError:
                logger.warning("Quota atteint pour %s : bascule sur le modèle suivant", client.model)
                self._resting_until[index] = now + self._cooldown_s
            except ModelUnavailableError:
                logger.warning("%s indisponible : bascule sur le modèle suivant", client.model)
                self._resting_until[index] = now + self._unavailable_cooldown_s
                only_quota_errors = False
        if only_quota_errors:
            raise QuotaExceededError("Quota gratuit atteint sur tous les modèles configurés")
        raise ModelUnavailableError("Aucun modèle configuré n'est disponible pour le moment")


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
