"""
Typed state for the Research Hub pipeline.

We deliberately do NOT use LangGraph's StateGraph (see docs/write-up.md, 3.1, for the
rationale). The Functional API (`@task` / `@entrypoint`) threads a single ResearchState
object through the pipeline by return value, so this module only needs to define the
shape of that object -- there is no shared mutable graph state to reduce over.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Optional
from uuid import uuid4


class SourceCredibility(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    REJECTED = "rejected"


class ReviewVerdict(str, Enum):
    APPROVE = "approve"
    REVISE = "revise"


@dataclass
class Source:
    url: str
    title: str
    snippet: str
    domain: str = ""
    fetched_text: Optional[str] = None
    credibility: Optional[SourceCredibility] = None
    credibility_reason: Optional[str] = None


@dataclass
class Claim:
    text: str
    supporting_source_urls: list[str] = field(default_factory=list)
    verified: Optional[bool] = None
    evidence_snippet: Optional[str] = None
    confidence: Optional[float] = None


@dataclass
class ReviewNote:
    verdict: ReviewVerdict
    reasons: list[str] = field(default_factory=list)
    requested_changes: list[str] = field(default_factory=list)


@dataclass
class ResearchState:
    """The single object threaded through every @task in pipeline.py."""

    thread_id: str
    query: str

    # Routing
    route_plan: list[str] = field(default_factory=list)
    needs_file_output: bool = False
    output_path: Optional[str] = None

    # Search
    sources: list[Source] = field(default_factory=list)

    # Source evaluation
    accepted_sources: list[Source] = field(default_factory=list)
    rejected_sources: list[Source] = field(default_factory=list)

    # Fact-checking / RAG
    claims: list[Claim] = field(default_factory=list)
    draft_report: str = ""

    # Review loop
    review_notes: list[ReviewNote] = field(default_factory=list)
    revision_count: int = 0
    max_revisions: int = 2

    # Human-in-the-loop
    awaiting_file_write_confirmation: bool = False
    awaiting_low_confidence_confirmation: bool = False
    human_confirmed: Optional[bool] = None

    # Output
    final_report: Optional[str] = None
    status: Literal["running", "interrupted", "done", "error"] = "running"
    demo_mode: bool = False

    trace: list[dict[str, Any]] = field(default_factory=list)

    def log(self, agent: str, event: str, **details: Any) -> None:
        self.trace.append({"agent": agent, "event": event, **details})


def new_thread_id() -> str:
    return str(uuid4())
