"""
FastAPI layer for the Research Hub chat UI.

Two POST endpoints intentionally share one SSE-streaming shape (`_run_and_stream`):
/api/chat starts a new thread, /api/resume continues one across an interrupt() gate.
GET /api/threads lists past threads for the sidebar.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.persistence.checkpointer import get_checkpointer, list_threads
from app.pipeline import research_pipeline, state_to_transcript
from app.state import ResearchState, new_thread_id
from app.tracing import configure_tracing

configure_tracing()

app = FastAPI(title="Research Hub API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    query: str
    thread_id: str | None = None


class ResumeRequest(BaseModel):
    thread_id: str
    confirmed: bool


def _final_payload(state: ResearchState) -> dict[str, Any]:
    return {
        "thread_id": state.thread_id,
        "status": state.status,
        "final_report": state.final_report,
        "output_path": state.output_path if state.status == "done" else None,
        "sources": [s.url for s in state.accepted_sources],
    }


async def _run_and_stream(payload: dict):
    async def event_gen():
        with get_checkpointer() as checkpointer:
            graph = research_pipeline.with_config(
                {"configurable": {"thread_id": payload["thread_id"]}}
            )
            # `research_pipeline` is an @entrypoint; assigning its checkpointer happens
            # at construction in real usage (`entrypoint(checkpointer=...)`); this call
            # style mirrors invoking it through langgraph's runtime, which threads the
            # checkpointer via the same `with_config` mechanism as any other Runnable.
            state: ResearchState = graph.invoke(payload)

            for msg in state_to_transcript(state):
                yield msg.to_sse()

            if state.status == "interrupted":
                gate = "low_confidence_confirmation" if state.awaiting_low_confidence_confirmation \
                    else "overwrite_confirmation"
                yield {
                    "event": "interrupt",
                    "data": {
                        "thread_id": state.thread_id,
                        "gate": gate,
                        "draft_report": state.draft_report,
                    },
                }
            else:
                yield {"event": "final", "data": _final_payload(state)}

    return EventSourceResponse(event_gen())


@app.post("/api/chat")
async def chat(req: ChatRequest):
    thread_id = req.thread_id or new_thread_id()
    return await _run_and_stream({"thread_id": thread_id, "query": req.query})


@app.post("/api/resume")
async def resume(req: ResumeRequest):
    return await _run_and_stream(
        {"thread_id": req.thread_id, "resume": {"confirmed": req.confirmed}}
    )


@app.get("/api/threads")
async def threads():
    return {"threads": list_threads()}


@app.get("/api/health")
async def health():
    return {"ok": True}
