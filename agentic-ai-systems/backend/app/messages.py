"""
AgentMessage: the common envelope every agent emits.

The chat UI, the SQLite checkpointer, and LangSmith tracing all consume the same
envelope shape, so an agent only has to know how to produce one kind of object.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal[
    "user",
    "orchestrator",
    "search",
    "source_evaluator",
    "fact_checker",
    "reviewer",
    "system",
]


@dataclass
class AgentMessage:
    role: Role
    content: str
    thread_id: str
    ts: float = field(default_factory=time.time)
    kind: Literal["status", "final", "interrupt", "error"] = "status"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "thread_id": self.thread_id,
            "ts": self.ts,
            "kind": self.kind,
            "metadata": self.metadata,
        }

    def to_sse(self) -> dict[str, str]:
        """Shape expected by the frontend's EventSource handler in src/api.ts."""
        import json

        return {"event": self.kind, "data": json.dumps(self.to_dict())}
