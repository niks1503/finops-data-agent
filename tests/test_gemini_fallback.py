"""The Gemini session should fall back to the next model when one is overloaded (503)."""
from types import SimpleNamespace

import pytest
from google.genai import errors

from finops_agent.llm import GeminiSession


class FakeModels:
    def __init__(self, failing: set[str], code: int = 503):
        self.failing, self.code, self.calls = failing, code, []

    def generate_content(self, model, contents, config):
        self.calls.append(model)
        if model in self.failing:
            raise errors.ServerError(self.code, {"error": {"code": self.code, "message": "overloaded", "status": "UNAVAILABLE"}})
        part = SimpleNamespace(function_call=None, text="ok", thought=False)
        return SimpleNamespace(
            usage_metadata=SimpleNamespace(prompt_token_count=5, candidates_token_count=1),
            candidates=[SimpleNamespace(content=SimpleNamespace(parts=[part]))],
        )


def _session(models, fake):
    GeminiSession.RETRIES_PER_MODEL = 1  # keep the test fast (no sleeps)
    return GeminiSession(SimpleNamespace(models=fake), models, "system", [])


def test_falls_back_to_next_model_on_503():
    fake = FakeModels(failing={"primary"})
    turn = _session(["primary", "backup"], fake).send_user("hi")
    assert turn.text == "ok" and turn.model == "backup"
    assert fake.calls == ["primary", "backup"]


def test_raises_clear_error_when_all_models_down():
    fake = FakeModels(failing={"a", "b"})
    with pytest.raises(RuntimeError, match="All Gemini models are unavailable"):
        _session(["a", "b"], fake).send_user("hi")


def test_non_transient_errors_are_not_retried():
    fake = FakeModels(failing={"a"}, code=400)
    with pytest.raises(errors.APIError):
        _session(["a", "b"], fake).send_user("hi")
    assert fake.calls == ["a"]
