export type ChatEvent =
  | { event: "status"; data: { role: string; content: string; metadata: Record<string, unknown> } }
  | { event: "interrupt"; data: { thread_id: string; gate: string; draft_report: string } }
  | { event: "final"; data: { thread_id: string; status: string; final_report: string; output_path: string | null; sources: string[] } };

async function streamPost(url: string, body: unknown, onEvent: (e: ChatEvent) => void): Promise<void> {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.body) throw new Error("No response body (SSE stream expected)");

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";
    for (const chunk of chunks) {
      const lines = chunk.split("\n");
      let event = "message";
      let data = "";
      for (const line of lines) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (data) {
        try {
          onEvent({ event, data: JSON.parse(data) } as ChatEvent);
        } catch {
          // ignore malformed chunk
        }
      }
    }
  }
}

export function sendChat(query: string, threadId: string | null, onEvent: (e: ChatEvent) => void) {
  return streamPost("/api/chat", { query, thread_id: threadId }, onEvent);
}

export function resumeChat(threadId: string, confirmed: boolean, onEvent: (e: ChatEvent) => void) {
  return streamPost("/api/resume", { thread_id: threadId, confirmed }, onEvent);
}

export async function listThreads(): Promise<string[]> {
  const resp = await fetch("/api/threads");
  const data = await resp.json();
  return data.threads ?? [];
}
