from app.router import NextAgent, decide_next
from app.state import ReviewNote, ReviewVerdict, ResearchState, Source, SourceCredibility


def _state(**overrides) -> ResearchState:
    base = ResearchState(thread_id="t1", query="test query")
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


def test_routes_to_search_when_no_sources():
    decision = decide_next(_state())
    assert decision.next_agent == NextAgent.SEARCH


def test_routes_to_evaluator_after_search():
    state = _state(sources=[Source(url="https://x.com", title="t", snippet="s")])
    decision = decide_next(state)
    assert decision.next_agent == NextAgent.SOURCE_EVALUATOR


def test_routes_back_to_search_if_everything_rejected():
    src = Source(url="https://x.com", title="t", snippet="s", credibility=SourceCredibility.REJECTED)
    state = _state(sources=[src], rejected_sources=[src])
    decision = decide_next(state)
    assert decision.next_agent == NextAgent.SEARCH


def test_routes_to_fact_checker_once_sources_accepted():
    src = Source(url="https://x.com", title="t", snippet="s")
    state = _state(sources=[src], accepted_sources=[src])
    decision = decide_next(state)
    assert decision.next_agent == NextAgent.FACT_CHECKER


def test_routes_to_reviewer_after_draft():
    src = Source(url="https://x.com", title="t", snippet="s")
    state = _state(sources=[src], accepted_sources=[src], draft_report="draft")
    decision = decide_next(state)
    assert decision.next_agent == NextAgent.REVIEWER


def test_done_after_reviewer_approves():
    src = Source(url="https://x.com", title="t", snippet="s")
    state = _state(
        sources=[src],
        accepted_sources=[src],
        draft_report="draft",
        review_notes=[ReviewNote(verdict=ReviewVerdict.APPROVE)],
    )
    decision = decide_next(state)
    assert decision.next_agent == NextAgent.DONE


def test_revision_budget_forces_done():
    src = Source(url="https://x.com", title="t", snippet="s")
    state = _state(
        sources=[src],
        accepted_sources=[src],
        draft_report="draft",
        review_notes=[ReviewNote(verdict=ReviewVerdict.REVISE)],
        revision_count=2,
        max_revisions=2,
    )
    decision = decide_next(state)
    assert decision.next_agent == NextAgent.DONE
