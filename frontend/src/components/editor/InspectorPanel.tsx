"use client";

import dynamic from "next/dynamic";
import { Save, X } from "lucide-react";

import { useAppStore } from "@/lib/store";

const Editor = dynamic(() => import("@monaco-editor/react"), { ssr: false });

export function InspectorPanel({ onClose }: { onClose?: () => void }) {
  const store = useAppStore();
  const editableFiles = store.editableFiles;
  const inspectorPath = store.inspectorPath;
  const inspectorContent = store.inspectorContent;
  const inspectorDirty = store.inspectorDirty;
  const loadInspectorFile = store.loadInspectorFile;
  const updateInspectorContent = store.updateInspectorContent;
  const saveInspector = store.saveInspector;

  return (
    <div
      style={{
        display: "flex",
        height: "100%",
        flexDirection: "column",
        borderRadius: 16,
        backgroundColor: "#ffffff",
        boxShadow: "0 8px 30px rgba(0,0,0,0.12)",
        border: "1px solid #e5e5e5",
      }}
    >
      <div
        style={{
          display: "flex",
          height: 56,
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: "1px solid #e5e5e5",
          padding: "0 16px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: "#1a1a1a" }}>设置</span>
          <span style={{ fontSize: 12, color: "#999999" }}>Memory / Prompts / Skills</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              borderRadius: 8,
              backgroundColor: "#10a37f",
              padding: "6px 12px",
              fontSize: 13,
              color: "#ffffff",
              border: "none",
              cursor: "pointer",
            }}
            onClick={() => void saveInspector()}
            type="button"
          >
            <Save size={14} />
            {inspectorDirty ? "保存" : "已保存"}
          </button>
          {onClose && (
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
              onClick={onClose}
              type="button"
            >
              <X size={16} />
            </button>
          )}
        </div>
      </div>

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 6,
          borderBottom: "1px solid #e5e5e5",
          backgroundColor: "#f5f5f5",
          padding: "8px 16px",
        }}
      >
        {editableFiles.map((path) => (
          <button
            key={path}
            style={{
              borderRadius: 6,
              padding: "4px 10px",
              fontSize: 12,
              border: path === inspectorPath ? "none" : "1px solid #e5e5e5",
              backgroundColor: path === inspectorPath ? "#1a1a1a" : "#ffffff",
              color: path === inspectorPath ? "#ffffff" : "#666666",
              cursor: "pointer",
            }}
            onClick={() => void loadInspectorFile(path)}
            type="button"
          >
            {path.split("/").pop()}
          </button>
        ))}
      </div>

      <div style={{ flex: 1, overflow: "hidden" }}>
        <Editor
          defaultLanguage="yaml"
          height="100%"
          onChange={(value) => updateInspectorContent(value ?? "")}
          options={{
            fontFamily: "var(--font-mono)",
            fontSize: 13,
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            wordWrap: "on",
            padding: { top: 16 },
          }}
          path={inspectorPath}
          theme="vs"
          value={inspectorContent}
        />
      </div>
    </div>
  );
}
