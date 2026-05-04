"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import {
  createSession,
  deleteSession,
  getRagMode,
  getSessionHistory,
  listSessions,
  listSkills,
  loadFile,
  renameSession,
  saveFile,
  setRagMode,
  streamChat,
  type RetrievalResult,
  type SessionSummary,
  type ThinkingStep,
  type ToolCall
} from "@/lib/api";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolCalls: ToolCall[];
  retrievals: RetrievalResult[];
  thinkingSteps: ThinkingStep[];
  timestamp: number;
};

type AppStore = {
  sessions: SessionSummary[];
  currentSessionId: string | null;
  messages: Message[];
  isStreaming: boolean;
  ragMode: boolean;
  forceThink: boolean;
  forceSearch: boolean;
  skills: Array<{ name: string; description: string; path: string }>;
  editableFiles: string[];
  inspectorPath: string;
  inspectorContent: string;
  inspectorDirty: boolean;
  sidebarWidth: number;
  tokenStats: { total_tokens: number } | null;
  createNewSession: () => Promise<void>;
  selectSession: (sessionId: string) => Promise<void>;
  sendMessage: (value: string) => Promise<void>;
  toggleRagMode: () => Promise<void>;
  toggleForceThink: () => void;
  toggleForceSearch: () => void;
  renameCurrentSession: (title: string) => Promise<void>;
  removeSession: (sessionId: string) => Promise<void>;
  loadInspectorFile: (path: string) => Promise<void>;
  updateInspectorContent: (value: string) => void;
  saveInspector: () => Promise<void>;
  setSidebarWidth: (width: number) => void;
};

const FIXED_FILES = [
  "config/prompts/router.yaml",
  "config/prompts/task.yaml",
  "config/prompts/data.yaml",
  "config/prompts/health.yaml",
  "config/prompts/info.yaml",
  "config/prompts/learning.yaml"
];

const StoreContext = createContext<AppStore | null>(null);

