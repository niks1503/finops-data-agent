"""LLM adapters. The agent talks to a small interface, so providers (or a fake for tests) are swappable."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]


@dataclass
class LLMTurn:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""  # which model actually produced this turn (can differ after a fallback)


class LLMSession(Protocol):
    def send_user(self, text: str) -> LLMTurn: ...
    def send_tool_results(self, results: list[tuple[ToolCall, dict[str, Any]]]) -> LLMTurn: ...


class LLMClient(Protocol):
    model: str
    def new_session(self, system: str, tools: list[dict[str, Any]]) -> LLMSession: ...


class GeminiClient:
    """Google Gemini via the google-genai SDK: manual function calling, per-call timeout,
    retries on rate limits / overload, and fallback to other models when one is unavailable."""

    def __init__(self, api_key: str | None, model: str, fallbacks: list[str] | None = None, timeout_s: float = 60):
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set. Add it to .env (see .env.example).")
        from google import genai
        from google.genai import types

        self._client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=int(timeout_s * 1000)))
        self.model = model
        self.models = [model] + [m for m in (fallbacks or []) if m and m != model]

    def new_session(self, system: str, tools: list[dict[str, Any]]) -> GeminiSession:
        return GeminiSession(self._client, self.models, system, tools)


class GeminiSession:
    RETRIES_PER_MODEL = 2
    TRANSIENT_CODES = (429, 500, 503, 504)

    def __init__(self, client: Any, models: list[str], system: str, tools: list[dict[str, Any]]):
        from google.genai import types

        self._types = types
        self._client = client
        self._models = list(models)  # first entry is the current model; failures move to the next
        self._contents: list[Any] = []
        self._config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0,
            tools=[types.Tool(function_declarations=[types.FunctionDeclaration(**t) for t in tools])],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

    def send_user(self, text: str) -> LLMTurn:
        t = self._types
        self._contents.append(t.Content(role="user", parts=[t.Part.from_text(text=text)]))
        return self._generate()

    def send_tool_results(self, results: list[tuple[ToolCall, dict[str, Any]]]) -> LLMTurn:
        t = self._types
        parts = [t.Part.from_function_response(name=call.name, response=result) for call, result in results]
        self._contents.append(t.Content(role="user", parts=parts))
        return self._generate()

    def _generate(self) -> LLMTurn:
        resp, model = self._call_with_fallback()
        usage = resp.usage_metadata
        turn = LLMTurn(
            input_tokens=(usage.prompt_token_count or 0) if usage else 0,
            output_tokens=(usage.candidates_token_count or 0) if usage else 0,
            model=model,
        )
        content = resp.candidates[0].content if resp.candidates else None
        if content is None or not content.parts:
            return turn
        self._contents.append(content)
        for part in content.parts:
            if part.function_call:
                turn.tool_calls.append(ToolCall(part.function_call.name, dict(part.function_call.args or {})))
            elif part.text and not getattr(part, "thought", False):
                turn.text += part.text
        return turn


    def _call_with_fallback(self) -> tuple[Any, str]:
        from google.genai import errors

        last_exc: Exception | None = None
        while self._models:
            model = self._models[0]
            for attempt in range(self.RETRIES_PER_MODEL):
                try:
                    resp = self._client.models.generate_content(
                        model=model, contents=self._contents, config=self._config
                    )
                    return resp, model
                except errors.APIError as exc:
                    if exc.code not in self.TRANSIENT_CODES:
                        raise
                    last_exc = exc
                except Exception as exc:  # network timeouts (the HTTP library varies by SDK version)
                    if "timeout" not in type(exc).__name__.lower():
                        raise
                    last_exc = exc
                if attempt < self.RETRIES_PER_MODEL - 1:
                    time.sleep(3 * (attempt + 1))
            self._models.pop(0)  # this model is overloaded or timing out: fall back to the next one
        raise RuntimeError(f"All Gemini models are unavailable right now ({type(last_exc).__name__}: {last_exc})")


class ScriptedLLM:
    """Deterministic fake used in tests: replays a fixed list of turns."""

    model = "scripted-fake"

    def __init__(self, turns: list[LLMTurn]):
        self._turns = list(turns)
        self.received: list[Any] = []

    def new_session(self, system: str, tools: list[dict[str, Any]]) -> ScriptedLLM:
        self.received.append(("system", system))
        return self

    def send_user(self, text: str) -> LLMTurn:
        self.received.append(("user", text))
        return self._turns.pop(0)

    def send_tool_results(self, results: list[tuple[ToolCall, dict[str, Any]]]) -> LLMTurn:
        self.received.append(("tool_results", results))
        return self._turns.pop(0)
