"""
Orchestration loop -- LangGraph Functional API only (`@task` / `@entrypoint`), never
`StateGraph`. See docs/write-up.md 3.1 for why: the control flow here is "ask a
router what's next, run it, repeat until done, pausing at two well-defined human
checkpoints" -- a plain loop with two interrupt() calls expresses that more directly
than building an explicit graph with conditional edges for the same two branches.

Track A shape: `decide_next()` in router.py is a dedicated supervisor that names the
next worker; workers never hand off to each other directly.
"""
from __future__ import annotations

import os

from langgraph.func import entrypoint, task
from langgraph.types import interrupt

from app.agents.fact_checker import run_fact_checker
from app.agents.reviewer import run_reviewer
from app.agents.search_agent import run_search
from app.agents.source_evaluator import run_source_evaluator
from app.llm import get_llm
from app.messages import AgentMessage
from app.reliability import source_evaluator_fallback, with_fallback, with_retry
from app.router import NextAgent, decide_next
from app.state import ResearchState
from app.tools.fs_tools import fs_exists, fs_write

# --- @task-wrapped workers -------------------------------------------------
# Each worker is retried on transient errors; the Source Evaluator additionally
# degrades gracefully instead of failing the whole run (see reliability.py).

search_task = task(with_retry(run_search))
source_evaluator_task = task(
    with_retry(with_fallback(run_source_evaluator, source_evaluator_fallback))
)
fact_checker_task = task(with_retry(run_fact_checker))
reviewer_task = task(with_retry(run_reviewer))


@task
def save_report_task(state: ResearchState) -> ResearchState:
    path = fs_write(state.output_path, state.final_report or state.draft_report)
    state.log("orchestrator", "file_saved", path=path)
    return state


WORKER_TASKS = {
    NextAgent.SEARCH: search_task,
    NextAgent.SOURCE_EVALUATOR: source_evaluator_task,
    NextAgent.FACT_CHECKER: fact_checker_task,
    NextAgent.REVIEWER: reviewer_task,
}

MAX_LOOP_STEPS = 25  # hard ceiling so a misbehaving router can never spin forever


def _detect_output_path(query: str) -> str | None:
    """Very small heuristic: 'save ... to reports/x.md' -> 'x.md'. Good enough for the
    three README requests; a real NL path-extraction pass would live here."""
    import re

    m = re.search(r"reports?/([\w\-./]+\.(?:md|txt))", query)
    return m.group(1) if m else None


@entrypoint()
def research_pipeline(payload: dict, *, previous: ResearchState | None = None) -> ResearchState:
    """
    payload: {"thread_id": str, "query": str} on first call, or
             {"thread_id": str, "resume": {"confirmed": bool}} to resume after interrupt().

    `previous` is the last checkpointed ResearchState for this thread, restored
    automatically by the SqliteSaver passed at invocation time (see server.py).
    """
    thread_id = payload["thread_id"]

    if previous is not None and "resume" in payload:
        state = previous
        state.human_confirmed = payload["resume"].get("confirmed", False)
        if state.awaiting_low_confidence_confirmation:
            state.awaiting_low_confidence_confirmation = False
            if not state.human_confirmed:
                state.status = "done"
                state.final_report = (
                    "Delivery cancelled: low-confidence claims were not confirmed by a human."
                )
                return state
        if state.awaiting_file_write_confirmation:
            state.awaiting_file_write_confirmation = False
            if state.human_confirmed:
                state = save_report_task(state).result()
    else:
        state = ResearchState(thread_id=thread_id, query=payload["query"])
        state.demo_mode = get_llm().demo
        state.output_path = _detect_output_path(payload["query"])
        state.needs_file_output = state.output_path is not None
        state.log("orchestrator", "pipeline_start", demo_mode=state.demo_mode)

    for _ in range(MAX_LOOP_STEPS):
        decision = decide_next(state)

        if decision.next_agent == NextAgent.DONE:
            state.final_report = state.draft_report

            # Gate 2 (example C): weak sourcing / low-confidence claims -> human must
            # confirm before the answer is delivered, even if the Reviewer approved it.
            if state.awaiting_low_confidence_confirmation:
                state.status = "interrupted"
                interrupt(
                    {
                        "type": "low_confidence_confirmation",
                        "message": (
                            "Some claims have low confidence. Deliver the report anyway?"
                        ),
                        "draft_report": state.final_report,
                        "claims": [c.__dict__ for c in state.claims],
                    }
                )

            # Gate 1 (example B vs. its variant): saving would overwrite an existing
            # file -> confirm first. A brand-new path (the README's example B) never
            # hits this gate at all.
            if state.needs_file_output and state.output_path:
                if fs_exists(state.output_path):
                    state.awaiting_file_write_confirmation = True
                    state.status = "interrupted"
                    interrupt(
                        {
                            "type": "overwrite_confirmation",
                            "message": f"'{state.output_path}' already exists. Overwrite?",
                        }
                    )
                else:
                    state = save_report_task(state).result()

            state.status = "done"
            return state

        worker = WORKER_TASKS[decision.next_agent]
        state = worker(state).result()

    state.status = "error"
    state.final_report = state.draft_report or "Pipeline exceeded its step budget."
    state.log("orchestrator", "step_budget_exceeded")
    return state


def state_to_transcript(state: ResearchState) -> list[AgentMessage]:
    """Renders state.trace as chat-friendly AgentMessages for the SSE stream."""
    messages = []
    for entry in state.trace:
        agent = entry.pop("agent") if "agent" in entry else "system"
        event = entry.get("event", "")
        messages.append(
            AgentMessage(
                role=agent,  # type: ignore[arg-type]
                content=f"{event}: {entry}",
                thread_id=state.thread_id,
                kind="status",
                metadata=entry,
            )
        )
    return messages
