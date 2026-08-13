"""
Single place that knows how to call "the model" -- real or synthetic.

Every agent and the router call `get_llm()` and then `.structured(...)` or `.complete(...)`.
Neither agents nor the router branch on whether a key is set; DemoLLM and ClaudeLLM
implement the same tiny protocol, so the exact same pipeline code runs in both modes.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from typing import Protocol, Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

MODEL_NAME = "claude-sonnet-4-6"


class LLM(Protocol):
    demo: bool

    def complete(self, system: str, prompt: str) -> str: ...

    def structured(self, system: str, prompt: str, schema: Type[T]) -> T: ...


@dataclass
class ClaudeLLM:
    """Thin wrapper over the Anthropic Messages API."""

    demo: bool = False

    def _client(self):
        import anthropic

        return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    def complete(self, system: str, prompt: str) -> str:
        resp = self._client().messages.create(
            model=MODEL_NAME,
            max_tokens=2000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in resp.content if b.type == "text")

    def structured(self, system: str, prompt: str, schema: Type[T]) -> T:
        schema_prompt = (
            f"{prompt}\n\nRespond with ONLY a single JSON object matching this schema, "
            f"no prose, no markdown fences:\n{schema.model_json_schema()}"
        )
        raw = self.complete(system, schema_prompt)
        cleaned = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        return schema.model_validate(json.loads(cleaned))


class DemoLLM:
    """
    Deterministic, keyless stand-in for Claude.

    Deterministic (hash-seeded) rather than random so that `pytest` and the demo
    notebook get reproducible output without needing an API key or network access.
    Every piece of text it emits is prefixed/labeled so it's unmistakably synthetic.
    """

    demo: bool = True

    @staticmethod
    def _seed(*parts: str) -> int:
        h = hashlib.sha256("||".join(parts).encode()).hexdigest()
        return int(h[:8], 16)

    def complete(self, system: str, prompt: str) -> str:
        seed = self._seed(system, prompt)
        return (
            f"[DEMO MODE] synthetic response (seed={seed % 10_000}) for prompt "
            f"starting: {prompt[:80]!r}"
        )

    def structured(self, system: str, prompt: str, schema: Type[T]) -> T:
        """
        Fills required fields of `schema` with deterministic synthetic values instead
        of calling an LLM. Agents pass the *actual* schema they need (RouteDecision,
        CredibilityVerdict, FactCheckResult, ReviewResult, ...), so this stays generic.
        """
        seed = self._seed(prompt, schema.__name__)
        values: dict = {}
        for field_name, field_info in schema.model_fields.items():
            values[field_name] = _demo_value_for(field_name, field_info, seed)
        return schema.model_validate(values)


def _demo_value_for(name: str, field_info, seed: int):
    ann = str(field_info.annotation)
    if "bool" in ann:
        return (seed + sum(map(ord, name))) % 2 == 0
    if "float" in ann:
        return round(0.55 + (seed % 40) / 100, 2)
    if "int" in ann:
        return seed % 5
    if "list" in ann:
        return []
    if hasattr(field_info.annotation, "__members__"):  # Enum
        members = list(field_info.annotation.__members__.values())
        return members[seed % len(members)]
    return f"[DEMO MODE] synthetic {name} (seed={seed % 10_000})"


def get_llm() -> LLM:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return ClaudeLLM()
    return DemoLLM()
