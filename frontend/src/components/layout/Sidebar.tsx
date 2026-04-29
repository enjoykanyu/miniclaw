"use client";

import { MessageSquare, Plus, Trash2, Bot } from "lucide-react";

import { useAppStore } from "@/lib/store";

export function Sidebar() {
  const {
    sessions,
    currentSessionId,
    selectSession,
    createNewSession,
    removeSession,
  } = useAppStore();

  return (
    <aside
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        width: 260,
        flexShrink: 0,
        borderRight: "1px solid #e5e5e5",
        backgroundColor: "#f9f9f9",
      }}
    >
      <div
        style={{
          display: "flex",
          height: 56,
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 16px",
          borderBottom: "1px solid #e5e5e5",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Bot size={20} style={{ color: "#10a37f" }} />
          <span style={{ fontSize: 14, fontWeight: 600, color: "#1a1a1a" }}>MiniClaw</span>
        </div>
        <button
          style={{
            display: "flex",
            height: 28,
            width: 28,
            alignItems: "center",
            justifyContent: "center",
            borderRadius: 6,
            color: "#666666",
            background: "transparent",
            border: "none",
            cursor: "pointer",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "#f0f0f0")}
          onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
          onClick={() => void createNewSession()}
          title="新会话"
          type="button"
        >
          <Plus size={16} />
        </button>
      </div>

      <div style={{ flex: 1, overflowY: "auto", paddingTop: 8 }}>
        <div style={{ padding: "0 12px 8px" }}>
          <span
            style={{
              fontSize: 11,
              fontWeight: 500,
              color: "#999999",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
            }}
          >
            会话列表
          </span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 2, padding: "0 8px" }}>
          {sessions.map((session) => (
            <div
              key={session.id}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                borderRadius: 8,
                padding: "10px 12px",
                cursor: "pointer",
                backgroundColor:
                  session.id === currentSessionId ? "rgba(16, 163, 127, 0.1)" : "transparent",
                color: session.id === currentSessionId ? "#10a37f" : "#1a1a1a",
                transition: "background-color 0.15s",
              }}
              onMouseEnter={(e) => {
                if (session.id !== currentSessionId) {
                  e.currentTarget.style.backgroundColor = "#f0f0f0";
                }
              }}
              onMouseLeave={(e) => {
                if (session.id !== currentSessionId) {
                  e.currentTarget.style.backgroundColor = "transparent";
                }
              }}
              onClick={() => void selectSession(session.id)}
            >
              <MessageSquare size={14} style={{ flexShrink: 0, opacity: 0.6 }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <p
                  style={{
                    fontSize: 13,
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    margin: 0,
                  }}
                >
                  {session.title}
                </p>
                <p style={{ fontSize: 11, color: "#999999", margin: 0, marginTop: 2 }}>
                  {session.message_count} 条消息
                </p>
              </div>
              <button
                style={{
                  display: "flex",
                  height: 24,
                  width: 24,
                  alignItems: "center",
                  justifyContent: "center",
                  borderRadius: 4,
                  color: "#999999",
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  opacity: 0,
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = "#ef4444";
                  e.currentTarget.style.backgroundColor = "rgba(239, 68, 68, 0.1)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = "#999999";
                  e.currentTarget.style.backgroundColor = "transparent";
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  void removeSession(session.id);
                }}
                title="删除"
                type="button"
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}
