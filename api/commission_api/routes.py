"""Routes HTTP de l'API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from .assistant.agent import Assistant
from .schemas import (
    CalculationOut,
    ChatRequest,
    ChatResponse,
    HealthOut,
    PerimeterDetailsOut,
    PerimeterSummaryOut,
    SampleContractOut,
    SimulationRequest,
    ToolCallTrace,
)
from .services import CommissionService

router = APIRouter(prefix="/api")


def _service(request: Request) -> CommissionService:
    return request.app.state.service


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


@router.post("/chat", response_model=ChatResponse, tags=["assistant"])
def chat(body: ChatRequest, request: Request) -> ChatResponse:
    assistant: Assistant | None = request.app.state.assistant
    if assistant is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "Assistant indisponible : la variable MISTRAL_API_KEY n'est pas configurée.")
    answer = assistant.answer(body.messages)
    return ChatResponse(
        answer=answer.content,
        tool_calls=[ToolCallTrace(name=t.name, arguments=t.arguments, result=t.result, ok=t.ok)
                    for t in answer.tool_calls],
        unverified_amounts=list(answer.unverified_amounts),
        model=assistant.model,
    )
