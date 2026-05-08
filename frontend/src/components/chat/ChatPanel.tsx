"use client";

import { useEffect, useRef } from "react";

import { ChatInput } from "@/components/chat/ChatInput";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { PixelPet } from "@/components/pet/PixelPet";
import { usePetAction } from "@/components/pet/usePetMood";
import { useAppStore } from "@/lib/store";

export function ChatPanel() {
  const { messages, sendMessage, isStreaming, forceThink, forceSearch, toggleForceThink, toggleForceSearch, selectedKbs, kbRetrievalMode, toggleKbSelection, setKbRetrievalMode, agentMode, petCharacter, setPetCharacter } = useAppStore();
  const endRef = useRef<HTMLDivElement | null>(null);
  const isCompanion = agentMode === "companion";
  const accentColor = isCompanion ? "#ec4899" : "#10a37f";
  const accentSoft = isCompanion ? "rgba(236, 72, 153, 0.1)" : "rgba(16, 163, 127, 0.1)";

  const petAction = usePetAction(messages, isStreaming);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0, backgroundColor: "#ffffff" }}>
      <div style={{ flex: 1, overflowY: "auto" }}>
        <div style={{ maxWidth: 768, margin: "0 auto", padding: "24px 16px" }}>
          {!messages.length && (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "40px 0", textAlign: "center" }}>
              {/* 情感陪伴模式显示像素宠物 */}
              {isCompanion && (
                <div style={{ marginBottom: 16 }}>
                  <PixelPet
                    character={petCharacter}
                    action={petAction}
                    size={140}
                    showSelector
                    onCharacterChange={setPetCharacter}
                  />
                </div>
              )}
              <div
                style={{
                  display: "flex",
                  height: 48,
                  width: 48,
                  alignItems: "center",
                  justifyContent: "center",
                  borderRadius: 12,
                  backgroundColor: accentSoft,
                  color: accentColor,
                  marginBottom: 16,
                }}
              >
                {isCompanion ? (
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
                  </svg>
                ) : (
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 2L2 7l10 5 10-5-10-5z" />
                    <path d="M2 17l10 5 10-5" />
                    <path d="M2 12l10 5 10-5" />
                  </svg>
                )}
              </div>
              <h2 style={{ fontSize: 20, fontWeight: 600, color: "#1a1a1a", marginBottom: 8 }}>
                {isCompanion ? "情感陪伴助手" : "MiniClaw 智能助手"}
              </h2>
              <p style={{ fontSize: 14, color: "#666666", maxWidth: 400 }}>
                {isCompanion
                  ? "我在这里倾听你的心声，陪你聊天、分享心情。无论开心还是难过，都可以告诉我。"
                  : "基于 LangGraph 的多 Agent 个人 AI 助手。你可以直接提问，系统会自动路由到最合适的 Agent 处理。"}
              </p>
            </div>
          )}

          {/* 有消息时，情感陪伴模式在顶部显示宠物 */}
          {isCompanion && messages.length > 0 && (
            <div style={{ display: "flex", justifyContent: "center", marginBottom: 16, paddingTop: 8 }}>
              <PixelPet
                character={petCharacter}
                action={petAction}
                size={100}
                showSelector
                onCharacterChange={setPetCharacter}
              />
            </div>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
            {messages.map((message) => (
              <ChatMessage
                agentMode={agentMode}
                content={message.content}
                key={message.id}
                retrievals={message.retrievals}
                role={message.role}
                thinkingSteps={message.thinkingSteps}
                timestamp={message.timestamp}
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
        selectedKbs={selectedKbs}
        kbRetrievalMode={kbRetrievalMode}
        onToggleKb={toggleKbSelection}
        onSetKbRetrievalMode={setKbRetrievalMode}
      />
    </div>
  );
}
