"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Database,
  Plus,
  Trash2,
  Loader2,
  BookOpen,
  Search,
} from "lucide-react";

import {
  listKnowledgeBases,
  createKnowledgeBase,
  deleteKnowledgeBase,
  type KnowledgeBase,
  type KbCreateConfig,
} from "@/lib/api";
import { KbCreateModal, type KbConfig } from "./KbCreateModal";
import { KbDetailPanel } from "./KbDetailPanel";

export function KnowledgeBasePanel({ onClose }: { onClose?: () => void }) {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [selectedKb, setSelectedKb] = useState<KnowledgeBase | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const loadKbs = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await listKnowledgeBases();
      setKbs(res.knowledge_bases);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadKbs();
  }, [loadKbs]);

  const handleCreate = async (config: KbConfig) => {
    try {
      const payload: KbCreateConfig = {
        name: config.name,
        description: config.description,
        embedding_model: config.embeddingModel,
        embedding_dimension: config.embeddingDimension,
        rerank_model: config.rerankModel,
        retrieve_top_k: config.retrieveTopK,
        doc_processor: config.docProcessor,
        chunk_size: config.chunkSize,
        chunk_overlap: config.chunkOverlap,
        similarity_threshold: config.similarityThreshold,
      };
      await createKnowledgeBase(payload);
      setShowCreate(false);
      await loadKbs();
      // Auto select the newly created KB
      const res = await listKnowledgeBases();
      const newKb = res.knowledge_bases.find((k) => k.name === config.name);
      if (newKb) setSelectedKb(newKb);
    } catch (e) {
      setError(e instanceof Error ? e.message : "创建失败");
    }
  };

  const handleDelete = async (name: string) => {
    if (!window.confirm(`确定要删除知识库 "${name}" 吗？`)) return;
    try {
      await deleteKnowledgeBase(name);
      if (selectedKb?.name === name) setSelectedKb(null);
      await loadKbs();
    } catch (e) {
      setError(e instanceof Error ? e.message : "删除失败");
    }
  };

  const filteredKbs = kbs.filter((kb) =>
    kb.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // If a KB is selected, show detail panel
  if (selectedKb) {
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
          overflow: "hidden",
        }}
      >
        <KbDetailPanel
          kb={selectedKb}
          onBack={() => setSelectedKb(null)}
          onRefresh={loadKbs}
        />
      </div>
    );
  }

  return (
    <>
      <div
        style={{
          display: "flex",
          height: "100%",
          flexDirection: "column",
          borderRadius: 16,
          backgroundColor: "#ffffff",
          boxShadow: "0 8px 30px rgba(0,0,0,0.12)",
          border: "1px solid #e5e5e5",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            height: 56,
            alignItems: "center",
            justifyContent: "space-between",
            borderBottom: "1px solid #e5e5e5",
            padding: "0 20px",
            flexShrink: 0,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Database size={18} style={{ color: "#10a37f" }} />
            <span style={{ fontSize: 15, fontWeight: 600, color: "#1a1a1a" }}>知识库</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 12px",
                borderRadius: 8,
                border: "1px solid #e5e5e5",
                backgroundColor: "#f9f9f9",
              }}
            >
              <Search size={14} style={{ color: "#999999" }} />
              <input
                type="text"
                placeholder="搜索知识库"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  border: "none",
                  background: "transparent",
                  fontSize: 13,
                  outline: "none",
                  width: 140,
                  color: "#1a1a1a",
                }}
              />
            </div>
            <button
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                borderRadius: 8,
                backgroundColor: "#10a37f",
                padding: "6px 14px",
                fontSize: 13,
                color: "#ffffff",
                border: "none",
                cursor: "pointer",
              }}
              onClick={() => setShowCreate(true)}
              type="button"
            >
              <Plus size={14} />
              添加
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
                  color: "#999999",
                  backgroundColor: "transparent",
                  border: "none",
                  cursor: "pointer",
                }}
                onClick={onClose}
                type="button"
              >
                <span style={{ fontSize: 18 }}>&times;</span>
              </button>
            )}
          </div>
        </div>

        {/* Error */}
        {error && (
          <div
            style={{
              padding: "8px 20px",
              backgroundColor: "rgba(239, 68, 68, 0.1)",
              color: "#ef4444",
              fontSize: 13,
              borderBottom: "1px solid #e5e5e5",
            }}
          >
            {error}
          </div>
        )}

        {/* KB List */}
        <div style={{ flex: 1, overflowY: "auto", padding: "16px 20px" }}>
          {loading ? (
            <div style={{ textAlign: "center", padding: 40, color: "#999999" }}>
              <Loader2 size={24} style={{ animation: "spin 1s linear infinite" }} />
            </div>
          ) : filteredKbs.length === 0 ? (
            <div style={{ textAlign: "center", padding: 60, color: "#999999" }}>
              <Database size={48} style={{ opacity: 0.3, marginBottom: 12 }} />
              <p style={{ fontSize: 14 }}>{searchQuery ? "未找到匹配的知识库" : "暂无知识库"}</p>
              <p style={{ fontSize: 12, marginTop: 4 }}>点击右上角"添加"创建新知识库</p>
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12 }}>
              {filteredKbs.map((kb) => (
                <div
                  key={kb.name}
                  onClick={() => setSelectedKb(kb)}
                  style={{
                    padding: 16,
                    borderRadius: 12,
                    border: "1px solid #e5e5e5",
                    backgroundColor: "#ffffff",
                    cursor: "pointer",
                    transition: "all 0.15s",
                    position: "relative",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = "#10a37f";
                    e.currentTarget.style.boxShadow = "0 2px 8px rgba(16,163,127,0.1)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = "#e5e5e5";
                    e.currentTarget.style.boxShadow = "none";
                  }}
                >
                  <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                    <div
                      style={{
                        display: "flex",
                        height: 40,
                        width: 40,
                        alignItems: "center",
                        justifyContent: "center",
                        borderRadius: 10,
                        backgroundColor: "rgba(16, 163, 127, 0.1)",
                        color: "#10a37f",
                        flexShrink: 0,
                      }}
                    >
                      <BookOpen size={18} />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <p
                        style={{
                          fontSize: 14,
                          fontWeight: 600,
                          color: "#1a1a1a",
                          margin: 0,
                          whiteSpace: "nowrap",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                        }}
                      >
                        {kb.name}
                      </p>
                      <p style={{ fontSize: 12, color: "#999999", margin: "4px 0 0" }}>
                        {kb.document_count} 文档 · {kb.has_index ? "已索引" : "未索引"}
                      </p>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        void handleDelete(kb.name);
                      }}
                      style={{
                        display: "flex",
                        height: 28,
                        width: 28,
                        alignItems: "center",
                        justifyContent: "center",
                        borderRadius: 6,
                        border: "none",
                        background: "transparent",
                        cursor: "pointer",
                        color: "#cccccc",
                        flexShrink: 0,
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.color = "#ef4444";
                        e.currentTarget.style.backgroundColor = "rgba(239,68,68,0.1)";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.color = "#cccccc";
                        e.currentTarget.style.backgroundColor = "transparent";
                      }}
                      type="button"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                  <div
                    style={{
                      display: "flex",
                      gap: 8,
                      marginTop: 12,
                      fontSize: 11,
                      color: "#999999",
                    }}
                  >
                    <span style={{ padding: "2px 8px", borderRadius: 6, backgroundColor: "#f5f5f5" }}>
                      索引: {kb.index_size}
                    </span>
                    {kb.updated_at && (
                      <span style={{ padding: "2px 8px", borderRadius: 6, backgroundColor: "#f5f5f5" }}>
                        {new Date(kb.updated_at).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Create Modal */}
      {showCreate && (
        <KbCreateModal
          onClose={() => setShowCreate(false)}
          onConfirm={handleCreate}
        />
      )}
    </>
  );
}
