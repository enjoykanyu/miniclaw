"use client";

import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { Plus, Settings, Bot, ChevronRight, Database } from "lucide-react";

import { useAppStore } from "@/lib/store";
import { InspectorPanel } from "@/components/editor/InspectorPanel";
import { KnowledgeBasePanel } from "@/components/knowledge/KnowledgeBasePanel";

export function Navbar() {
  const [isInspectorOpen, setIsInspectorOpen] = useState(false);
  const [isKbOpen, setIsKbOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const {
    createNewSession,
    renameCurrentSession,
    sessions,
    currentSessionId
  } = useAppStore();

  const currentTitle =
    sessions.find((session) => session.id === currentSessionId)?.title ?? "新会话";

  return (
    <>
      <header
        style={{
          display: "flex",
          height: 56,
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 16px",
          borderBottom: "1px solid #e5e5e5",
          backgroundColor: "#ffffff",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div
            style={{
              display: "flex",
              height: 32,
              width: 32,
              alignItems: "center",
              justifyContent: "center",
              borderRadius: 8,
              backgroundColor: "rgba(16, 163, 127, 0.1)",
              color: "#10a37f",
            }}
          >
            <Bot size={18} />
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 14, fontWeight: 500, color: "#1a1a1a" }}>
              {currentTitle}
            </span>
            <button
              style={{
                color: "#999999",
                background: "transparent",
                border: "none",
                cursor: "pointer",
                padding: 0,
                display: "flex",
                alignItems: "center",
              }}
              onClick={() => {
                const next = window.prompt("重命名当前会话", currentTitle);
                if (next) {
                  void renameCurrentSession(next);
                }
              }}
              title="重命名"
              type="button"
            >
              <ChevronRight size={14} style={{ transform: "rotate(90deg)" }} />
            </button>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              borderRadius: 8,
              border: "1px solid #e5e5e5",
              padding: "6px 12px",
              fontSize: 13,
              color: "#666666",
              backgroundColor: "#ffffff",
              cursor: "pointer",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "#f0f0f0")}
            onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "#ffffff")}
            onClick={() => void createNewSession()}
            type="button"
          >
            <Plus size={14} />
            新会话
          </button>
          <button
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              borderRadius: 8,
              border: "1px solid #e5e5e5",
              padding: "6px 12px",
              fontSize: 13,
              color: "#666666",
              backgroundColor: "#ffffff",
              cursor: "pointer",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "#f0f0f0")}
            onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "#ffffff")}
            onClick={() => setIsKbOpen(true)}
            title="知识库管理"
            type="button"
          >
            <Database size={14} />
            知识库
          </button>
          <button
            style={{
              display: "flex",
              height: 32,
              width: 32,
              alignItems: "center",
              justifyContent: "center",
              borderRadius: 8,
              color: "#666666",
              backgroundColor: "transparent",
              border: "none",
              cursor: "pointer",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "#f0f0f0")}
            onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
            onClick={() => setIsInspectorOpen(true)}
            title="设置"
            type="button"
          >
            <Settings size={16} />
          </button>
        </div>
      </header>

      {isInspectorOpen && mounted && createPortal(
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 9999,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <div
            style={{
              position: "absolute",
              inset: 0,
              backgroundColor: "rgba(0,0,0,0.3)",
              backdropFilter: "blur(4px)",
            }}
            onClick={() => setIsInspectorOpen(false)}
          />
          <div
            style={{
              position: "relative",
              zIndex: 10,
              display: "flex",
              height: "80vh",
              width: "90vw",
              maxWidth: 900,
              flexDirection: "column",
            }}
          >
            <InspectorPanel onClose={() => setIsInspectorOpen(false)} />
          </div>
        </div>,
        document.body
      )}

      {isKbOpen && mounted && createPortal(
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 9999,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <div
            style={{
              position: "absolute",
              inset: 0,
              backgroundColor: "rgba(0,0,0,0.3)",
              backdropFilter: "blur(4px)",
            }}
            onClick={() => setIsKbOpen(false)}
          />
          <div
            style={{
              position: "relative",
              zIndex: 10,
              display: "flex",
              height: "80vh",
              width: "90vw",
              maxWidth: 1000,
              flexDirection: "column",
            }}
          >
            <KnowledgeBasePanel onClose={() => setIsKbOpen(false)} />
          </div>
        </div>,
        document.body
      )}
    </>
  );
}
