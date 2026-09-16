"""Routes HTTP de l'API."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from .assistant.agent import Assistant, AssistantAnswer, Completed, TextDelta, ToolFinished, ToolStarted, ToolTrace
from .assistant.llm import LLMError, QuotaExceededError
from .schemas import (
    CalculationOut,
    ChatRequest,
    ChatResponse,
    CitationOut,
    HealthOut,
    PerimeterDetailsOut,
    PerimeterSummaryOut,
    SampleContractOut,
    SimulationRequest,
    ToolCallTrace,
)
from .services import CommissionService

QUOTA_MESSAGE = ("Le quota gratuit de la démonstration est atteint. Réessayez dans quelques minutes, "
                 "ou demain si le quota journalier est épuisé.")
UNAVAILABLE_MESSAGE = "Le modèle de langage est momentanément indisponible. Réessayez dans quelques instants."
NO_KEY_MESSAGE = "Assistant indisponible : la variable LLM_API_KEY n'est pas configurée."

STREAM_DESCRIPTION = """Flux Server-Sent Events. Événements, dans l'ordre où ils surviennent :

- `delta` `{"text"}` : texte généré. Le texte qui précède des appels d'outils n'est pas la réponse finale.
- `tool_call` `{"name", "arguments"}` : un outil va être exécuté.
- `tool_result` : trace de l'appel (même format que `tool_calls` de `/api/chat`).
- `done` : réponse complète, au même format que `/api/chat`.
- `error` `{"status", "detail"}` : échec du modèle (429 quota épuisé, 502 indisponible) ; le flux s'arrête.
"""

router = APIRouter(prefix="/api")


def _service(request: Request) -> CommissionService:
    return request.app.state.service


def _assistant(request: Request) -> Assistant:
    """Assistant configuré, après décompte de la question dans les limites de débit de la démo."""
    assistant: Assistant | None = request.app.state.assistant
    if assistant is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, NO_KEY_MESSAGE)
    request.app.state.rate_limiter.acquire(_visitor(request))
    return assistant


def _visitor(request: Request) -> str:
    # Derrière un proxy, uvicorn --proxy-headers renseigne ici l'adresse réelle du visiteur.
    return request.client.host if request.client else "inconnu"


@router.get("/health", response_model=HealthOut, tags=["système"])
def health(request: Request) -> HealthOut:
    assistant: Assistant | None = request.app.state.assistant
    return HealthOut(status="ok", chat_enabled=assistant is not None, model=assistant.model if assistant else None)


@router.get("/perimeters", response_model=list[PerimeterSummaryOut], tags=["paramétrage"])
def list_perimeters(request: Request) -> list[PerimeterSummaryOut]:
    return _service(request).perimeters()


@router.get("/perimeters/{code}", response_model=PerimeterDetailsOut, tags=["paramétrage"])
def get_perimeter(code: str, request: Request) -> PerimeterDetailsOut:
    return _service(request).perimeter_details(code)


@router.post("/simulate", response_model=CalculationOut, tags=["calcul"])
def simulate(body: SimulationRequest, request: Request) -> CalculationOut:
    return _service(request).simulate(body)


@router.get("/samples/{perimeter}/contracts/{contract_id}", response_model=SampleContractOut, tags=["calcul"])
def get_sample_contract(perimeter: str, contract_id: str, request: Request) -> SampleContractOut:
    return _service(request).sample_contract(perimeter, contract_id)


RATE_LIMIT_RESPONSE = {429: {"description": "Limite de débit de la démo atteinte (en-tête Retry-After) "
                                            "ou quota du fournisseur de modèle épuisé"}}


@router.post("/chat", response_model=ChatResponse, tags=["assistant"], responses=RATE_LIMIT_RESPONSE)
def chat(body: ChatRequest, request: Request) -> ChatResponse:
    return chat_response(_assistant(request).answer(body.messages))


@router.post("/chat/stream", tags=["assistant"], response_class=StreamingResponse,
             responses={200: {"content": {"text/event-stream": {}}, "description": STREAM_DESCRIPTION},
                        **RATE_LIMIT_RESPONSE})
def chat_stream(body: ChatRequest, request: Request) -> StreamingResponse:
    assistant = _assistant(request)
    return StreamingResponse(_stream_events(assistant, body), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _stream_events(assistant: Assistant, body: ChatRequest) -> Iterator[str]:
    try:
        for event in assistant.events(body.messages):
            match event:
                case TextDelta(text=text):
                    yield _sse("delta", {"text": text})
                case ToolStarted(name=name, arguments=arguments):
                    yield _sse("tool_call", {"name": name, "arguments": arguments})
                case ToolFinished(trace=trace):
                    yield _sse("tool_result", _trace_out(trace).model_dump(mode="json"))
                case Completed(answer=answer):
                    yield _sse("done", chat_response(answer).model_dump(mode="json"))
    except QuotaExceededError:
        yield _sse("error", {"status": 429, "detail": QUOTA_MESSAGE})
    except LLMError:
        yield _sse("error", {"status": 502, "detail": UNAVAILABLE_MESSAGE})


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _trace_out(trace: ToolTrace) -> ToolCallTrace:
    return ToolCallTrace(name=trace.name, arguments=trace.arguments, result=trace.result, ok=trace.ok)


def chat_response(answer: AssistantAnswer) -> ChatResponse:
    return ChatResponse(
        answer=answer.content,
        tool_calls=[_trace_out(trace) for trace in answer.tool_calls],
        citations=[CitationOut(**asdict(citation)) for citation in answer.citations],
        unverified_amounts=list(answer.unverified_amounts),
        unknown_rules=list(answer.unknown_rules),
        unknown_products=list(answer.unknown_products),
        model=answer.model,
    )
