# Research Hub — Multi-Agent Research Assistant

A small team of cooperating agents behind one chat interface. Give it a research question and an
Orchestrator routes the request through five specialist agents — Search, Source Evaluator,
Fact-Checker (RAG), and Reviewer — to go from a raw query to a verified, written, human-approved
report: finding sources, judging their credibility, checking claims against retrieved evidence,
drafting the report, and reviewing it before it reaches you or a saved file.

Built on the **LangGraph Functional API** (`@task`/`@entrypoint`, never `StateGraph`), with
per-thread checkpointed persistence, a cross-thread long-term memory Store, two human-in-the-loop
gates, a bounded revision loop, retry/fallback error handling, and a full chat UI.

## Programme

- **Team:** Leen, Lamya, Ghalia, Walaa
- **Programme / cohort dates:** Building Agentic AI Systems — Aug 9–13, 2026 (Sun–Thu)
- **Declared track:** A (Supervisor + workers — `app/router.py` is a dedicated LLM router deciding the next step across the Search / Source Evaluator / Fact-Checker / Reviewer worker agents; the course capstone-prep material maps a dedicated-router "who decides next" shape to Track A)
- **SDAIA Academy GitHub:** https://github.com/SDAIA

## The idea, in three requests

| # | Request | What happens |
|---|---|---|
| A | *"What's new in the Model Context Protocol?"* | Quick research, answered in chat. No file, no human checkpoint. |
| B | *"Research the top 3 vector databases and save a comparison to reports/vector-dbs.md."* | Full pipeline, ends with a saved file (no confirmation needed — the file is new). |
| C | *"Is this claim about drug X still accurate?"* | Sources are weak; the Reviewer rejects the first draft; a revision cycle runs; a human confirms before the answer is delivered. |

See `docs/write-up.md` for the full design write-up and how each piece maps to the project rubric.

## Architecture at a glance

```
backend/app/
  state.py, messages.py       typed ResearchState + AgentMessage envelope
  router.py                   LLM structured-output router + deterministic fallback
  pipeline.py                 @entrypoint/@task orchestration loop, the two interrupt() gates
  agents/                     search_agent, source_evaluator, fact_checker (RAG + report), reviewer
  rag/                        chunking + local TF-IDF embeddings + retrieval (no external API needed)
  mcp_servers/                real MCP servers: web_search / fetch_page / domain_lookup, fs_* tools
  tools/                      in-process wrappers the pipeline calls (same logic as the MCP servers)
  persistence/                SQLite checkpointer (short-term) + SQLite long-term Store (cross-thread)
  reliability.py, tracing.py  RetryPolicy + fallback, LangSmith wiring + local trace-finding helper
  server.py                   FastAPI: POST /api/chat, POST /api/resume (SSE), GET /api/threads
notebook/demo.ipynb           runs requests A/B/C end-to-end, captures a trace finding
frontend/                     Vite + React + TypeScript + Tailwind chat UI ("Research Hub")
```

## Running it

### 1. Backend

```bash
cd backend
python3 -m venv ../.venv && source ../.venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # then fill in ANTHROPIC_API_KEY (see below)
uvicorn app.server:app --reload --port 8000
```

**No API key? It still runs.** With no `ANTHROPIC_API_KEY` set, the server automatically falls back
to a keyless **demo mode**: the exact same agent/pipeline code path runs against a deterministic
synthetic LLM and synthetic sources (clearly labeled `[DEMO MODE]` in every report), so the whole
chat UI — including the revision loop and both human-in-the-loop gates — is explorable with zero
setup. Set `ANTHROPIC_API_KEY` in `.env` (and optionally `TAVILY_API_KEY` for real web search
instead of the keyless DuckDuckGo fallback) to research for real.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — the dev server proxies `/api/*` to the backend on port 8000.

### 3. Tests

```bash
cd backend
pytest   # fully offline: FakeStructuredLLM + canned fixtures, no API keys needed
```

### 4. Demo notebook

```bash
cd notebook
jupyter nbconvert --to notebook --execute --inplace demo.ipynb
```

Runs requests A, B, and C end-to-end (offline by default; flip `USE_LIVE_LLM = True` with a real
key to run it live) and captures a concrete trace finding.

## Standalone MCP servers

The web-search and filesystem tools are also runnable as standalone MCP servers for any MCP
client (Claude Desktop, `mcp` inspector, etc.):

```bash
python -m app.mcp_servers.web_search_server
python -m app.mcp_servers.filesystem_server
```

The pipeline itself calls the same underlying logic in-process (`app/tools/*`) to avoid
stdio/subprocess overhead on the hot path — see `docs/write-up.md` section 3.4 for why.

## Environment variables

See `.env.example` for the full list. Nothing is required to run the demo; `ANTHROPIC_API_KEY`
(and optionally `TAVILY_API_KEY`, `LANGCHAIN_API_KEY`) turn on the real pipeline.
