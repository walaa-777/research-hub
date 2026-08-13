import pytest

from app.reliability import source_evaluator_fallback, with_fallback, with_retry
from app.state import ResearchState, Source


def test_with_retry_eventually_succeeds():
    calls = {"n": 0}

    def flaky(state):
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("boom")
        return state

    wrapped = with_retry(flaky, backoff_seconds=0)
    state = ResearchState(thread_id="t", query="q")
    wrapped(state)
    assert calls["n"] == 3


def test_with_retry_gives_up_after_max_attempts():
    def always_fails(state):
        raise ConnectionError("boom")

    wrapped = with_retry(always_fails, max_attempts=2, backoff_seconds=0)
    with pytest.raises(ConnectionError):
        wrapped(ResearchState(thread_id="t", query="q"))


def test_fallback_degrades_instead_of_crashing():
    def broken_evaluator(state):
        raise RuntimeError("evaluator down")

    wrapped = with_fallback(broken_evaluator, source_evaluator_fallback)
    state = ResearchState(
        thread_id="t", query="q", sources=[Source(url="https://x.com", title="t", snippet="s")]
    )
    result = wrapped(state)
    assert len(result.accepted_sources) == 1
    assert result.accepted_sources[0].credibility.value == "medium"
