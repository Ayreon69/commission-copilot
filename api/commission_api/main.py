"""Point d'entrée de l'API.

    uvicorn commission_api.main:create_app --factory --reload
"""

from __future__ import annotations

from commission_engine import Catalog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .assistant.agent import Assistant
from .assistant.llm import FallbackLLM, LLMClient, LLMError, OpenAICompatibleClient, QuotaExceededError
from .assistant.prompt import build_system_prompt
from .assistant.tools import Toolbox
from .config import Settings
from .routes import router
from .services import CommissionService, InvalidRequestError, NotFoundError


def build_llm(settings: Settings) -> LLMClient | None:
    if not settings.llm_api_key:
        return None
    return FallbackLLM([
        OpenAICompatibleClient(base_url=settings.llm_base_url, api_key=settings.llm_api_key, model=model,
                               reasoning_effort=settings.llm_reasoning_effort)
        for model in settings.llm_models
    ])


def create_app(settings: Settings | None = None, llm: LLMClient | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    catalog = Catalog.load(settings.catalog_path)
    service = CommissionService(catalog, settings.samples_dir)
    knowledge = settings.knowledge_path.read_text(encoding="utf-8")

    llm = llm or build_llm(settings)
    assistant = None
    if llm is not None:
        prompt = build_system_prompt(catalog, knowledge, service.default_month())
        assistant = Assistant(llm, Toolbox(service), prompt, knowledge, settings.max_tool_rounds)

    app = FastAPI(
        title="Commission Copilot API",
        version="0.1.0",
        description="Moteur de calcul des commissions de courtage et assistant conversationnel. Données fictives.",
    )
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type"])
    app.state.service = service
    app.state.assistant = assistant
    app.include_router(router)

    @app.exception_handler(NotFoundError)
    async def _not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(InvalidRequestError)
    async def _invalid(_: Request, exc: InvalidRequestError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(QuotaExceededError)
    async def _quota_exceeded(_: Request, exc: QuotaExceededError) -> JSONResponse:
        return JSONResponse(status_code=429, content={
            "detail": "Le quota gratuit de la démonstration est atteint. Réessayez dans quelques minutes, "
                      "ou demain si le quota journalier est épuisé."
        })

    @app.exception_handler(LLMError)
    async def _llm_unavailable(_: Request, exc: LLMError) -> JSONResponse:
        return JSONResponse(status_code=502, content={
            "detail": "Le modèle de langage est momentanément indisponible. Réessayez dans quelques instants."
        })

    return app
