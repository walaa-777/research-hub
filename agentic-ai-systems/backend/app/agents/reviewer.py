"""
Reviewer worker: the human-facing quality gate. Approves the draft or sends it back
with concrete requested changes, bounded by state.max_revisions in pipeline.py.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.llm import get_llm
from app.state import ResearchState, ReviewNote, ReviewVerdict

REVIEWER_SYSTEM_PROMPT = """You are an editorial reviewer. Given a draft report and
its underlying claims (with verification status), decide APPROVE or REVISE. Revise
if: any unverified claim is stated as fact, sourcing is thin (fewer than 2 accepted
sources), or the report doesn't actually answer the query. List concrete requested
changes when revising."""


class ReviewResult(BaseModel):
    verdict: ReviewVerdict
    reasons: list[str] = Field(default_factory=list)
    requested_changes: list[str] = Field(default_factory=list)


def run_reviewer(state: ResearchState) -> ResearchState:
    claims_blob = "\n".join(
        f"- [{'verified' if c.verified else 'UNVERIFIED'}] {c.text}" for c in state.claims
    )
    prompt = (
        f"Query: {state.query}\nAccepted sources: {len(state.accepted_sources)}\n\n"
        f"Claims:\n{claims_blob}\n\nDraft report:\n{state.draft_report}"
    )
    result = get_llm().structured(REVIEWER_SYSTEM_PROMPT, prompt, ReviewResult)

    note = ReviewNote(
        verdict=result.verdict,
        reasons=result.reasons,
        requested_changes=result.requested_changes,
    )
    state.review_notes.append(note)

    if note.verdict == ReviewVerdict.REVISE:
        state.revision_count += 1

    state.log(
        "reviewer",
        "review_complete",
        verdict=note.verdict.value,
        revision_count=state.revision_count,
    )
    return state
