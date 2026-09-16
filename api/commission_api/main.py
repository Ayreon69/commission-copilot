"""Point d'entrée de l'API.

    uvicorn commission_api.main:create_app --factory --reload
"""

from __future__ import annotations

from commission_engine import Catalog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from .assistant.agent import Assistant
from .assistant.llm import FallbackLLM, LLMClient, LLMError, OpenAICompatibleClient, QuotaExceededError
from .assistant.prompt import build_system_prompt
from .assistant.tools import Toolbox
from .config import Settings
from .ratelimit import RateLimitedError, RateLimiter
from .routes import QUOTA_MESSAGE, UNAVAILABLE_MESSAGE, router
from .services import CommissionService, InvalidRequestError, NotFoundError


def build_llm(settings: Settings) -> LLMClient | None:
    if not settings.llm_api_key:
        return None
    return FallbackLLM([
        OpenAICompatibleClient(base_url=settings.llm_base_url, api_key=settings.llm_api_key, model=model,
                               reasoning_effort=settings.llm_reasoning_effort)
        for model in settings.llm_models
    ])


def build_assistant(settings: Settings, llm: LLMClient, service: CommissionService) -> Assistant:
    knowledge = settings.knowledge_path.read_text(encoding="utf-8")
    prompt = build_system_prompt(service.catalog, knowledge, service.default_month())
    return Assistant(llm, Toolbox(service), prompt, knowledge, settings.max_tool_rounds)


def create_app(settings: Settings | None = None, llm: LLMClient | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    service = CommissionService(Catalog.load(settings.catalog_path), settings.samples_dir)
    llm = llm or build_llm(settings)
    assistant = build_assistant(settings, llm, service) if llm is not None else None

    app = FastAPI(
        title="Commission Copilot API",
        version="0.1.0",
        description="Moteur de calcul des commissions de courtage et assistant conversationnel. Données fictives.",
    )
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type"], expose_headers=["Retry-After"])
    app.state.service = service
    app.state.assistant = assistant
    app.state.rate_limiter = RateLimiter(settings.rate_limits)
    app.include_router(router)

    @app.get("/", include_in_schema=False)
    def _home() -> RedirectResponse:
        return RedirectResponse("/docs")

    @app.exception_handler(NotFoundError)
    async def _not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(InvalidRequestError)
    async def _invalid(_: Request, exc: InvalidRequestError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(RateLimitedError)
    async def _rate_limited(_: Request, exc: RateLimitedError) -> JSONResponse:
        return JSONResponse(status_code=429, content={"detail": str(exc)},
                            headers={"Retry-After": str(exc.retry_after)})

    @app.exception_handler(QuotaExceededError)
    async def _quota_exceeded(_: Request, exc: QuotaExceededError) -> JSONResponse:
        return JSONResponse(status_code=429, content={"detail": QUOTA_MESSAGE})

    @app.exception_handler(LLMError)
    async def _llm_unavailable(_: Request, exc: LLMError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": UNAVAILABLE_MESSAGE})

    return app
