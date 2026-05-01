"use client";

import { useEffect, useRef } from "react";

import { ChatInput } from "@/components/chat/ChatInput";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { useAppStore } from "@/lib/store";

export function ChatPanel() {
  const { messages, sendMessage, isStreaming, forceThink, forceSearch, toggleForceThink, toggleForceSearch } = useAppStore();
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0, backgroundColor: "#ffffff" }}>
      <div style={{ flex: 1, overflowY: "auto" }}>
        <div style={{ maxWidth: 768, margin: "0 auto", padding: "24px 16px" }}>
          {!messages.length && (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "80px 0", textAlign: "center" }}>
              <div
                style={{
                  display: "flex",
                  height: 48,
                  width: 48,
                  alignItems: "center",
                  justifyContent: "center",
                  borderRadius: 12,
                  backgroundColor: "rgba(16, 163, 127, 0.1)",
                  color: "#10a37f",
                  marginBottom: 16,
                }}
              >
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 2L2 7l10 5 10-5-10-5z" />
                  <path d="M2 17l10 5 10-5" />
                  <path d="M2 12l10 5 10-5" />
                </svg>
              </div>
              <h2 style={{ fontSize: 20, fontWeight: 600, color: "#1a1a1a", marginBottom: 8 }}>
                MiniClaw 智能助手
              </h2>
              <p style={{ fontSize: 14, color: "#666666", maxWidth: 400 }}>
                基于 LangGraph 的多 Agent 个人 AI 助手。你可以直接提问，系统会自动路由到最合适的 Agent 处理。
              </p>
            </div>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
            {messages.map((message) => (
              <ChatMessage
                content={message.content}
                key={message.id}
                retrievals={message.retrievals}
                role={message.role}
                thinkingSteps={message.thinkingSteps}
                toolCalls={message.toolCalls}
              />
            ))}
          </div>
          <div ref={endRef} />
        </div>
      </div>

      <ChatInput
        disabled={isStreaming}
        onSend={sendMessage}
        forceThink={forceThink}
        forceSearch={forceSearch}
        onToggleThink={toggleForceThink}
        onToggleSearch={toggleForceSearch}
      />
    </div>
  );
}