function makeId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function toUiMessages(history: Awaited<ReturnType<typeof getSessionHistory>>["messages"]) {
  return history.map((message) => ({
    id: makeId(),
    role: message.role,
    content: message.content ?? "",
    toolCalls: message.tool_calls ?? [],
    retrievals: [],
    thinkingSteps: [],
    timestamp: message.timestamp ? new Date(message.timestamp).getTime() : Date.now()
  }));
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [ragMode, setRagModeState] = useState(false);
  const [forceThink, setForceThink] = useState(false);
  const [forceSearch, setForceSearch] = useState(false);
  const [skills, setSkills] = useState<Array<{ name: string; description: string; path: string }>>([]);
  const [inspectorPath, setInspectorPath] = useState(
    "config/prompts/router.yaml"
  );
  const [inspectorContent, setInspectorContent] = useState("");
  const [inspectorDirty, setInspectorDirty] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(308);
  const [tokenStats, setTokenStats] = useState<{ total_tokens: number } | null>(null);

  const editableFiles = useMemo(
    () => [...FIXED_FILES, ...skills.map((skill) => skill.path)],
    [skills]
  );

  async function refreshSessions() {
    setSessions(await listSessions());
  }

  async function refreshSkills() {
    setSkills(await listSkills());
  }

  async function refreshSessionDetails(sessionId: string) {
    const history = await getSessionHistory(sessionId);
    setMessages(toUiMessages(history.messages));
    setTokenStats({ total_tokens: history.messages.length * 100 });
  }

  async function createNewSession() {
    const created = await createSession();
    await refreshSessions();
    setCurrentSessionId(created.id);
    setMessages([]);
    setTokenStats(null);
  }

  async function selectSession(sessionId: string) {
    setCurrentSessionId(sessionId);
    await refreshSessionDetails(sessionId);
  }

  async function ensureSession() {
    if (currentSessionId) {
      return currentSessionId;
    }

    const created = await createSession();
    setCurrentSessionId(created.id);
    await refreshSessions();
    return created.id;
  }

  async function sendMessage(value: string) {
    if (!value.trim() || isStreaming) {
      return;
    }

    const sessionId = await ensureSession();
    const userMessage: Message = {
      id: makeId(),
      role: "user",
      content: value.trim(),
      toolCalls: [],
      retrievals: [],
      thinkingSteps: [],
      timestamp: Date.now()
    };
    const assistantMessage: Message = {
      id: makeId(),
      role: "assistant",
      content: "",
      toolCalls: [],
      retrievals: [],
      thinkingSteps: [],
      timestamp: Date.now()
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setIsStreaming(true);

    let activeAssistantId = assistantMessage.id;

    const patchAssistant = (updater: (message: Message) => Message) => {
      setMessages((prev) =>
        prev.map((message) => (message.id === activeAssistantId ? updater(message) : message))
      );
    };

    try {
      await streamChat(
        { message: value.trim(), session_id: sessionId, force_think: forceThink, force_search: forceSearch },
        {
          onEvent(event, data) {
            console.log("[SSE event]", event, data);
            // 思考过程事件
            if (event === "thinking") {
              const step = String(data.step ?? "");
              const status = String(data.status ?? "start") as "start" | "end" | "thinking";
              const message = String(data.message ?? "");
              const isThinkingContent = Boolean(data.is_thinking_content);
              console.log("[SSE thinking]", step, status, message, isThinkingContent);

              patchAssistant((msg) => {
                const existingIndex = msg.thinkingSteps.findIndex(s => s.step === step);
                if (existingIndex >= 0) {
                  const updated = [...msg.thinkingSteps];
                  const existing = updated[existingIndex];
                  // 如果是实时思考内容，累积到 thinkingContent
                  if (status === "thinking" && isThinkingContent) {
                    updated[existingIndex] = {
                      ...existing,
                      status: "thinking",
                      thinkingContent: (existing.thinkingContent || "") + message
                    };
                  } else if (status === "end") {
                    // 节点结束时，保留 thinkingContent，同时更新 status 和 message
                    updated[existingIndex] = {
                      ...existing,
                      status: "end",
                      message: message || existing.message
                    };
                  } else {
                    updated[existingIndex] = { ...existing, step, status, message };
                  }
                  return { ...msg, thinkingSteps: updated };
                }
                // 新建 step
                const newStep: ThinkingStep = status === "thinking" && isThinkingContent
                  ? { step, status: "thinking", message, thinkingContent: message }
                  : { step, status, message };
                return {
                  ...msg,
                  thinkingSteps: [...msg.thinkingSteps, newStep]
                };
              });
              return;
            }

            if (event === "retrieval") {
              patchAssistant((message) => ({
                ...message,
                retrievals: (data.results as RetrievalResult[]) ?? []
              }));
              return;
            }

            if (event === "token") {
              patchAssistant((message) => ({
                ...message,
                content: `${message.content}${String(data.content ?? "")}`
              }));
              return;
            }

            if (event === "tool_start") {
              patchAssistant((message) => ({
                ...message,
                toolCalls: [
                  ...message.toolCalls,
                  {
                    tool: String(data.tool ?? "tool"),
                    input: String(data.input ?? ""),
                    output: ""
                  }
                ]
              }));
              return;
            }

            if (event === "tool_end") {
              patchAssistant((message) => {
                const updatedToolCalls = message.toolCalls.map((toolCall, index, list) =>
                  index === list.length - 1
                    ? { ...toolCall, output: String(data.output ?? "") }
                    : toolCall
                );
                return {
                  ...message,
                  toolCalls: updatedToolCalls
                };
              });
              return;
            }

            if (event === "new_response") {
              const nextAssistant: Message = {
                id: makeId(),
                role: "assistant",
                content: "",
                toolCalls: [],
                retrievals: [],
                thinkingSteps: [],
                timestamp: Date.now()
              };
              activeAssistantId = nextAssistant.id;
              setMessages((prev) => [...prev, nextAssistant]);
              return;
            }

            if (event === "done") {
              const finalContent = String(data.content ?? "");
              patchAssistant((message) =>
                message.content
                  ? message
                  : {
                      ...message,
                      content: finalContent
                    }
              );
              return;
            }

            if (event === "title") {
              void refreshSessions();
              return;
            }

            if (event === "error") {
              patchAssistant((message) => ({
                ...message,
                content:
                  message.content || `请求失败: ${String(data.error ?? "unknown error")}`
              }));
            }
          }
        }
      );
    } finally {
      setIsStreaming(false);
      await refreshSessions();
      let thinkingStepsBackup = new Map<string, ThinkingStep[]>();
      setMessages((prev) => {
        const backup = new Map<string, ThinkingStep[]>();
        for (const msg of prev) {
          if (msg.thinkingSteps && msg.thinkingSteps.length > 0) {
            backup.set(msg.content, [...msg.thinkingSteps]);
          }
        }
        thinkingStepsBackup = backup;
        return prev;
      });
      await refreshSessionDetails(sessionId);
      if (thinkingStepsBackup.size > 0) {
        setMessages((prev) =>
          prev.map((msg) => {
            const saved = thinkingStepsBackup.get(msg.content);
            if (saved && saved.length > 0 && (!msg.thinkingSteps || msg.thinkingSteps.length === 0)) {
              return { ...msg, thinkingSteps: saved };
            }
            return msg;
          })
        );
      }
    }
  }

  async function toggleRagMode() {
    const next = !ragMode;
    setRagModeState(next);
    try {
      await setRagMode(next);
    } catch (error) {
      setRagModeState(!next);
      throw error;
    }
  }

  function toggleForceThink() {
    setForceThink((prev) => !prev);
  }

  function toggleForceSearch() {
    setForceSearch((prev) => !prev);
  }

  async function renameCurrentSession(title: string) {
    if (!currentSessionId || !title.trim()) {
      return;
    }
    await renameSession(currentSessionId, title.trim());
    await refreshSessions();
  }

  async function removeSession(sessionId: string) {
    await deleteSession(sessionId);
    await refreshSessions();
    if (currentSessionId === sessionId) {
      const nextSessions = await listSessions();
      setSessions(nextSessions);
      if (nextSessions.length) {
        setCurrentSessionId(nextSessions[0].id);
        await refreshSessionDetails(nextSessions[0].id);
      } else {
        setCurrentSessionId(null);
        setMessages([]);
        setTokenStats(null);
      }
    }
  }

  async function loadInspectorFile(path: string) {
    setInspectorPath(path);
    const file = await loadFile(path);
    setInspectorContent(file.content);
    setInspectorDirty(false);
  }

  function updateInspectorContent(value: string) {
    setInspectorContent(value);
    setInspectorDirty(true);
  }

  async function saveInspector() {
    await saveFile(inspectorPath, inspectorContent);
    setInspectorDirty(false);
    await refreshSkills();
  }

  useEffect(() => {
    void (async () => {
      const [initialSessions, rag, initialSkills] = await Promise.all([
        listSessions(),
        getRagMode(),
        listSkills()
      ]);

      setSessions(initialSessions);
      setRagModeState(rag.enabled);
      setSkills(initialSkills);

      if (initialSessions.length) {
        setCurrentSessionId(initialSessions[0].id);
        await refreshSessionDetails(initialSessions[0].id);
      } else {
        const created = await createSession();
        setCurrentSessionId(created.id);
        setSessions([created]);
      }

      try {
        const file = await loadFile("config/prompts/router.yaml");
        setInspectorPath(file.path);
        setInspectorContent(file.content);
      } catch {
        setInspectorContent("# 暂无内容");
      }
    })();
  }, []);

  const value: AppStore = {
    sessions,
    currentSessionId,
    messages,
    isStreaming,
    ragMode,
    forceThink,
    forceSearch,
    skills,
    editableFiles,
    inspectorPath,
    inspectorContent,
    inspectorDirty,
    sidebarWidth,
    tokenStats,
    createNewSession,
    selectSession,
    sendMessage,
    toggleRagMode,
    toggleForceThink,
    toggleForceSearch,
    renameCurrentSession,
    removeSession,
    loadInspectorFile,
    updateInspectorContent,
    saveInspector,
    setSidebarWidth
  };

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useAppStore() {
  const value = useContext(StoreContext);
  if (!value) {
    throw new Error("useAppStore must be used inside AppProvider");
  }
  return value;
}
