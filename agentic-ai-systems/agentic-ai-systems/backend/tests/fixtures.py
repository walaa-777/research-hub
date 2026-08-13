"""Canned, deterministic test doubles -- no network, no API keys required."""
from __future__ import annotations

from typing import Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

CANNED_SOURCES = [
    {"url": "https://nature.com/articles/example-1", "title": "Primary study A", "snippet": "Peer-reviewed findings on the topic."},
    {"url": "https://randomblog.blogspot.com/post-1", "title": "Some blog take", "snippet": "An opinion piece with no citations."},
    {"url": "https://reuters.com/article/example-2", "title": "News wire coverage", "snippet": "Wire report summarizing the same findings."},
]


class FakeStructuredLLM:
    """
    Returns pre-scripted structured outputs keyed by schema name, so each test can
    control exactly what the router/evaluator/fact-checker/reviewer "decide" without
    any network call. `.demo` is False so router.py takes the LLM branch, exercising
    the same code path production traffic uses (with a scripted LLM instead of a
    synthetic one).
    """

    demo = False

    def __init__(self, script: dict[str, list[dict]]):
        # script: {SchemaName: [dict, dict, ...]} consumed in order, repeating the last
        self._script = {k: list(v) for k, v in script.items()}
        self._calls: dict[str, int] = {}

    def complete(self, system: str, prompt: str) -> str:
        return "FAKE_COMPLETION"

    def structured(self, system: str, prompt: str, schema: Type[T]) -> T:
        name = schema.__name__
        queue = self._script.get(name)
        if not queue:
            raise AssertionError(f"FakeStructuredLLM has no scripted response for {name}")
        idx = min(self._calls.get(name, 0), len(queue) - 1)
        self._calls[name] = self._calls.get(name, 0) + 1
        return schema.model_validate(queue[idx])
