"""Accès au modèle de langage, derrière une interface minimale que les tests remplacent par un modèle scripté."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Protocol

from mistralai.client import Mistral
from mistralai.client.errors import MistralError, NoResponseError

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


class LLMError(Exception):
    """Le modèle de langage n'a pas pu répondre : réseau, quota ou erreur du fournisseur."""


class LLMClient(Protocol):
    model: str

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMReply: ...


class MistralClient:
    def __init__(self, api_key: str, model: str, *, temperature: float = 0.2, max_tokens: int = 1500,
                 timeout_ms: int = 60_000):
        self._client = Mistral(api_key=api_key)
        self.model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout_ms = timeout_ms

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMReply:
        options: dict[str, Any] = {"tools": tools, "tool_choice": "auto"} if tools else {}
        try:
            response = self._client.chat.complete(
                model=self.model,
                messages=messages,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
                timeout_ms=self._timeout_ms,
                **options,
            )
        except (MistralError, NoResponseError) as exc:
            logger.error("Échec de l'appel à Mistral : %s", exc)
            raise LLMError(str(exc)) from exc

        if not response or not response.choices or response.choices[0].message is None:
            raise LLMError("Réponse vide du modèle")
        if response.usage:
            logger.info("Mistral %s : %s jetons en entrée, %s en sortie", self.model,
                        response.usage.prompt_tokens, response.usage.completion_tokens)

        message = response.choices[0].message
        calls = tuple(
            ToolCall(id=call.id or f"call{index:05d}", name=call.function.name,
                     arguments=_parse_arguments(call.function.arguments))
            for index, call in enumerate(message.tool_calls or [])
        )
        return LLMReply(_text(message.content), calls)


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(getattr(chunk, "text", "") or "" for chunk in content)
    return ""


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
