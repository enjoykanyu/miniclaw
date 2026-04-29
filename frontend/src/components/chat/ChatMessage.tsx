"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { RetrievalCard } from "@/components/chat/RetrievalCard";
import { ThoughtChain } from "@/components/chat/ThoughtChain";
import type { RetrievalResult, ToolCall } from "@/lib/api";

export function ChatMessage({
  role,
  content,
  toolCalls,
  retrievals
}: {
  role: "user" | "assistant";
  content: string;
  toolCalls: ToolCall[];
  retrievals: RetrievalResult[];
}) {
  const isUser = role === "user";

  return (
    <div style={{ display: "flex", gap: 12, flexDirection: isUser ? "row-reverse" : "row" }}>
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

          {!isUser && (!content || content.trim() === "") && !toolCalls.length && (
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
