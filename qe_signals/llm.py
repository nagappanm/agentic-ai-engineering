"""Thin Anthropic adapter with prompt-steered structured output — the yilsf pattern.

* text in, text out; the client is injectable so tests never touch the network
* `structured()` appends a strict JSON directive, tolerantly extracts the first
  balanced JSON value from the reply, then validates with pydantic
* NO JSON schema is ever sent to the API (avoids the strict-schema rejections
  seen with anyOf/discriminator), and invalid output is a *reported* signal
  (`Parsed.valid == False`), never a crash and never a silent fallback
* every call is appended to `self.trace` with stage, prompt sha, validity, ms
"""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Generic, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from qe_signals.models import sha256_text

DEFAULT_MODEL = os.getenv("QE_SIGNALS_MODEL", "claude-sonnet-5")
DEFAULT_MAX_TOKENS = int(os.getenv("QE_SIGNALS_MAX_TOKENS", "2048"))

T = TypeVar("T", bound=BaseModel)


class SupportsMessages(Protocol):
    @property
    def messages(self) -> Any: ...


@dataclass
class Parsed(Generic[T]):  # Generic[] not PEP 695: CI runs 3.11
    valid: bool
    data: T | None
    errors: list[str]
    raw: str


@dataclass
class TraceEntry:
    stage: str
    model: str
    prompt_sha: str
    ms: int
    valid: bool | None
    errors: list[str] = field(default_factory=list)
    raw: str = ""
    prompt: str = ""


class BudgetExceeded(RuntimeError):
    """The run-level LLM call budget is exhausted."""


class CallBudget:
    def __init__(self, max_calls: int):
        self.max_calls = max_calls
        self.used = 0

    @property
    def remaining(self) -> int:
        return max(0, self.max_calls - self.used)

    def take(self) -> None:
        if self.used >= self.max_calls:
            raise BudgetExceeded(f"LLM call budget of {self.max_calls} exhausted")
        self.used += 1


JSON_DIRECTIVE = (
    "\n\nOutput ONLY a single JSON value matching this shape — no prose, no markdown fences, "
    "no comments, no trailing text:\n{shape}"
)


def shape_of(model: type[BaseModel]) -> str:
    """A compact, human-readable field list (not a JSON schema) for the directive."""
    parts = []
    for name, f in model.model_fields.items():
        ann = getattr(f.annotation, "__name__", None) or str(f.annotation).replace("typing.", "")
        parts.append(f'  "{name}": <{ann}>')
    return "{\n" + ",\n".join(parts) + "\n}"


def extract_json(text: str) -> str | None:
    """Return the first balanced JSON object/array in `text`, tolerating fences and prose."""
    if not text:
        return None
    t = re.sub(r"```(?:json)?", "", text)
    starts = [i for i, ch in enumerate(t) if ch in "{["]
    for start in starts:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(t)):
            ch = t[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch in "{[":
                depth += 1
            elif ch in "}]":
                depth -= 1
                if depth == 0:
                    candidate = t[start : i + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except ValueError:
                        break
    return None


class LLM:
    def __init__(
        self,
        client: SupportsMessages | None = None,
        *,
        model: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        budget: CallBudget | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client  # built lazily so constructing without a key never raises
        self.model = model or DEFAULT_MODEL
        self.max_tokens = max_tokens
        self.budget = budget
        self.trace: list[TraceEntry] = []
        self._clock = clock

    @property
    def client(self) -> SupportsMessages:
        if self._client is None:
            from anthropic import Anthropic

            self._client = Anthropic()
        return self._client

    def complete(self, system: str, user: str, *, stage: str = "complete") -> str:
        if self.budget is not None:
            self.budget.take()
        t0 = self._clock()
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=0,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in response.content if getattr(b, "type", "") == "text")
        self.trace.append(
            TraceEntry(
                stage=stage,
                model=self.model,
                prompt_sha=sha256_text(system + "\n" + user)[:16],
                ms=int((self._clock() - t0) * 1000),
                valid=None,
                raw=text,
                prompt=user,
            )
        )
        return text

    def structured(self, system: str, user: str, model: type[T], *, stage: str) -> Parsed[T]:
        user_full = user + JSON_DIRECTIVE.format(shape=shape_of(model))
        raw = self.complete(system, user_full, stage=stage)
        entry = self.trace[-1]
        candidate = extract_json(raw)
        if candidate is None:
            entry.valid = False
            entry.errors = ["no JSON value found in response"]
            return Parsed(False, None, entry.errors, raw)
        try:
            data = model.model_validate(json.loads(candidate))
        except ValidationError as e:
            entry.valid = False
            entry.errors = [
                f"{'.'.join(str(x) for x in err.get('loc', ()))}: {err.get('msg')}"
                for err in e.errors()
            ]
            return Parsed(False, None, entry.errors, raw)
        entry.valid = True
        return Parsed(True, data, [], raw)

    def trace_dump(self) -> list[dict]:
        return [
            {
                "stage": t.stage,
                "model": t.model,
                "prompt_sha": t.prompt_sha,
                "ms": t.ms,
                "valid": t.valid,
                "errors": t.errors,
                "raw": t.raw,
                "prompt": t.prompt,
            }
            for t in self.trace
        ]
