import pytest

from commission_api import config
from commission_api.config import GEMINI_BASE_URL, Settings
from commission_api.main import build_llm

VARIABLES = ["LLM_API_KEY", "GEMINI_API_KEY", "LLM_BASE_URL", "LLM_MODELS", "LLM_REASONING_EFFORT", "CORS_ORIGINS"]


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", lambda *args, **kwargs: None)
    for name in VARIABLES:
        monkeypatch.delenv(name, raising=False)


def test_defaults_target_gemini_free_models():
    settings = Settings.from_env()
    assert settings.llm_api_key is None
    assert settings.llm_base_url == GEMINI_BASE_URL
    assert settings.llm_models == ("gemini-3.5-flash-lite", "gemini-3.7-flash")
    assert build_llm(settings) is None


def test_provider_can_be_changed_through_environment(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "cle")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("LLM_MODELS", " openai/gpt-oss-120b , qwen/qwen3.8-27b ,")
    monkeypatch.setenv("CORS_ORIGINS", "https://demo.example, http://localhost:3000")

    settings = Settings.from_env()

    assert settings.llm_models == ("openai/gpt-oss-120b", "qwen/qwen3.8-27b")
    assert settings.cors_origins == ("https://demo.example", "http://localhost:3000")
    assert build_llm(settings).models == ["openai/gpt-oss-120b", "qwen/qwen3.8-27b"]


def test_gemini_key_name_is_accepted(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "cle-gemini")
    assert Settings.from_env().llm_api_key == "cle-gemini"
