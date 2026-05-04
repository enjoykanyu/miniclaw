"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useState } from "react";

import { RetrievalCard } from "@/components/chat/RetrievalCard";
import { ThoughtChain } from "@/components/chat/ThoughtChain";
import type { RetrievalResult, ThinkingStep, ToolCall } from "@/lib/api";

export function ChatMessage({
  role,
  content,
  toolCalls,
  retrievals,
  thinkingSteps,
  timestamp,
}: {
  role: "user" | "assistant";
  content: string;
  toolCalls: ToolCall[];
  retrievals: RetrievalResult[];
  thinkingSteps: ThinkingStep[];
  timestamp: number;
}) {
  const isUser = role === "user";
  const formattedTime = formatTime(timestamp);

  return (
    <div style={{ marginBottom: 24 }}>
      {/* 头部：头像 + 名称 + 时间 */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
        {/* 头像 */}
        <div
          style={{
            display: "flex",
            height: 36,
            width: 36,
            flexShrink: 0,
            alignItems: "center",
            justifyContent: "center",
            borderRadius: 10,
            backgroundColor: isUser ? "#10b981" : "#1a1a1a",
            color: "#ffffff",
            fontSize: 13,
            fontWeight: 600,
          }}
        >
          {isUser ? (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          ) : (
            <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1 }}>AI</span>
          )}
        </div>

        {/* 名称和时间 */}
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 14, fontWeight: 600, color: "#1a1a1a" }}>
              {isUser ? "用户" : "MiniClaw AI"}
            </span>
            {!isUser && (
              <span style={{ fontSize: 11, color: "#10b981", fontWeight: 500, backgroundColor: "rgba(16, 185, 129, 0.1)", padding: "1px 6px", borderRadius: 4 }}>
                Agent
              </span>
            )}
          </div>
          <span style={{ fontSize: 11, color: "#999999" }}>{formattedTime}</span>
        </div>
      </div>

      {/* 内容区域 */}
      <div style={{ paddingLeft: 46 }}>
        {/* AI 的思考过程 */}
        {!isUser && thinkingSteps.length > 0 && (
          <ThinkingProcess steps={thinkingSteps} />
        )}

        {/* 消息内容 */}
        <div
          style={{
            borderRadius: 12,
            padding: isUser ? "12px 16px" : "0",
            backgroundColor: isUser ? "#f3f4f6" : "transparent",
            color: "#1a1a1a",
            maxWidth: isUser ? "85%" : "100%",
            display: "inline-block",
          }}
        >
          {!isUser && <RetrievalCard results={retrievals} />}
          {!isUser && <ThoughtChain toolCalls={toolCalls} />}

          {content && content.trim() !== "" && (
            <div className={isUser ? "" : "markdown"} style={{ fontSize: 14, lineHeight: 1.7 }}>
              {isUser ? (
                <span>{content}</span>
              ) : (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {content}
                </ReactMarkdown>
              )}
            </div>
          )}

          {/* Loading 状态 */}
          {!isUser && (!content || content.trim() === "") && !toolCalls.length && thinkingSteps.length === 0 && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, color: "#999999" }}>
              <div style={{ display: "flex", gap: 4 }}>
                <span style={{ height: 6, width: 6, borderRadius: "50%", backgroundColor: "#999999", animation: "bounce 1s infinite", animationDelay: "0ms" }} />
                <span style={{ height: 6, width: 6, borderRadius: "50%", backgroundColor: "#999999", animation: "bounce 1s infinite", animationDelay: "150ms" }} />
                <span style={{ height: 6, width: 6, borderRadius: "50%", backgroundColor: "#999999", animation: "bounce 1s infinite", animationDelay: "300ms" }} />
              </div>
              正在思考...
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function formatTime(timestamp: number): string {
  const date = new Date(timestamp);
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${month}/${day} ${hours}:${minutes}`;
}

function ThinkingProcess({ steps }: { steps: ThinkingStep[] }) {
  const [isExpanded, setIsExpanded] = useState(true);
  const activeSteps = steps.filter((s) => s.status === "start");
  const thinkingSteps = steps.filter((s) => s.status === "thinking");
  const completedSteps = steps.filter((s) => s.status === "end");
  const isThinking = activeSteps.length > 0 || thinkingSteps.length > 0;

  const nodeIcons: Record<string, string> = {
    supervisor: "🧠",
    chat: "💬",
    info: "🔍",
    health: "🏥",
    learning: "📚",
    task: "📋",
    data: "📊",
    rag_detect: "📄",
    force_search: "🌐",
  };

  return (
    <div
      style={{
        marginBottom: 12,
        borderRadius: 10,
        backgroundColor: "#fafafa",
        border: "1px solid #f0f0f0",
        padding: "10px 14px",
        cursor: "pointer",
      }}
      onClick={() => setIsExpanded(!isExpanded)}
    >
      {/* 头部 */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {isThinking ? (
            <div style={{ display: "flex", gap: 3 }}>
              <span style={{ height: 5, width: 5, borderRadius: "50%", backgroundColor: "#10b981", animation: "bounce 1.2s infinite", animationDelay: "0ms" }} />
              <span style={{ height: 5, width: 5, borderRadius: "50%", backgroundColor: "#10b981", animation: "bounce 1.2s infinite", animationDelay: "200ms" }} />
              <span style={{ height: 5, width: 5, borderRadius: "50%", backgroundColor: "#10b981", animation: "bounce 1.2s infinite", animationDelay: "400ms" }} />
            </div>
          ) : (
            <div style={{ width: 14, height: 14, borderRadius: "50%", backgroundColor: "#10b981", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </div>
          )}
          <span style={{ fontSize: 12, color: "#666666", fontWeight: 500 }}>
            {isThinking
              ? (thinkingSteps.length > 0 ? "正在分析..." : activeSteps[activeSteps.length - 1]?.message || "正在处理...")
              : completedSteps.length > 0 ? "思考完成" : "正在思考..."}
          </span>
        </div>
        <span style={{ fontSize: 12, color: "#999999", transition: "transform 0.2s", transform: isExpanded ? "rotate(180deg)" : "rotate(0deg)" }}>▼</span>
      </div>

      {/* 详细步骤 */}
      {isExpanded && (
        <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 8, paddingLeft: 4 }}>
          {thinkingSteps.map((step, index) => {
            const icon = nodeIcons[step.step] || "⚙️";
            return (
              <div key={`thinking-${step.step}-${index}`} style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 11, color: "#666666", padding: "6px 8px", borderRadius: 6, backgroundColor: "#f0f8f5", border: "1px solid #e0f0e8" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ fontSize: 12 }}>{icon}</span>
                  <span style={{ fontWeight: 500, color: "#10b981" }}>{step.message || `正在思考: ${step.step}`}</span>
                  <div style={{ display: "flex", gap: 2, marginLeft: "auto" }}>
                    <span style={{ height: 4, width: 4, borderRadius: "50%", backgroundColor: "#10b981", animation: "bounce 1s infinite" }} />
                    <span style={{ height: 4, width: 4, borderRadius: "50%", backgroundColor: "#10b981", animation: "bounce 1s infinite", animationDelay: "150ms" }} />
                    <span style={{ height: 4, width: 4, borderRadius: "50%", backgroundColor: "#10b981", animation: "bounce 1s infinite", animationDelay: "300ms" }} />
                  </div>
                </div>
                {step.thinkingContent && (
                  <div style={{ fontSize: 11, lineHeight: 1.5, color: "#555555", whiteSpace: "pre-wrap", wordBreak: "break-word", maxHeight: 200, overflowY: "auto", padding: "4px 6px", backgroundColor: "rgba(255,255,255,0.6)", borderRadius: 4 }}>
                    {step.thinkingContent}
                  </div>
                )}
              </div>
            );
          })}

          {completedSteps.map((step, index) => {
            const icon = nodeIcons[step.step] || "⚙️";
            const isDecision = step.step === "supervisor" && step.message?.includes("决策分析");
            return (
              <div key={`${step.step}-${index}`} style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 11, color: isDecision ? "#10b981" : "#666666", padding: "6px 8px", borderRadius: 6, backgroundColor: step.thinkingContent ? "#f8faf8" : (isDecision ? "rgba(16, 185, 129, 0.05)" : "transparent"), border: step.thinkingContent ? "1px solid #e8f0e8" : "none" }}>
                <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                  <span style={{ fontSize: 12, flexShrink: 0 }}>{icon}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: isDecision ? 500 : 400 }}>{step.message || `正在调用 ${step.step}...`}</div>
                    {isDecision && <div style={{ marginTop: 2, fontSize: 10, color: "#10b981", opacity: 0.8 }}>路由决策</div>}
                  </div>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, marginTop: 2 }}>
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </div>
                {step.thinkingContent && (
                  <div style={{ fontSize: 11, lineHeight: 1.5, color: "#555555", whiteSpace: "pre-wrap", wordBreak: "break-word", maxHeight: 150, overflowY: "auto", padding: "4px 6px", backgroundColor: "rgba(255,255,255,0.7)", borderRadius: 4, marginLeft: 20 }}>
                    {step.thinkingContent}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
