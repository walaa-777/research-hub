"""
Source Evaluator worker: judges credibility of every not-yet-evaluated Source and
sorts it into accepted_sources / rejected_sources. Combines a cheap offline domain
signal with an LLM (or DemoLLM) judgment of the snippet content itself.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.llm import get_llm
from app.state import ResearchState, Source, SourceCredibility
from app.tools.domain_lookup import domain_lookup
from app.tools.fetch_page import fetch_page

EVALUATOR_SYSTEM_PROMPT = """You evaluate the credibility of a web source for a
research report. Consider the domain signal provided, the title, and the snippet.
Rate it high, medium, low, or rejected, and give one sentence of reasoning."""


class CredibilityVerdict(BaseModel):
    credibility: SourceCredibility
    reason: str = Field(description="One sentence justification")


def _evaluate_one(source: Source) -> Source:
    domain_info = domain_lookup(source.url)
    source.domain = domain_info["domain"]

    prompt = (
        f"URL: {source.url}\nDomain signal: {domain_info['signal']}\n"
        f"Title: {source.title}\nSnippet: {source.snippet}"
    )
    verdict = get_llm().structured(EVALUATOR_SYSTEM_PROMPT, prompt, CredibilityVerdict)
    source.credibility = verdict.credibility
    source.credibility_reason = verdict.reason

    if verdict.credibility != SourceCredibility.REJECTED:
        source.fetched_text = fetch_page(source.url)
    return source


def run_source_evaluator(state: ResearchState) -> ResearchState:
    evaluated_urls = {s.url for s in state.accepted_sources + state.rejected_sources}
    for source in state.sources:
        if source.url in evaluated_urls:
            continue
        _evaluate_one(source)
        if source.credibility == SourceCredibility.REJECTED:
            state.rejected_sources.append(source)
        else:
            state.accepted_sources.append(source)

    state.log(
        "source_evaluator",
        "evaluation_complete",
        accepted=len(state.accepted_sources),
        rejected=len(state.rejected_sources),
    )
    return state
