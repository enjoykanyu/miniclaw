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
}: {
  role: "user" | "assistant";
  content: string;
  toolCalls: ToolCall[];
  retrievals: RetrievalResult[];
  thinkingSteps: ThinkingStep[];
}) {
  const isUser = role === "user";

  return (
    <div style={{ display: "flex", gap: 12, flexDirection: isUser ? "row" : "row-reverse", justifyContent: isUser ? "flex-end" : "flex-start" }}>
      {/* Avatar */}
      <div
        style={{
          display: "flex",
          height: 32,
          width: 32,
          flexShrink: 0,
          alignItems: "center",
          justifyContent: "center",
          borderRadius: "50%",
          backgroundColor: isUser ? "#1a1a1a" : "rgba(16, 163, 127, 0.1)",
          color: isUser ? "#ffffff" : "#10a37f",
        }}
      >
        {isUser ? (
          <span style={{ fontSize: 12, fontWeight: 500 }}>我</span>
        ) : (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
        )}
      </div>

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0, maxWidth: isUser ? "80%" : "85%" }}>
        {/* Thinking Process - 只要有 thinkingSteps 就显示 */}
        {!isUser && thinkingSteps.length > 0 && (
          <ThinkingProcess steps={thinkingSteps} />
        )}

        <div
          style={{
            display: "inline-block",
            borderRadius: 16,
            padding: "10px 16px",
            backgroundColor: isUser ? "#1a1a1a" : "#f5f5f5",
            color: isUser ? "#ffffff" : "#1a1a1a",
          }}
        >
          {!isUser && <RetrievalCard results={retrievals} />}
          {!isUser && <ThoughtChain toolCalls={toolCalls} />}

          {content && content.trim() !== "" && (
            <div className={isUser ? "" : "markdown"}>
              {isUser ? (
                <span style={{ fontSize: 14, lineHeight: 1.6 }}>{content}</span>
              ) : (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {content}
                </ReactMarkdown>
              )}
            </div>
          )}

          {/* 只有在没有 content、没有 thinkingSteps、没有 toolCalls 时才显示默认 loading */}
          {!isUser && (!content || content.trim() === "") && !toolCalls.length && thinkingSteps.length === 0 && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, color: "#999999" }}>
              <div style={{ display: "flex", gap: 4 }}>
                <span
                  style={{
                    height: 6,
                    width: 6,
                    borderRadius: "50%",
                    backgroundColor: "#999999",
                    animation: "bounce 1s infinite",
                    animationDelay: "0ms",
                  }}
                />
                <span
                  style={{
                    height: 6,
                    width: 6,
                    borderRadius: "50%",
                    backgroundColor: "#999999",
                    animation: "bounce 1s infinite",
                    animationDelay: "150ms",
                  }}
                />
                <span
                  style={{
                    height: 6,
                    width: 6,
                    borderRadius: "50%",
                    backgroundColor: "#999999",
                    animation: "bounce 1s infinite",
                    animationDelay: "300ms",
                  }}
                />
              </div>
              正在思考...
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ThinkingProcess({ steps }: { steps: ThinkingStep[] }) {
  const [isExpanded, setIsExpanded] = useState(true);
  const activeSteps = steps.filter((s) => s.status === "start");
  const thinkingSteps = steps.filter((s) => s.status === "thinking");
  const completedSteps = steps.filter((s) => s.status === "end");
  const isThinking = activeSteps.length > 0 || thinkingSteps.length > 0;

  // 节点图标映射
  const nodeIcons: Record<string, string> = {
    supervisor: "🧠",
    chat: "💬",
    info: "🔍",
    health: "🏥",
    learning: "📚",
    task: "📋",
    data: "📊",
    rag_detect: "📄",
  };

  return (
    <div
      style={{
        marginBottom: 8,
        borderRadius: 12,
        backgroundColor: "#fafafa",
        border: "1px solid #f0f0f0",
        padding: "8px 12px",
        cursor: "pointer",
      }}
      onClick={() => setIsExpanded(!isExpanded)}
    >
      {/* 头部：状态指示 + 标题 */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {isThinking ? (
            <div style={{ display: "flex", gap: 3 }}>
              <span
                style={{
                  height: 5,
                  width: 5,
                  borderRadius: "50%",
                  backgroundColor: "#10a37f",
                  animation: "bounce 1.2s infinite",
                  animationDelay: "0ms",
                }}
              />
              <span
                style={{
                  height: 5,
                  width: 5,
                  borderRadius: "50%",
                  backgroundColor: "#10a37f",
                  animation: "bounce 1.2s infinite",
                  animationDelay: "200ms",
                }}
              />
              <span
                style={{
                  height: 5,
                  width: 5,
                  borderRadius: "50%",
                  backgroundColor: "#10a37f",
                  animation: "bounce 1.2s infinite",
                  animationDelay: "400ms",
                }}
              />
            </div>
          ) : (
            <div
              style={{
                width: 14,
                height: 14,
                borderRadius: "50%",
                backgroundColor: "#10a37f",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </div>
          )}
          <span style={{ fontSize: 12, color: "#666666", fontWeight: 500 }}>
            {isThinking
              ? (thinkingSteps.length > 0
                ? "正在分析..."
                : activeSteps[activeSteps.length - 1].message || `正在调用 ${activeSteps[activeSteps.length - 1].step}...`)
              : completedSteps.length > 0
              ? "思考完成"
              : "正在思考..."}
          </span>
        </div>
        {/* 展开/折叠箭头 */}
        <span style={{ fontSize: 12, color: "#999999", transition: "transform 0.2s", transform: isExpanded ? "rotate(180deg)" : "rotate(0deg)" }}>
          ▼
        </span>
      </div>

      {/* 详细步骤列表 - 可折叠 */}
      {isExpanded && (
        <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 8, paddingLeft: 4 }}>
          {/* 实时思考内容 - supervisor 节点的 LLM 思考过程 */}
          {thinkingSteps.map((step, index) => {
            const icon = nodeIcons[step.step] || "⚙️";
            return (
              <div
                key={`thinking-${step.step}-${index}`}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                  fontSize: 11,
                  color: "#666666",
                  padding: "6px 8px",
                  borderRadius: 6,
                  backgroundColor: "#f0f8f5",
                  border: "1px solid #e0f0e8",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ fontSize: 12 }}>{icon}</span>
                  <span style={{ fontWeight: 500, color: "#10a37f" }}>
                    {step.message || `正在思考: ${step.step}`}
                  </span>
                  <div style={{ display: "flex", gap: 2, marginLeft: "auto" }}>
                    <span style={{ height: 4, width: 4, borderRadius: "50%", backgroundColor: "#10a37f", animation: "bounce 1s infinite" }} />
                    <span style={{ height: 4, width: 4, borderRadius: "50%", backgroundColor: "#10a37f", animation: "bounce 1s infinite", animationDelay: "150ms" }} />
                    <span style={{ height: 4, width: 4, borderRadius: "50%", backgroundColor: "#10a37f", animation: "bounce 1s infinite", animationDelay: "300ms" }} />
                  </div>
                </div>
                {/* 实时累积的思考文字 */}
                {step.thinkingContent && (
                  <div
                    style={{
                      fontSize: 11,
                      lineHeight: 1.5,
                      color: "#555555",
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-word",
                      maxHeight: 200,
                      overflowY: "auto",
                      padding: "4px 6px",
                      backgroundColor: "rgba(255,255,255,0.6)",
                      borderRadius: 4,
                    }}
                  >
                    {step.thinkingContent}
                  </div>
                )}
              </div>
            );
          })}

          {/* 已完成的步骤 */}
          {completedSteps.map((step, index) => {
            const icon = nodeIcons[step.step] || "⚙️";
            const isDecision = step.step === "supervisor" && step.message?.includes("决策分析");
            const hasThinkingContent = !!step.thinkingContent;

            return (
              <div
                key={`${step.step}-${index}`}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                  fontSize: 11,
                  color: isDecision ? "#10a37f" : "#666666",
                  padding: "6px 8px",
                  borderRadius: 6,
                  backgroundColor: hasThinkingContent ? "#f8faf8" : (isDecision ? "rgba(16, 163, 127, 0.05)" : "transparent"),
                  border: hasThinkingContent ? "1px solid #e8f0e8" : "none",
                }}
              >
                <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                  <span style={{ fontSize: 12, flexShrink: 0 }}>{icon}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: isDecision ? 500 : 400 }}>
                      {step.message || `正在调用 ${step.step}...`}
                    </div>
                    {isDecision && (
                      <div style={{ marginTop: 2, fontSize: 10, color: "#10a37f", opacity: 0.8 }}>
                        路由决策
                      </div>
                    )}
                  </div>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#10a37f" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, marginTop: 2 }}>
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </div>
                {/* 展示该节点的思考内容 */}
                {hasThinkingContent && (
                  <div
                    style={{
                      fontSize: 11,
                      lineHeight: 1.5,
                      color: "#555555",
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-word",
                      maxHeight: 150,
                      overflowY: "auto",
                      padding: "4px 6px",
                      backgroundColor: "rgba(255,255,255,0.7)",
                      borderRadius: 4,
                      marginLeft: 20,
                    }}
                  >
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
