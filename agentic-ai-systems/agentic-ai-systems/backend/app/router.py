"""
Dedicated LLM router -- the "who decides next" piece that puts this project on
Track A (Supervisor + workers) rather than Track B (peer-to-peer handoffs).

`decide_next` is called once per pipeline turn by pipeline.py. It never executes
work itself; it only returns a RouteDecision naming the next worker (or "done").
If the structured call fails or returns something invalid, `_deterministic_fallback`
takes over so the pipeline never wedges on a malformed router response.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.llm import get_llm
from app.state import ResearchState

ROUTER_SYSTEM_PROMPT = """You are the Orchestrator of a research pipeline with four
worker agents: search, source_evaluator, fact_checker, reviewer. Given the current
research state, decide which worker should run next, or "done" if the report is
ready to deliver. Never do the worker's job yourself -- only route."""


class NextAgent(str, Enum):
    SEARCH = "search"
    SOURCE_EVALUATOR = "source_evaluator"
    FACT_CHECKER = "fact_checker"
    REVIEWER = "reviewer"
    DONE = "done"


class RouteDecision(BaseModel):
    next_agent: NextAgent
    reason: str = Field(description="One sentence explaining the routing choice")


def _summarize_state(state: ResearchState) -> str:
    return (
        f"query={state.query!r}\n"
        f"sources_found={len(state.sources)}\n"
        f"accepted_sources={len(state.accepted_sources)}\n"
        f"rejected_sources={len(state.rejected_sources)}\n"
        f"claims_checked={len(state.claims)}\n"
        f"has_draft={bool(state.draft_report)}\n"
        f"review_rounds={len(state.review_notes)}\n"
        f"revision_count={state.revision_count}/{state.max_revisions}\n"
        f"last_review_verdict="
        f"{state.review_notes[-1].verdict.value if state.review_notes else None}\n"
    )


def _deterministic_fallback(state: ResearchState) -> RouteDecision:
    """Rule-based router used both as a safety net and, in tests, for determinism."""
    if not state.sources:
        return RouteDecision(next_agent=NextAgent.SEARCH, reason="No sources gathered yet.")
    if not state.accepted_sources and not state.rejected_sources:
        return RouteDecision(
            next_agent=NextAgent.SOURCE_EVALUATOR, reason="Sources need credibility triage."
        )
    if not state.accepted_sources:
        return RouteDecision(
            next_agent=NextAgent.SEARCH,
            reason="All sources were rejected; need another search pass.",
        )
    if not state.draft_report:
        return RouteDecision(
            next_agent=NextAgent.FACT_CHECKER, reason="Need claims checked and a draft written."
        )
    if not state.review_notes or state.review_notes[-1].verdict.value == "revise":
        if state.revision_count >= state.max_revisions:
            return RouteDecision(
                next_agent=NextAgent.DONE, reason="Revision budget exhausted; deliver as-is."
            )
        return RouteDecision(next_agent=NextAgent.REVIEWER, reason="Draft needs review.")
    return RouteDecision(next_agent=NextAgent.DONE, reason="Reviewer approved the draft.")


def decide_next(state: ResearchState) -> RouteDecision:
    llm = get_llm()
    if llm.demo:
        # Keep demo mode's routing legible and correct rather than pseudo-random.
        decision = _deterministic_fallback(state)
    else:
        try:
            decision = llm.structured(
                ROUTER_SYSTEM_PROMPT, _summarize_state(state), RouteDecision
            )
        except Exception:
            decision = _deterministic_fallback(state)

    state.route_plan.append(decision.next_agent.value)
    state.log("orchestrator", "route", next_agent=decision.next_agent.value, reason=decision.reason)
    return decision
