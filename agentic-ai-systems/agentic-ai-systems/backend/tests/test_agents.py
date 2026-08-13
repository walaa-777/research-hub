from app import llm as llm_module
from app.agents.reviewer import run_reviewer
from app.agents.source_evaluator import run_source_evaluator
from app.state import ResearchState, Source
from tests.fixtures import FakeStructuredLLM


def test_source_evaluator_sorts_by_credibility(monkeypatch):
    fake = FakeStructuredLLM(
        {
            "CredibilityVerdict": [
                {"credibility": "high", "reason": "peer reviewed"},
                {"credibility": "rejected", "reason": "no citations, opinion blog"},
            ]
        }
    )
    monkeypatch.setattr(llm_module, "get_llm", lambda: fake)

    state = ResearchState(
        thread_id="t1",
        query="q",
        sources=[
            Source(url="https://nature.com/a", title="A", snippet="s"),
            Source(url="https://blog.blogspot.com/b", title="B", snippet="s"),
        ],
    )
    result = run_source_evaluator(state)
    assert len(result.accepted_sources) == 1
    assert len(result.rejected_sources) == 1
    assert result.accepted_sources[0].url == "https://nature.com/a"


def test_reviewer_increments_revision_count_on_revise(monkeypatch):
    fake = FakeStructuredLLM(
        {"ReviewResult": [{"verdict": "revise", "reasons": ["thin sourcing"], "requested_changes": ["add a source"]}]}
    )
    monkeypatch.setattr(llm_module, "get_llm", lambda: fake)

    state = ResearchState(thread_id="t1", query="q", draft_report="draft")
    result = run_reviewer(state)
    assert result.revision_count == 1
    assert result.review_notes[-1].verdict.value == "revise"
