"""
Fact-Checker (RAG) worker: extracts checkable claims relevant to the query, retrieves
supporting evidence for each from the accepted-source index, marks each claim
verified/unverified, and drafts the report from only the verified claims.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.llm import get_llm
from app.rag.retrieval import build_index, retrieve_evidence
from app.state import Claim, ResearchState

CLAIM_EXTRACTION_SYSTEM_PROMPT = """Given a research query and a set of source
excerpts, extract 3-6 discrete, checkable factual claims that would belong in a
report answering the query. Return only the claim statements."""

VERIFY_SYSTEM_PROMPT = """Given a claim and retrieved evidence snippets, decide
whether the evidence supports the claim. Return verified=true only if the evidence
clearly supports it, and a confidence between 0 and 1."""

REPORT_SYSTEM_PROMPT = """Write a concise, well-cited research report answering the
query using ONLY the verified claims provided. Note explicitly if a claim could not
be verified rather than omitting the gap silently."""


class ExtractedClaims(BaseModel):
    claims: list[str] = Field(description="3-6 short, checkable factual statements")


class VerifyResult(BaseModel):
    verified: bool
    confidence: float
    evidence_snippet: str = Field(description="The strongest supporting snippet, or empty")


def run_fact_checker(state: ResearchState) -> ResearchState:
    llm = get_llm()
    index = build_index(state.accepted_sources)

    excerpt_blob = "\n".join(
        f"- {s.title}: {(s.fetched_text or s.snippet)[:300]}" for s in state.accepted_sources
    )
    extraction = llm.structured(
        CLAIM_EXTRACTION_SYSTEM_PROMPT,
        f"Query: {state.query}\n\nSource excerpts:\n{excerpt_blob}",
        ExtractedClaims,
    )

    claims: list[Claim] = []
    for claim_text in extraction.claims:
        evidence = retrieve_evidence(index, claim_text, k=3)
        evidence_blob = "\n".join(f"- {c.text}" for c, _ in evidence) or "(no evidence retrieved)"
        result = llm.structured(
            VERIFY_SYSTEM_PROMPT,
            f"Claim: {claim_text}\n\nRetrieved evidence:\n{evidence_blob}",
            VerifyResult,
        )
        claims.append(
            Claim(
                text=claim_text,
                supporting_source_urls=[c.source_url for c, _ in evidence],
                verified=result.verified,
                evidence_snippet=result.evidence_snippet or None,
                confidence=result.confidence,
            )
        )
    state.claims = claims

    verified_blob = "\n".join(
        f"- {c.text} (confidence={c.confidence:.2f})" for c in claims if c.verified
    ) or "(no claims could be verified)"
    unverified_blob = "\n".join(f"- {c.text}" for c in claims if not c.verified)

    draft = llm.complete(
        REPORT_SYSTEM_PROMPT,
        f"Query: {state.query}\n\nVerified claims:\n{verified_blob}\n\n"
        f"Unverified/rejected claims (mention as open questions):\n{unverified_blob}",
    )
    if llm.demo:
        draft = f"# {state.query}\n\n[DEMO MODE]\n\n{draft}\n\nVerified claims:\n{verified_blob}"
    state.draft_report = draft

    low_confidence = any(c.verified and (c.confidence or 0) < 0.5 for c in claims)
    if low_confidence:
        state.awaiting_low_confidence_confirmation = True

    state.log(
        "fact_checker",
        "draft_complete",
        claims=len(claims),
        verified=sum(1 for c in claims if c.verified),
        low_confidence=low_confidence,
    )
    return state
