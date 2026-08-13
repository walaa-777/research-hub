# Research Hub — Design Write-Up

**Team:** Leen, Lamya, Ghalia, Walaa
**Programme:** Building Agentic AI Systems — Aug 9–13, 2026
**Track:** A — Supervisor + workers

## 1. Problem and scope

Given a research question, produce a report whose claims are traceable to sources that
were actually judged credible and actually checked against retrieved evidence — not a
single LLM call improvising citations. Three request shapes drive the design (see the
table in `README.md`): a quick chat-only answer, a full pipeline ending in a saved
file, and a pipeline that hits weak sourcing and needs a human decision mid-run.

## 2. Agent roles

| Agent | Job | Does NOT do |
|---|---|---|
| Orchestrator (`router.py`) | Decide the next worker from current `ResearchState` | Any research work itself |
| Search (`agents/search_agent.py`) | Query the web, populate `state.sources` | Judge credibility |
| Source Evaluator (`agents/source_evaluator.py`) | Domain signal + LLM judgment → accept/reject each source, fetch accepted pages | Fact-check claims |
| Fact-Checker/RAG (`agents/fact_checker.py`) | Extract claims, retrieve evidence via local TF-IDF, verify, draft report | Approve/reject the draft |
| Reviewer (`agents/reviewer.py`) | Approve or request revisions, bounded by `max_revisions` | Rewrite the draft itself |

## 3. Architecture decisions

### 3.1 Functional API, not `StateGraph`

The control flow is "ask a dedicated router what's next, run it, repeat until done,
pausing at two human checkpoints." That's a loop with two `interrupt()` calls, not a
graph with many conditional edges — `@task`/`@entrypoint` expresses it directly and
keeps `pipeline.py` readable as a single function. `StateGraph` earns its complexity
when the topology itself is the interesting part (many nodes, branching edges,
cycles as first-class graph structure); here the topology is trivial and re-decided
every step by the LLM router, so a graph would just be a loop wearing a costume.

### 3.2 Track A: dedicated router vs. peer handoffs

`router.py` is a single LLM-structured-output call that names the next worker;
workers never talk to each other or decide what runs next themselves. This is the
canonical Track A ("who decides next" = a dedicated supervisor) shape from the
capstone-prep material, as opposed to Track B's peer-to-peer handoff pattern.

### 3.3 Local TF-IDF instead of an embeddings API

RAG needs vector similarity, not necessarily *learned* embeddings. Scikit-learn's
TF-IDF + cosine similarity gives real semantic-ish retrieval over the fetched source
chunks with zero external calls, zero API keys, and full determinism for tests and
demo mode — at the cost of missing true semantic matches that TF-IDF's bag-of-words
model can't see (synonyms, paraphrase). That trade favors this project: sources are
short-lived (rebuilt per thread), and the offline/keyless requirement was a hard
constraint from day one.

### 3.4 In-process tool calls vs. going through the MCP servers

`app/mcp_servers/*.py` exist so the same tools are usable by *any* MCP client. The
pipeline itself calls `app/tools/*.py` directly rather than spawning/talking to those
servers over stdio, because the pipeline is the hot path and a subprocess+stdio round
trip per search/fetch call would add latency with no benefit — nothing about running
in-process changes the tool's behavior or its interface.

### 3.5 Source credibility: cheap offline signal + LLM judgment, not a paid API

`domain_lookup.py` gives a fast, free, offline signal (TLD + known-domain lists) that
narrows what the LLM judgment call in `source_evaluator.py` has to reason about. A
paid credibility-scoring API would be more accurate but reintroduces the "requires a
key to run at all" problem this project avoids everywhere else.

## 4. Human-in-the-loop gates

1. **Overwrite confirmation** (`pipeline.py`, gate 1) — fires only when
   `state.output_path` already exists on disk. A new path (README request B) never
   interrupts. Resumed via `POST /api/resume`.
2. **Low-confidence confirmation** (`pipeline.py`, gate 2) — fires when any verified
   claim's confidence is below 0.5 (README request C: weak sourcing on a
   fast-changing claim). The Reviewer can still separately request revisions; this
   gate is about the human accepting residual uncertainty even in an *approved*
   draft, which is a different judgment call than the Reviewer's approve/revise.

## 5. Reliability

`reliability.py` separates two failure modes: transient (`with_retry`, backoff) and
sustained (`with_fallback`, degrade-not-crash). Only the Source Evaluator gets a
fallback today — accept everything as `medium` credibility and let the Reviewer's
sourcing check catch anything that shouldn't have gotten through — because it's the
one worker whose total failure has an obviously-safe degraded behavior; Search,
Fact-Checker, and Reviewer failing sustained-ly means the pipeline genuinely can't
proceed, so they only retry.

## 6. What demo mode proves and doesn't

`DemoLLM` and the keyless search/fetch fallbacks run the *identical* pipeline code
path as the real one — same router, same agents, same interrupt gates — with
synthetic, `[DEMO MODE]`-labeled content standing in for the model and the web. It
proves the orchestration, the two HITL gates, and the revision loop all work; it does
NOT prove the real Source Evaluator's or Fact-Checker's *judgment quality* — that
needs `ANTHROPIC_API_KEY` set and is out of scope for automated tests, which instead
use `FakeStructuredLLM` (scripted, not synthetic) to pin down each agent's *logic*
independent of any model's actual judgment.

## 7. Trace finding (see `notebook/demo.ipynb`)

`tracing.py::find_trace_insight` walks `state.trace` after a run and reports whichever
of {fallback triggered, retries needed, revision rounds needed} actually happened,
falling back to "clean first-pass run" — this is the concrete, reproducible finding
the demo notebook captures for requests A/B/C without requiring the LangSmith UI.
