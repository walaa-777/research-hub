import { useEffect, useRef, useState } from "react";
import { ChatEvent, listThreads, resumeChat, sendChat } from "./api";

type LogLine = { role: string; content: string; kind: "status" | "final" | "error" };

type PendingInterrupt = { threadId: string; gate: string; draftReport: string } | null;

export default function App() {
  const [query, setQuery] = useState("");
  const [threadId, setThreadId] = useState<string | null>(null);
  const [threads, setThreads] = useState<string[]>([]);
  const [log, setLog] = useState<LogLine[]>([]);
  const [busy, setBusy] = useState(false);
  const [pendingInterrupt, setPendingInterrupt] = useState<PendingInterrupt>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listThreads().then(setThreads).catch(() => {});
  }, [threadId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [log]);

  function handleEvent(e: ChatEvent) {
    if (e.event === "status") {
      setLog((prev) => [...prev, { role: e.data.role, content: e.data.content, kind: "status" }]);
    } else if (e.event === "interrupt") {
      setThreadId(e.data.thread_id);
      setPendingInterrupt({ threadId: e.data.thread_id, gate: e.data.gate, draftReport: e.data.draft_report });
      setLog((prev) => [
        ...prev,
        { role: "system", content: `Waiting on you: ${gateLabel(e.data.gate)}`, kind: "status" },
      ]);
    } else if (e.event === "final") {
      setThreadId(e.data.thread_id);
      setLog((prev) => [
        ...prev,
        {
          role: "orchestrator",
          content: e.data.final_report + (e.data.output_path ? `\n\nSaved to ${e.data.output_path}` : ""),
          kind: "final",
        },
      ]);
    }
  }

  async function submitQuery() {
    if (!query.trim() || busy) return;
    setBusy(true);
    setLog((prev) => [...prev, { role: "user", content: query, kind: "status" }]);
    const q = query;
    setQuery("");
    try {
      await sendChat(q, threadId, handleEvent);
    } catch (err) {
      setLog((prev) => [...prev, { role: "system", content: `Error: ${String(err)}`, kind: "error" }]);
    } finally {
      setBusy(false);
    }
  }

  async function respondToInterrupt(confirmed: boolean) {
    if (!pendingInterrupt || busy) return;
    setBusy(true);
    const tid = pendingInterrupt.threadId;
    setPendingInterrupt(null);
    try {
      await resumeChat(tid, confirmed, handleEvent);
    } catch (err) {
      setLog((prev) => [...prev, { role: "system", content: `Error: ${String(err)}`, kind: "error" }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-screen">
      <aside className="w-64 shrink-0 border-r border-ink/10 p-4 hidden md:block">
        <h2 className="font-semibold text-ember mb-3">Research Hub</h2>
        <button
          className="text-sm text-ink/60 hover:text-ink mb-4"
          onClick={() => {
            setThreadId(null);
            setLog([]);
            setPendingInterrupt(null);
          }}
        >
          + New thread
        </button>
        <div className="text-xs uppercase tracking-wide text-ink/40 mb-2">Threads</div>
        <ul className="space-y-1 text-sm">
          {threads.map((t) => (
            <li
              key={t}
              className={`truncate cursor-pointer px-2 py-1 rounded ${
                t === threadId ? "bg-ember/10 text-ember" : "text-ink/70 hover:bg-ink/5"
              }`}
              onClick={() => setThreadId(t)}
            >
              {t.slice(0, 8)}
            </li>
          ))}
        </ul>
      </aside>

      <main className="flex-1 flex flex-col">
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
          {log.length === 0 && (
            <div className="text-ink/40 text-sm max-w-lg">
              Ask a research question. Try: "What's new in the Model Context Protocol?" or
              "Research the top 3 vector databases and save a comparison to reports/vector-dbs.md."
            </div>
          )}
          {log.map((line, i) => (
            <Message key={i} line={line} />
          ))}

          {pendingInterrupt && (
            <div className="border border-ember/40 bg-ember/5 rounded-lg p-4 max-w-xl">
              <div className="font-medium mb-2">{gateLabel(pendingInterrupt.gate)}</div>
              <pre className="text-xs whitespace-pre-wrap text-ink/70 mb-3 max-h-40 overflow-y-auto">
                {pendingInterrupt.draftReport}
              </pre>
              <div className="flex gap-2">
                <button
                  className="px-3 py-1.5 rounded bg-ember text-white text-sm disabled:opacity-50"
                  disabled={busy}
                  onClick={() => respondToInterrupt(true)}
                >
                  Confirm
                </button>
                <button
                  className="px-3 py-1.5 rounded border border-ink/20 text-sm disabled:opacity-50"
                  disabled={busy}
                  onClick={() => respondToInterrupt(false)}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="border-t border-ink/10 p-4">
          <div className="flex gap-2 max-w-3xl mx-auto">
            <input
              className="flex-1 border border-ink/20 rounded-lg px-4 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-ember/40"
              placeholder="Ask a research question…"
              value={query}
              disabled={busy || !!pendingInterrupt}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submitQuery()}
            />
            <button
              className="px-5 py-2 rounded-lg bg-ink text-white disabled:opacity-40"
              disabled={busy || !!pendingInterrupt}
              onClick={submitQuery}
            >
              {busy ? "Working…" : "Send"}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}

function gateLabel(gate: string): string {
  if (gate === "overwrite_confirmation") return "That report file already exists — overwrite it?";
  if (gate === "low_confidence_confirmation") return "Some claims are low-confidence — deliver anyway?";
  return "Confirmation needed";
}

function Message({ line }: { line: LogLine }) {
  const isUser = line.role === "user";
  const isFinal = line.kind === "final";
  return (
    <div className={`max-w-2xl ${isUser ? "ml-auto text-right" : ""}`}>
      <div className="text-[11px] uppercase tracking-wide text-ink/40 mb-1">
        {isUser ? "you" : line.role.replace("_", " ")}
      </div>
      <div
        className={`inline-block rounded-lg px-4 py-2 text-sm whitespace-pre-wrap ${
          isUser
            ? "bg-ink text-white"
            : isFinal
            ? "bg-white border border-ember/30 shadow-sm text-left"
            : "bg-ink/5 text-ink/70 text-left"
        }`}
      >
        {line.content}
      </div>
    </div>
  );
}
