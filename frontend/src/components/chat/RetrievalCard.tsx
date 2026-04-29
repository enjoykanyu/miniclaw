"use client";

import { ChevronRight, Database } from "lucide-react";
import { useState } from "react";

import type { RetrievalResult } from "@/lib/api";

export function RetrievalCard({ results }: { results: RetrievalResult[] }) {
  const [expanded, setExpanded] = useState(false);

  if (!results.length) {
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
          backgroundColor: "rgba(16, 163, 127, 0.1)",
          padding: "6px 10px",
          fontSize: 12,
          color: "#10a37f",
          border: "none",
          cursor: "pointer",
        }}
        onClick={() => setExpanded(!expanded)}
        type="button"
      >
        <Database size={12} />
        <span>检索到 {results.length} 条 Memory 片段</span>
        <ChevronRight
          size={12}
          style={{ transform: expanded ? "rotate(90deg)" : "rotate(0deg)", transition: "transform 0.2s" }}
        />
      </button>

      {expanded && (
        <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 8 }}>
          {results.map((item, index) => (
            <div
              key={`${item.source}-${index}`}
              style={{
                borderRadius: 12,
                border: "1px solid #e5e5e5",
                backgroundColor: "#ffffff",
                padding: 12,
              }}
            >
              <div style={{ marginBottom: 6, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span style={{ fontSize: 12, fontWeight: 500, color: "#666666" }}>
                  {item.source}
                </span>
                <span style={{ fontSize: 12, color: "#999999" }}>
                  相关度: {item.score.toFixed(3)}
                </span>
              </div>
              <p style={{ fontSize: 14, lineHeight: 1.6, color: "#1a1a1a", margin: 0 }}>
                {item.text}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
