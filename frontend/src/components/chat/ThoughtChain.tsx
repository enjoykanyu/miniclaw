"use client";

import { ChevronRight, Wrench } from "lucide-react";
import { useState } from "react";

import type { ToolCall } from "@/lib/api";

export function ThoughtChain({ toolCalls }: { toolCalls: ToolCall[] }) {
  const [expanded, setExpanded] = useState(false);

  if (!toolCalls.length) {
    return null;
  }

  return (
    <div style={{ marginBottom: 12 }}>
      <button
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          borderRadius: 8,
          backgroundColor: "rgba(255,255,255,0.6)",
          padding: "6px 10px",
          fontSize: 12,
          color: "#666666",
          border: "none",
          cursor: "pointer",
        }}
        onClick={() => setExpanded(!expanded)}
        type="button"
      >
        <Wrench size={12} />
        <span>{toolCalls.length} 个工具调用</span>
        <ChevronRight
          size={12}
          style={{ transform: expanded ? "rotate(90deg)" : "rotate(0deg)", transition: "transform 0.2s" }}
        />
      </button>

      {expanded && (
        <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 8 }}>
          {toolCalls.map((toolCall, index) => (
            <div
              key={`${toolCall.tool}-${index}`}
              style={{
                borderRadius: 12,
                border: "1px solid #e5e5e5",
                backgroundColor: "#ffffff",
                padding: 12,
              }}
            >
              <div style={{ marginBottom: 8 }}>
                <span
                  style={{
                    borderRadius: 6,
                    backgroundColor: "rgba(16, 163, 127, 0.1)",
                    padding: "2px 8px",
                    fontSize: 12,
                    fontWeight: 500,
                    color: "#10a37f",
                  }}
                >
                  {toolCall.tool}
                </span>
              </div>
              {toolCall.input && (
                <div style={{ marginBottom: 8 }}>
                  <div style={{ marginBottom: 4, fontSize: 12, fontWeight: 500, color: "#999999" }}>
                    输入
                  </div>
                  <pre
                    style={{
                      borderRadius: 8,
                      backgroundColor: "#f5f5f5",
                      padding: 8,
                      fontSize: 12,
                      color: "#666666",
                      overflowX: "auto",
                      margin: 0,
                      fontFamily: "var(--font-mono), monospace",
                    }}
                  >
                    {toolCall.input}
                  </pre>
                </div>
              )}
              {toolCall.output && (
                <div>
                  <div style={{ marginBottom: 4, fontSize: 12, fontWeight: 500, color: "#999999" }}>
                    输出
                  </div>
                  <div
                    style={{
                      maxHeight: 160,
                      overflowY: "auto",
                      borderRadius: 8,
                      backgroundColor: "#f5f5f5",
                      padding: 8,
                      fontSize: 12,
                      color: "#666666",
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-all",
                      fontFamily: "var(--font-mono), monospace",
                    }}
                  >
                    {toolCall.output}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
