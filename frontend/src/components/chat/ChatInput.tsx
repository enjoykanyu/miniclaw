"use client";

import { Send, Loader2, Globe, Brain, Database, ChevronDown, X, Check } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { listKnowledgeBases, type KnowledgeBase } from "@/lib/api";

export function ChatInput({
  disabled,
  onSend,
  forceThink,
  forceSearch,
  onToggleThink,
  onToggleSearch,
  selectedKbs,
  kbRetrievalMode,
  onToggleKb,
  onSetKbRetrievalMode,
}: {
  disabled: boolean;
  onSend: (value: string) => Promise<void>;
  forceThink: boolean;
  forceSearch: boolean;
  onToggleThink: () => void;
  onToggleSearch: () => void;
  selectedKbs: string[];
  kbRetrievalMode: "intent" | "force";
  onToggleKb: (kbName: string) => void;
  onSetKbRetrievalMode: (mode: "intent" | "force") => void;
}) {
  const [value, setValue] = useState("");
  const [showKbDropdown, setShowKbDropdown] = useState(false);
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [kbLoading, setKbLoading] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const kbDropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (showKbDropdown && kbs.length === 0) {
      setKbLoading(true);
      listKnowledgeBases()
        .then((res) => setKbs(res.knowledge_bases))
        .catch(() => setKbs([]))
        .finally(() => setKbLoading(false));
    }
  }, [showKbDropdown, kbs.length]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (kbDropdownRef.current && !kbDropdownRef.current.contains(event.target as Node)) {
        setShowKbDropdown(false);
      }
    }
    if (showKbDropdown) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [showKbDropdown]);

  const handleSend = () => {
    const nextValue = value.trim();
    if (!nextValue || disabled) {
      return;
    }
    void onSend(nextValue);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const kbActive = selectedKbs.length > 0;

  return (
    <div style={{ borderTop: "1px solid #e5e5e5", backgroundColor: "#ffffff", padding: "12px 16px" }}>
      <div style={{ maxWidth: 768, margin: "0 auto" }}>
        {/* KB selection chips */}
        {kbActive && (
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8, alignItems: "center" }}>
            <span style={{ fontSize: 11, color: "#999999", marginRight: 4 }}>知识库:</span>
            {selectedKbs.map((kbName) => (
              <span
                key={kbName}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 4,
                  padding: "3px 10px",
                  borderRadius: 12,
                  fontSize: 12,
                  backgroundColor: "rgba(16, 163, 127, 0.1)",
                  color: "#10a37f",
                  border: "1px solid rgba(16, 163, 127, 0.2)",
                }}
              >
                <Database size={11} />
                {kbName}
                <button
                  onClick={() => onToggleKb(kbName)}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    border: "none",
                    background: "transparent",
                    cursor: "pointer",
                    color: "#10a37f",
                    padding: 0,
                    marginLeft: 2,
                  }}
                  type="button"
                >
                  <X size={11} />
                </button>
              </span>
            ))}
            <span
              style={{
                fontSize: 11,
                padding: "2px 8px",
                borderRadius: 10,
                backgroundColor: kbRetrievalMode === "force" ? "rgba(239, 68, 68, 0.1)" : "rgba(59, 130, 246, 0.1)",
                color: kbRetrievalMode === "force" ? "#ef4444" : "#3b82f6",
                border: `1px solid ${kbRetrievalMode === "force" ? "rgba(239, 68, 68, 0.2)" : "rgba(59, 130, 246, 0.2)"}`,
                cursor: "pointer",
                userSelect: "none",
              }}
              onClick={() => onSetKbRetrievalMode(kbRetrievalMode === "intent" ? "force" : "intent")}
              title={kbRetrievalMode === "force" ? "当前: 强制检索 - 点击切换为意图识别" : "当前: 意图识别 - 点击切换为强制检索"}
            >
              {kbRetrievalMode === "force" ? "强制检索" : "意图识别"}
            </span>
          </div>
        )}

        <div
          style={{
            display: "flex",
            alignItems: "flex-end",
            gap: 8,
            borderRadius: 16,
            border: "1px solid #e5e5e5",
            backgroundColor: "#f5f5f5",
            padding: "8px 12px",
            transition: "border-color 0.2s, box-shadow 0.2s",
          }}
          onFocus={(e) => {
            e.currentTarget.style.borderColor = "#10a37f";
            e.currentTarget.style.boxShadow = "0 0 0 1px #10a37f";
          }}
          onBlur={(e) => {
            e.currentTarget.style.borderColor = "#e5e5e5";
            e.currentTarget.style.boxShadow = "none";
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", flex: 1, gap: 4 }}>
            <textarea
              ref={textareaRef}
              style={{
                flex: 1,
                resize: "none",
                backgroundColor: "transparent",
                padding: "8px 0",
                fontSize: 14,
                color: "#1a1a1a",
                outline: "none",
                border: "none",
                maxHeight: 128,
                lineHeight: 1.5,
              }}
              onChange={(event) => {
                setValue(event.target.value);
                event.target.style.height = "auto";
                event.target.style.height = `${Math.min(event.target.scrollHeight, 128)}px`;
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  handleSend();
                }
              }}
              placeholder="有什么我能帮您的？"
              rows={1}
              value={value}
            />
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              {/* KB Selector */}
              <div style={{ position: "relative" }} ref={kbDropdownRef}>
                <button
                  type="button"
                  onClick={() => setShowKbDropdown(!showKbDropdown)}
                  title="选择知识库"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                    padding: "4px 10px",
                    borderRadius: 12,
                    border: "none",
                    fontSize: 12,
                    cursor: "pointer",
                    transition: "all 0.15s",
                    backgroundColor: kbActive ? "#10a37f" : "transparent",
                    color: kbActive ? "#ffffff" : "#666666",
                  }}
                >
                  <Database size={14} />
                  <span>知识库</span>
                  {kbActive && <span style={{ fontSize: 10, opacity: 0.9 }}>({selectedKbs.length})</span>}
                  <ChevronDown size={12} />
                </button>

                {showKbDropdown && (
                  <div
                    style={{
                      position: "absolute",
                      bottom: "calc(100% + 8px)",
                      left: 0,
                      zIndex: 100,
                      width: 280,
                      backgroundColor: "#ffffff",
                      borderRadius: 12,
                      boxShadow: "0 8px 30px rgba(0,0,0,0.15)",
                      border: "1px solid #e5e5e5",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        padding: "10px 14px",
                        borderBottom: "1px solid #f0f0f0",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                      }}
                    >
                      <span style={{ fontSize: 13, fontWeight: 600, color: "#1a1a1a" }}>选择知识库</span>
                      {kbActive && (
                        <button
                          onClick={() => {
                            selectedKbs.forEach((k) => onToggleKb(k));
                          }}
                          style={{
                            fontSize: 11,
                            color: "#999999",
                            background: "transparent",
                            border: "none",
                            cursor: "pointer",
                          }}
                          type="button"
                        >
                          清除
                        </button>
                      )}
                    </div>

                    {/* Retrieval mode toggle */}
                    <div
                      style={{
                        display: "flex",
                        padding: "8px 12px",
                        gap: 8,
                        borderBottom: "1px solid #f0f0f0",
                      }}
                    >
                      <button
                        onClick={() => onSetKbRetrievalMode("intent")}
                        style={{
                          flex: 1,
                          padding: "5px 10px",
                          borderRadius: 8,
                          border: "1px solid",
                          borderColor: kbRetrievalMode === "intent" ? "#10a37f" : "#e5e5e5",
                          backgroundColor: kbRetrievalMode === "intent" ? "rgba(16, 163, 127, 0.1)" : "#ffffff",
                          color: kbRetrievalMode === "intent" ? "#10a37f" : "#666666",
                          fontSize: 12,
                          cursor: "pointer",
                          transition: "all 0.15s",
                        }}
                        type="button"
                      >
                        意图识别
                      </button>
                      <button
                        onClick={() => onSetKbRetrievalMode("force")}
                        style={{
                          flex: 1,
                          padding: "5px 10px",
                          borderRadius: 8,
                          border: "1px solid",
                          borderColor: kbRetrievalMode === "force" ? "#ef4444" : "#e5e5e5",
                          backgroundColor: kbRetrievalMode === "force" ? "rgba(239, 68, 68, 0.1)" : "#ffffff",
                          color: kbRetrievalMode === "force" ? "#ef4444" : "#666666",
                          fontSize: 12,
                          cursor: "pointer",
                          transition: "all 0.15s",
                        }}
                        type="button"
                      >
                        强制检索
                      </button>
                    </div>

                    <div style={{ maxHeight: 220, overflowY: "auto" }}>
                      {kbLoading ? (
                        <div style={{ padding: 20, textAlign: "center", color: "#999999" }}>
                          <Loader2 size={16} style={{ animation: "spin 1s linear infinite" }} />
                        </div>
                      ) : kbs.length === 0 ? (
                        <div style={{ padding: 20, textAlign: "center", color: "#999999", fontSize: 12 }}>
                          暂无知识库
                        </div>
                      ) : (
                        kbs.map((kb) => {
                          const isSelected = selectedKbs.includes(kb.name);
                          return (
                            <button
                              key={kb.name}
                              onClick={() => onToggleKb(kb.name)}
                              style={{
                                display: "flex",
                                alignItems: "center",
                                gap: 8,
                                width: "100%",
                                padding: "10px 14px",
                                border: "none",
                                background: isSelected ? "rgba(16, 163, 127, 0.05)" : "transparent",
                                cursor: "pointer",
                                textAlign: "left",
                                transition: "background 0.1s",
                              }}
                              onMouseEnter={(e) => {
                                if (!isSelected) e.currentTarget.style.backgroundColor = "#f9f9f9";
                              }}
                              onMouseLeave={(e) => {
                                if (!isSelected) e.currentTarget.style.backgroundColor = "transparent";
                              }}
                              type="button"
                            >
                              <div
                                style={{
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "center",
                                  height: 18,
                                  width: 18,
                                  borderRadius: 4,
                                  border: isSelected ? "none" : "1.5px solid #d0d0d0",
                                  backgroundColor: isSelected ? "#10a37f" : "transparent",
                                  color: "#ffffff",
                                  flexShrink: 0,
                                }}
                              >
                                {isSelected && <Check size={12} />}
                              </div>
                              <div style={{ flex: 1, minWidth: 0 }}>
                                <div style={{ fontSize: 13, color: "#1a1a1a", fontWeight: 500 }}>{kb.name}</div>
                                <div style={{ fontSize: 11, color: "#999999", marginTop: 2 }}>
                                  {kb.document_count} 文档
                                </div>
                              </div>
                            </button>
                          );
                        })
                      )}
                    </div>
                  </div>
                )}
              </div>

              <button
                type="button"
                onClick={onToggleSearch}
                title="联网搜索"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                  padding: "4px 10px",
                  borderRadius: 12,
                  border: "none",
                  fontSize: 12,
                  cursor: "pointer",
                  transition: "all 0.15s",
                  backgroundColor: forceSearch ? "#10a37f" : "transparent",
                  color: forceSearch ? "#ffffff" : "#666666",
                }}
              >
                <Globe size={14} />
                <span>联网搜索</span>
              </button>
              <button
                type="button"
                onClick={onToggleThink}
                title="深度思考"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                  padding: "4px 10px",
                  borderRadius: 12,
                  border: "none",
                  fontSize: 12,
                  cursor: "pointer",
                  transition: "all 0.15s",
                  backgroundColor: forceThink ? "#10a37f" : "transparent",
                  color: forceThink ? "#ffffff" : "#666666",
                }}
              >
                <Brain size={14} />
                <span>深度思考</span>
              </button>
            </div>
          </div>
          <button
            style={{
              display: "flex",
              height: 32,
              width: 32,
              flexShrink: 0,
              alignItems: "center",
              justifyContent: "center",
              borderRadius: 8,
              backgroundColor: disabled || !value.trim() ? "rgba(16, 163, 127, 0.4)" : "#10a37f",
              color: "#ffffff",
              border: "none",
              cursor: disabled || !value.trim() ? "not-allowed" : "pointer",
              transition: "background-color 0.15s",
              marginBottom: 2,
            }}
            disabled={disabled || !value.trim()}
            onClick={handleSend}
            type="button"
          >
            {disabled ? (
              <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} />
            ) : (
              <Send size={14} />
            )}
          </button>
        </div>
        <p style={{ marginTop: 6, textAlign: "center", fontSize: 11, color: "#999999" }}>
          MiniClaw 可能会生成不准确的信息，请核实重要信息。
        </p>
      </div>
    </div>
  );
}
