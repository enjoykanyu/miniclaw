export type ToolCall = {
  tool: string;
  input: string;
  output: string;
};

export type RetrievalResult = {
  text: string;
  score: number;
  source: string;
};

export type ThinkingStep = {
  step: string;
  status: "start" | "end" | "thinking";
  message?: string;
  thinkingContent?: string;
};

export type SessionSummary = {
  id: string;
  title: string;
  created_at: number;
  updated_at: number;
  message_count: number;
};

export type SessionHistory = {
  id: string;
  title: string;
  created_at: number;
  updated_at: number;
  compressed_context?: string;
  messages: Array<{
    role: "user" | "assistant";
    content: string;
    tool_calls?: ToolCall[];
    timestamp?: string;
  }>;
};

export type StreamHandlers = {
  onEvent: (event: string, data: Record<string, unknown>) => void;
};

function getApiBase() {
  if (typeof window === "undefined") {
    return "http://127.0.0.1:9190";
  }
  return `http://${window.location.hostname}:9190`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBase()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }

  return (await response.json()) as T;
}

export async function listSessions() {
  return request<SessionSummary[]>("/sessions");
}

export async function createSession(title = "新会话") {
  return request<SessionSummary>("/sessions", {
    method: "POST",
    body: JSON.stringify({ title })
  });
}

export async function renameSession(sessionId: string, title: string) {
  return request<SessionSummary>(`/sessions/${sessionId}`, {
    method: "PUT",
    body: JSON.stringify({ title })
  });
}

export async function deleteSession(sessionId: string) {
  return request<{ ok: boolean }>(`/sessions/${sessionId}`, {
    method: "DELETE"
  });
}

export async function getSessionHistory(sessionId: string) {
  return request<SessionHistory>(`/sessions/${sessionId}/history`);
}

export async function listSkills() {
  return request<Array<{ name: string; description: string; path: string }>>("/skills");
}

export async function loadFile(path: string) {
  return request<{ path: string; content: string }>(
    `/files?path=${encodeURIComponent(path)}`
  );
}

export async function saveFile(path: string, content: string) {
  return request<{ ok: boolean; path: string }>("/files", {
    method: "POST",
    body: JSON.stringify({ path, content })
  });
}

export async function getRagMode() {
  return request<{ enabled: boolean }>("/config/rag-mode");
}

export async function setRagMode(enabled: boolean) {
  return request<{ enabled: boolean }>("/config/rag-mode", {
    method: "PUT",
    body: JSON.stringify({ enabled })
  });
}

export type KnowledgeBase = {
  name: string;
  description: string;
  document_count: number;
  index_size: number;
  has_index: boolean;
  updated_at: string;
};

export type KbDocument = {
  source: string;
  type: string;
  chunk_count: number;
};

export async function listKnowledgeBases() {
  return request<{ knowledge_bases: KnowledgeBase[]; count: number }>("/knowledge-bases");
}

export async function createKnowledgeBase(name: string, description = "") {
  return request<{ name: string; description: string; document_count: number; message: string }>("/knowledge-bases", {
    method: "POST",
    body: JSON.stringify({ name, description }),
  });
}

export async function getKnowledgeBase(kbName: string) {
  return request<KnowledgeBase & { persist_dir: string }>(`/knowledge-bases/${encodeURIComponent(kbName)}`);
}

export async function updateKnowledgeBase(kbName: string, newName: string, description = "") {
  return request<{ name: string; description: string; message: string }>(`/knowledge-bases/${encodeURIComponent(kbName)}`, {
    method: "PUT",
    body: JSON.stringify({ name: newName, description }),
  });
}

export async function deleteKnowledgeBase(kbName: string) {
  return request<{ message: string }>(`/knowledge-bases/${encodeURIComponent(kbName)}`, {
    method: "DELETE",
  });
}

export async function listKbDocuments(kbName: string) {
  return request<{ knowledge_base: string; documents: KbDocument[]; total_chunks: number }>(
    `/knowledge-bases/${encodeURIComponent(kbName)}/documents`
  );
}

export async function addDocumentsToKb(kbName: string, filePaths: string[]) {
  const query = filePaths.map((p) => `file_paths=${encodeURIComponent(p)}`).join("&");
  return request<{ knowledge_base: string; added_count: number; message: string }>(
    `/knowledge-bases/${encodeURIComponent(kbName)}/documents?${query}`,
    { method: "POST" }
  );
}

export async function clearKbDocuments(kbName: string) {
  return request<{ message: string }>(`/knowledge-bases/${encodeURIComponent(kbName)}/documents`, {
    method: "DELETE",
  });
}

export async function streamChat(
  payload: {
    message: string;
    session_id: string;
    force_think?: boolean;
    force_search?: boolean;
  },
  handlers: StreamHandlers
) {
  const response = await fetch(`${getApiBase()}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      ...payload,
      user_id: "web_user",
      stream: true
    })
  });

  if (!response.ok || !response.body) {
    throw new Error(`Chat request failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const flushBlock = (block: string) => {
    const lines = block.split("\n");
    let event = "message";
    const dataLines: string[] = [];

    for (const line of lines) {
      if (line.startsWith("event:")) {
        event = line.slice(6).trim();
      }
      if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trim());
      }
    }

    if (!dataLines.length) {
      return;
    }

    const data = JSON.parse(dataLines.join("\n")) as Record<string, unknown>;
    handlers.onEvent(event, data);
  };

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });

    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      flushBlock(buffer.slice(0, boundary));
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf("\n\n");
    }

    if (done) {
      if (buffer.trim()) {
        flushBlock(buffer);
      }
      break;
    }
  }
}
