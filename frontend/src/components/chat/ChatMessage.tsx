"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

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
  const activeSteps = steps.filter((s) => s.status === "start");
  const completedSteps = steps.filter((s) => s.status === "end");

  return (
    <div
      style={{
        marginBottom: 8,
        borderRadius: 12,
        backgroundColor: "#fafafa",
        border: "1px solid #f0f0f0",
        padding: "8px 12px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
        <div
          style={{
            display: "flex",
            gap: 3,
          }}
        >
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
        <span style={{ fontSize: 12, color: "#666666" }}>
          {activeSteps.length > 0
            ? activeSteps[activeSteps.length - 1].message || `正在调用 ${activeSteps[activeSteps.length - 1].step}...`
            : completedSteps.length > 0
            ? "思考完成"
            : "正在思考..."}
        </span>
      </div>

      {completedSteps.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          {completedSteps.map((step, index) => (
            <div
              key={`${step.step}-${index}`}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                fontSize: 11,
                color: "#999999",
              }}
            >
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#10a37f" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
              <span>{step.message || step.step}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
