"""Offline tests for the shared LangChain model factory (Module 2, U1)."""

from __future__ import annotations

from documind.config import settings
from documind.lc import chat_model


def test_chat_model_passes_injected_model_through() -> None:
    # The dependency-injection seam: a fake model is returned unchanged, so the
    # chain and agent tests can drive a scripted model without any network.
    sentinel = object()
    assert chat_model(model=sentinel) is sentinel


def test_chat_model_builds_from_settings(monkeypatch) -> None:
    # Constructing ChatAnthropic reads the key but makes no network call.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    model = chat_model()
    model_id = getattr(model, "model", None) or getattr(model, "model_name", None)
    assert model_id == settings.dev_model


def test_agent_max_steps_default_is_a_positive_int() -> None:
    assert isinstance(settings.agent_max_steps, int)
    assert settings.agent_max_steps > 0
