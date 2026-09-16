from dataclasses import replace

import pytest
from conftest import FakeLLM
from fastapi.testclient import TestClient

from commission_api.assistant.llm import LLMReply
from commission_api.config import Settings
from commission_api.main import create_app
from commission_api.ratelimit import (
    DAY,
    GLOBAL_DAY_MESSAGE,
    VISITOR_DAY_MESSAGE,
    VISITOR_MINUTE_MESSAGE,
    RateLimitedError,
    RateLimiter,
    RateLimits,
)

QUESTION = {"messages": [{"role": "user", "content": "Qu'est-ce qu'un précompte ?"}]}


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_per_minute_limit_blocks_then_releases():
    clock = Clock()
    limiter = RateLimiter(RateLimits(per_minute=2, per_day=0, global_per_day=0), clock)
    limiter.acquire("a")
    clock.now += 10
    limiter.acquire("a")
    with pytest.raises(RateLimitedError) as exc:
        limiter.acquire("a")
    assert str(exc.value) == VISITOR_MINUTE_MESSAGE
    assert exc.value.retry_after == 50
    limiter.acquire("b")  # un autre visiteur n'est pas concerné
    clock.now += 51
    limiter.acquire("a")


def test_per_day_limit_is_per_visitor():
    clock = Clock()
    limiter = RateLimiter(RateLimits(per_minute=0, per_day=2, global_per_day=0), clock)
    limiter.acquire("a")
    clock.now += 3600
    limiter.acquire("a")
    with pytest.raises(RateLimitedError) as exc:
        limiter.acquire("a")
    assert str(exc.value) == VISITOR_DAY_MESSAGE
    assert exc.value.retry_after == DAY - 3600
    limiter.acquire("b")


def test_global_limit_counts_all_visitors_and_forgets_after_a_day():
    clock = Clock()
    limiter = RateLimiter(RateLimits(per_minute=0, per_day=0, global_per_day=2), clock)
    limiter.acquire("a")
    limiter.acquire("b")
    with pytest.raises(RateLimitedError) as exc:
        limiter.acquire("c")
    assert str(exc.value) == GLOBAL_DAY_MESSAGE
    clock.now += DAY + 1
    limiter.acquire("c")
    assert set(limiter._visitors) == {"c"}


def test_refused_question_is_not_counted():
    clock = Clock()
    limiter = RateLimiter(RateLimits(per_minute=1, per_day=2, global_per_day=0), clock)
    limiter.acquire("a")
    for _ in range(3):
        with pytest.raises(RateLimitedError):
            limiter.acquire("a")
    clock.now += 61
    limiter.acquire("a")


def test_zero_disables_limits():
    limiter = RateLimiter(RateLimits(0, 0, 0))
    for _ in range(100):
        limiter.acquire("a")


def test_chat_routes_answer_429_with_retry_after():
    settings = replace(Settings(), rate_limits=RateLimits(per_minute=1, per_day=0, global_per_day=0))
    client = TestClient(create_app(settings, llm=FakeLLM(LLMReply("Un précompte est versé d'avance."),
                                                         repeat_last=True)))
    assert client.post("/api/chat", json=QUESTION).status_code == 200
    for path in ("/api/chat", "/api/chat/stream"):
        response = client.post(path, json=QUESTION)
        assert response.status_code == 429
        assert response.json()["detail"] == VISITOR_MINUTE_MESSAGE
        assert 1 <= int(response.headers["Retry-After"]) <= 60
    assert client.post("/api/simulate", json={}).status_code == 422  # le simulateur n'est pas limité


def test_invalid_request_does_not_consume_quota():
    settings = replace(Settings(), rate_limits=RateLimits(per_minute=1, per_day=0, global_per_day=0))
    client = TestClient(create_app(settings, llm=FakeLLM(LLMReply("Réponse."), repeat_last=True)))
    assert client.post("/api/chat", json={"messages": []}).status_code == 422
    assert client.post("/api/chat", json=QUESTION).status_code == 200


def test_limits_read_from_environment(monkeypatch):
    monkeypatch.setenv("CHAT_LIMIT_PER_MINUTE", "3")
    monkeypatch.setenv("CHAT_LIMIT_PER_DAY", "0")
    monkeypatch.delenv("CHAT_LIMIT_GLOBAL_PER_DAY", raising=False)
    assert Settings.from_env().rate_limits == RateLimits(per_minute=3, per_day=0,
                                                          global_per_day=RateLimits().global_per_day)
