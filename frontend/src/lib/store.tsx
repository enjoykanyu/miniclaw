"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode
} from "react";

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
} from "./api";

export type AgentMode = "assistant" | "companion";

export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolCalls: ToolCall[];
  retrievals: RetrievalResult[];
  thinkingSteps: ThinkingStep[];
  timestamp: number;
};

const FIXED_FILES = [
  "config/prompts/router.yaml",
  "config/agents.yaml",
  "config/skills.yaml",
];

function makeId() {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

function formatTime(ts: number) {
  const d = new Date(ts);
  return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

function toUiMessages(raw: Array<{ role: string; content: string }>): Message[] {
  return raw.map((m) => ({
    id: makeId(),
    role: m.role as "user" | "assistant",
    content: m.content,
    toolCalls: [],
    retrievals: [],
    thinkingSteps: [],
    timestamp: Date.now(),
  }));
}

type AppStore = {
  sessions: SessionSummary[];
  currentSessionId: string | null;
  messages: Message[];
  isStreaming: boolean;
  ragMode: boolean;
  forceThink: boolean;
  forceSearch: boolean;
  selectedKbs: string[];
  kbRetrievalMode: "intent" | "force";
  skills: Array<{ name: string; description: string; path: string }>;
  editableFiles: string[];
  inspectorPath: string;
  inspectorContent: string;
  inspectorDirty: boolean;
  sidebarWidth: number;
  tokenStats: { total_tokens: number } | null;
  agentMode: AgentMode;
  petCharacter: "pikachu" | "doraemon" | "armorhero";
  createNewSession: () => Promise<void>;
  selectSession: (sessionId: string) => Promise<void>;
  sendMessage: (value: string) => Promise<void>;
  toggleRagMode: () => Promise<void>;
  toggleForceThink: () => void;
  toggleForceSearch: () => void;
  toggleKbSelection: (kbName: string) => void;
  setKbRetrievalMode: (mode: "intent" | "force") => void;
  renameCurrentSession: (title: string) => Promise<void>;
  removeSession: (sessionId: string) => Promise<void>;
  loadInspectorFile: (path: string) => Promise<void>;
  updateInspectorContent: (value: string) => void;
  saveInspector: () => Promise<void>;
  setSidebarWidth: (width: number) => void;
  setAgentMode: (mode: AgentMode) => Promise<void>;
  setPetCharacter: (character: "pikachu" | "doraemon" | "armorhero") => void;
};

const StoreContext = createContext<AppStore | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  // === 全局状态 ===
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [ragMode, setRagModeState] = useState(false);
  const [forceThink, setForceThink] = useState(false);
  const [forceSearch, setForceSearch] = useState(false);
  const [selectedKbs, setSelectedKbs] = useState<string[]>([]);
  const [kbRetrievalMode, setKbRetrievalModeState] = useState<"intent" | "force">("intent");
  const [skills, setSkills] = useState<Array<{ name: string; description: string; path: string }>>([]);
  const [inspectorPath, setInspectorPath] = useState("config/prompts/router.yaml");
  const [inspectorContent, setInspectorContent] = useState("");
  const [inspectorDirty, setInspectorDirty] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(308);
  const [tokenStats, setTokenStats] = useState<{ total_tokens: number } | null>(null);
  const [agentMode, setAgentModeState] = useState<AgentMode>("assistant");
  const [isStreaming, setIsStreaming] = useState(false);
  const [petCharacter, setPetCharacter] = useState<"pikachu" | "doraemon" | "armorhero">("pikachu");

  // === 个人助理模式独立状态 ===
  const [assistantSessionId, setAssistantSessionId] = useState<string | null>(null);
  const [assistantMessages, setAssistantMessages] = useState<Message[]>([]);

  // === 情感陪伴模式独立状态 ===
  const [companionSessionId, setCompanionSessionId] = useState<string | null>(null);
  const [companionMessages, setCompanionMessages] = useState<Message[]>([]);

  // === 使用 ref 确保 callback 总是获取最新值 ===
  const agentModeRef = useRef(agentMode);
  const assistantSessionIdRef = useRef(assistantSessionId);
  const companionSessionIdRef = useRef(companionSessionId);
  const isStreamingRef = useRef(isStreaming);
  const forceThinkRef = useRef(forceThink);
  const forceSearchRef = useRef(forceSearch);
  const selectedKbsRef = useRef(selectedKbs);
  const kbRetrievalModeRef = useRef(kbRetrievalMode);

  useEffect(() => { agentModeRef.current = agentMode; }, [agentMode]);
  useEffect(() => { assistantSessionIdRef.current = assistantSessionId; }, [assistantSessionId]);
  useEffect(() => { companionSessionIdRef.current = companionSessionId; }, [companionSessionId]);
  useEffect(() => { isStreamingRef.current = isStreaming; }, [isStreaming]);
  useEffect(() => { forceThinkRef.current = forceThink; }, [forceThink]);
  useEffect(() => { forceSearchRef.current = forceSearch; }, [forceSearch]);
  useEffect(() => { selectedKbsRef.current = selectedKbs; }, [selectedKbs]);
  useEffect(() => { kbRetrievalModeRef.current = kbRetrievalMode; }, [kbRetrievalMode]);

  // === 根据当前模式派生当前显示的 session 和 messages ===
  const isCompanion = agentMode === "companion";
  const currentSessionId = isCompanion ? companionSessionId : assistantSessionId;
  const messages = isCompanion ? companionMessages : assistantMessages;

  const setCurrentSessionId = useCallback((id: string | null) => {
    if (agentModeRef.current === "companion") {
      setCompanionSessionId(id);
    } else {
      setAssistantSessionId(id);
    }
  }, []);

  const setCurrentMessages = useCallback((updater: React.SetStateAction<Message[]>) => {
    if (agentModeRef.current === "companion") {
      setCompanionMessages(updater);
    } else {
      setAssistantMessages(updater);
    }
  }, []);

  const getCurrentSessionId = useCallback(() => {
    return agentModeRef.current === "companion"
      ? companionSessionIdRef.current
      : assistantSessionIdRef.current;
  }, []);

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
    setCurrentMessages(toUiMessages(history.messages));
    setTokenStats({ total_tokens: history.messages.length * 100 });
  }

  async function createNewSession() {
    const created = await createSession();
    await refreshSessions();
    setCurrentSessionId(created.id);
    setCurrentMessages([]);
    setTokenStats(null);
  }

  async function selectSession(sessionId: string) {
    setCurrentSessionId(sessionId);
    await refreshSessionDetails(sessionId);
  }

  async function ensureSession() {
    const sid = getCurrentSessionId();
    if (sid) {
      return sid;
    }
    const created = await createSession();
    setCurrentSessionId(created.id);
    await refreshSessions();
    return created.id;
  }

  async function sendMessage(value: string) {
    if (!value.trim() || isStreamingRef.current) {
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

    setCurrentMessages((prev) => [...prev, userMessage, assistantMessage]);
    setIsStreaming(true);

    let activeAssistantId = assistantMessage.id;

    const patchAssistant = (updater: (message: Message) => Message) => {
      setCurrentMessages((prev) =>
        prev.map((message) => (message.id === activeAssistantId ? updater(message) : message))
      );
    };

    try {
      await streamChat(
        {
          message: value.trim(),
          session_id: sessionId,
          force_think: forceThinkRef.current,
          force_search: forceSearchRef.current,
          selected_kbs: selectedKbsRef.current,
          kb_retrieval_mode: kbRetrievalModeRef.current,
          agent_mode: agentModeRef.current
        },
        {
          onEvent(event, data) {
            console.log("[SSE event]", event, data);

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
                  if (status === "thinking" && isThinkingContent) {
                    updated[existingIndex] = {
                      ...existing,
                      status: "thinking",
                      thinkingContent: (existing.thinkingContent || "") + message
                    };
                  } else if (status === "end") {
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
                retrievals: [
                  ...message.retrievals,
                  {
                    source: String(data.source ?? ""),
                    text: String(data.content ?? ""),
                    score: Number(data.score ?? 0),
                  },
                ],
              }));
              return;
            }

            if (event === "token") {
              const token = String(data.token ?? "");
              patchAssistant((message) => ({
                ...message,
                content: message.content + token,
              }));
              return;
            }

            if (event === "tool_start") {
              patchAssistant((message) => ({
                ...message,
                toolCalls: [
                  ...message.toolCalls,
                  {
                    tool: String(data.name ?? ""),
                    input: String(data.input ?? ""),
                    output: "",
                  },
                ],
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
                return { ...message, toolCalls: updatedToolCalls };
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
              setCurrentMessages((prev) => [...prev, nextAssistant]);
              return;
            }

            if (event === "done") {
              const finalContent = String(data.content ?? "");
              patchAssistant((message) =>
                message.content ? message : { ...message, content: finalContent }
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
                content: message.content || `请求失败: ${String(data.error ?? "unknown error")}`
              }));
            }
          }
        }
      );
    } finally {
      setIsStreaming(false);
      await refreshSessions();
      let thinkingStepsBackup = new Map<string, ThinkingStep[]>();
      setCurrentMessages((prev) => {
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
        setCurrentMessages((prev) =>
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

  function toggleKbSelection(kbName: string) {
    setSelectedKbs((prev) =>
      prev.includes(kbName) ? prev.filter((n) => n !== kbName) : [...prev, kbName]
    );
  }

  function setKbRetrievalMode(mode: "intent" | "force") {
    setKbRetrievalModeState(mode);
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
        setCurrentMessages([]);
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
      try {
        const [initialSessions, rag, initialSkills] = await Promise.all([
          listSessions(),
          getRagMode(),
          listSkills()
        ]);

        // 处理后端未启动的情况（返回空对象）
        const sessions = Array.isArray(initialSessions) ? initialSessions : [];
        const ragEnabled = rag && typeof rag.enabled === "boolean" ? rag.enabled : false;
        const skills = Array.isArray(initialSkills) ? initialSkills : [];

        setSessions(sessions);
        setRagModeState(ragEnabled);
        setSkills(skills);

        if (sessions.length > 0) {
          // 为assistant模式设置第一个session
          setAssistantSessionId(sessions[0].id);
          // 为companion模式也设置（可以是同一个或创建新的）
          if (sessions.length > 1) {
            setCompanionSessionId(sessions[1].id);
          }
          // 加载当前模式的对话详情
          await refreshSessionDetails(sessions[0].id);
        }
        // 如果后端未启动，不自动创建session，避免更多报错
      } catch (error) {
        console.warn("[Store] Failed to initialize from backend:", error);
        // 使用默认空状态，不报错
        setSessions([]);
        setRagModeState(false);
        setSkills([]);
      }

      try {
        const file = await loadFile("config/prompts/router.yaml");
        if (file && file.content) {
          setInspectorPath(file.path);
          setInspectorContent(file.content);
        }
      } catch {
        setInspectorContent("# 暂无内容");
      }
    })();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function setAgentMode(mode: AgentMode) {
    setAgentModeState(mode);
    // 使用setTimeout确保状态更新后再检查
    await new Promise(resolve => setTimeout(resolve, 0));

    // 切换模式后，确保新模式有 session
    if (mode === "companion") {
      if (!companionSessionIdRef.current) {
        const created = await createSession();
        setCompanionSessionId(created.id);
        await refreshSessions();
      }
    } else {
      if (!assistantSessionIdRef.current) {
        const created = await createSession();
        setAssistantSessionId(created.id);
        await refreshSessions();
      }
    }
  }

  const value: AppStore = {
    sessions,
    currentSessionId,
    messages,
    isStreaming,
    ragMode,
    forceThink,
    forceSearch,
    selectedKbs,
    kbRetrievalMode,
    skills,
    editableFiles,
    inspectorPath,
    inspectorContent,
    inspectorDirty,
    sidebarWidth,
    tokenStats,
    agentMode,
    petCharacter,
    createNewSession,
    selectSession,
    sendMessage,
    toggleRagMode,
    toggleForceThink,
    toggleForceSearch,
    toggleKbSelection,
    setKbRetrievalMode,
    renameCurrentSession,
    removeSession,
    loadInspectorFile,
    updateInspectorContent,
    saveInspector,
    setSidebarWidth,
    setAgentMode,
    setPetCharacter
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
