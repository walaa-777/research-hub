"""
Retry + fallback wrapper applied around every worker @task in pipeline.py.

Two independent concerns, both real failure modes in this system:
  1. Transient errors (rate limits, flaky network fetch) -> retry with backoff.
  2. Sustained failure of a worker -> fall back to a safe degraded behavior instead
     of crashing the whole pipeline (e.g. Source Evaluator down -> treat sources as
     medium-credibility and let the Reviewer catch anything that slips through).
"""
from __future__ import annotations

import functools
import time
from typing import Callable, TypeVar

from app.state import ResearchState

T = TypeVar("T")

RETRYABLE_EXCEPTIONS = (ConnectionError, TimeoutError, OSError)


def with_retry(
    fn: Callable[[ResearchState], ResearchState],
    *,
    max_attempts: int = 3,
    backoff_seconds: float = 0.5,
) -> Callable[[ResearchState], ResearchState]:
    @functools.wraps(fn)
    def wrapper(state: ResearchState) -> ResearchState:
        last_exc: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                return fn(state)
            except RETRYABLE_EXCEPTIONS as exc:
                last_exc = exc
                state.log(fn.__name__, "retry", attempt=attempt, error=str(exc))
                time.sleep(backoff_seconds * attempt)
        assert last_exc is not None
        raise last_exc

    return wrapper


def with_fallback(
    fn: Callable[[ResearchState], ResearchState],
    fallback: Callable[[ResearchState, Exception], ResearchState],
) -> Callable[[ResearchState], ResearchState]:
    @functools.wraps(fn)
    def wrapper(state: ResearchState) -> ResearchState:
        try:
            return fn(state)
        except Exception as exc:  # noqa: BLE001 -- deliberately broad, this is the safety net
            state.log(fn.__name__, "fallback_triggered", error=str(exc))
            return fallback(state, exc)

    return wrapper


def source_evaluator_fallback(state: ResearchState, exc: Exception) -> ResearchState:
    """If the Source Evaluator worker keeps failing, don't drop the run -- degrade
    to 'accept everything as medium, unfetched' and let the Reviewer catch issues."""
    from app.state import SourceCredibility

    for source in state.sources:
        if source.url not in {s.url for s in state.accepted_sources + state.rejected_sources}:
            source.credibility = SourceCredibility.MEDIUM
            source.credibility_reason = f"Fallback: evaluator unavailable ({exc})"
            state.accepted_sources.append(source)
    return state
