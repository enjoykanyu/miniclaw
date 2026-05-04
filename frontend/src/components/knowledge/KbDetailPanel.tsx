"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  Database,
  FileText,
  StickyNote,
  FolderOpen,
  Link as LinkIcon,
  Globe,
  Upload,
  CheckCircle,
  AlertCircle,
  Loader2,
  Trash2,
  X,
  Plus,
} from "lucide-react";

import {
  listKbDocuments,
  clearKbDocuments,
  uploadFilesToKb,
  type KnowledgeBase,
  type KbDocument,
} from "@/lib/api";

type UploadFileItem = {
  id: string;
  file: File;
  status: "pending" | "uploading" | "success" | "error";
  progress: number;
  message?: string;
};

type TabType = "files" | "notes" | "folders" | "urls" | "websites";

const TABS: { key: TabType; label: string; icon: React.ReactNode }[] = [
  { key: "files", label: "文件", icon: <FileText size={14} /> },
  { key: "notes", label: "笔记", icon: <StickyNote size={14} /> },
  { key: "folders", label: "目录", icon: <FolderOpen size={14} /> },
  { key: "urls", label: "网址", icon: <LinkIcon size={14} /> },
  { key: "websites", label: "网站", icon: <Globe size={14} /> },
];

export function KbDetailPanel({
  kb,
  onBack,
  onRefresh,
}: {
  kb: KnowledgeBase;
  onBack: () => void;
  onRefresh: () => void;
}) {
  const [activeTab, setActiveTab] = useState<TabType>("files");
  const [documents, setDocuments] = useState<KbDocument[]>([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [uploadQueue, setUploadQueue] = useState<UploadFileItem[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadDocs = useCallback(async () => {
    setDocsLoading(true);
    try {
      const res = await listKbDocuments(kb.name);
      setDocuments(res.documents);
    } catch (e) {
      console.error("Load docs error:", e);
      setDocuments([]);
    } finally {
      setDocsLoading(false);
    }
  }, [kb.name]);

  useEffect(() => {
    void loadDocs();
  }, [loadDocs]);

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (activeTab !== "files") return;
    await addFilesToQueue(Array.from(e.dataTransfer.files));
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      await addFilesToQueue(Array.from(e.target.files));
    }
  };

  const addFilesToQueue = async (files: File[]) => {
    const newItems: UploadFileItem[] = files.map((file) => ({
      id: Math.random().toString(36).slice(2),
      file,
      status: "pending",
      progress: 0,
    }));

    setUploadQueue((prev) => [...prev, ...newItems]);

    // Process uploads sequentially
    for (const item of newItems) {
      setUploadQueue((prev) =>
        prev.map((i) => (i.id === item.id ? { ...i, status: "uploading" } : i))
      );

      try {
        const res = await uploadFilesToKb(kb.name, [item.file]);
        setUploadQueue((prev) =>
          prev.map((i) =>
            i.id === item.id
              ? { ...i, status: "success", progress: 100, message: `+${res.added_chunks} chunks` }
              : i
          )
        );
        await loadDocs();
        onRefresh();
      } catch (e) {
        setUploadQueue((prev) =>
          prev.map((i) =>
            i.id === item.id
              ? { ...i, status: "error", message: e instanceof Error ? e.message : "上传失败" }
              : i
          )
        );
      }
    }
  };

  const removeUploadItem = (id: string) => {
    setUploadQueue((prev) => prev.filter((i) => i.id !== id));
  };

  const handleClearDocs = async () => {
    if (!window.confirm(`确定要清空 "${kb.name}" 中的所有文档吗？`)) return;
    try {
      await clearKbDocuments(kb.name);
      await loadDocs();
      onRefresh();
    } catch (e) {
      console.error("Clear docs error:", e);
    }
  };

  const statusIcon = (status: UploadFileItem["status"]) => {
    switch (status) {
      case "uploading":
        return <Loader2 size={14} style={{ animation: "spin 1s linear infinite", color: "#10a37f" }} />;
      case "success":
        return <CheckCircle size={14} style={{ color: "#10a37f" }} />;
      case "error":
        return <AlertCircle size={14} style={{ color: "#ef4444" }} />;
      default:
        return <div style={{ width: 14, height: 14, borderRadius: "50%", border: "2px solid #e5e5e5" }} />;
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* KB Header */}
      <div
        style={{
          padding: "12px 20px",
          borderBottom: "1px solid #e5e5e5",
          backgroundColor: "#ffffff",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button
            onClick={onBack}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
              fontSize: 13,
              color: "#666666",
              background: "transparent",
              border: "none",
              cursor: "pointer",
            }}
            type="button"
          >
            <Database size={14} />
            知识库
          </button>
          <span style={{ color: "#cccccc" }}>/</span>
          <span style={{ fontSize: 14, fontWeight: 600, color: "#1a1a1a" }}>{kb.name}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 12, color: "#666666" }}>
          <span style={{ display: "flex", alignItems: "center", gap: 4, padding: "4px 10px", borderRadius: 12, backgroundColor: "#f5f5f5" }}>
            <Database size={12} />
            {kb.embedding_model || "默认模型"}
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: 4, padding: "4px 10px", borderRadius: 12, backgroundColor: "#f5f5f5" }}>
            <CheckCircle size={12} />
            {kb.rerank_model || "默认重排"}
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 4,
          padding: "8px 20px",
          borderBottom: "1px solid #e5e5e5",
          backgroundColor: "#fafafa",
        }}
      >
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "6px 14px",
              borderRadius: 8,
              border: "none",
              fontSize: 13,
              cursor: "pointer",
              backgroundColor: activeTab === tab.key ? "#ffffff" : "transparent",
              color: activeTab === tab.key ? "#10a37f" : "#666666",
              boxShadow: activeTab === tab.key ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
              fontWeight: activeTab === tab.key ? 500 : 400,
            }}
            type="button"
          >
            {tab.icon}
            {tab.label}
            {tab.key === "files" && documents.length > 0 && (
              <span
                style={{
                  fontSize: 10,
                  padding: "1px 6px",
                  borderRadius: 10,
                  backgroundColor: "#10a37f",
                  color: "#ffffff",
                  marginLeft: 2,
                }}
              >
                {documents.length}
              </span>
            )}
          </button>
        ))}
        <div style={{ flex: 1 }} />
        <button
          onClick={() => fileInputRef.current?.click()}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "6px 14px",
            borderRadius: 8,
            border: "none",
            fontSize: 13,
            cursor: "pointer",
            backgroundColor: "#10a37f",
            color: "#ffffff",
          }}
          type="button"
        >
          <Plus size={14} />
          添加文件
        </button>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          style={{ display: "none" }}
          onChange={handleFileSelect}
        />
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: "auto", padding: "16px 20px" }}>
        {activeTab === "files" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {/* Upload Drop Zone */}
            <div
              onDrop={handleDrop}
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={(e) => {
                e.preventDefault();
                setDragOver(false);
              }}
              onClick={() => fileInputRef.current?.click()}
              style={{
                border: `2px dashed ${dragOver ? "#10a37f" : "#d0d0d0"}`,
                borderRadius: 12,
                padding: "32px 24px",
                textAlign: "center",
                cursor: "pointer",
                backgroundColor: dragOver ? "rgba(16, 163, 127, 0.03)" : "#fafafa",
                transition: "all 0.2s",
              }}
            >
              <Upload size={28} style={{ color: "#999999", marginBottom: 8 }} />
              <p style={{ fontSize: 14, color: "#1a1a1a", margin: 0 }}>拖拽文件到这里</p>
              <p style={{ fontSize: 12, color: "#999999", margin: "4px 0 0" }}>
                支持 TXT, MD, HTML, PDF, DOCX, PPTX, XLSX, EPUB... 格式
              </p>
            </div>

            {/* Upload Queue */}
            {uploadQueue.length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <p style={{ fontSize: 13, fontWeight: 500, color: "#1a1a1a", margin: 0 }}>上传队列</p>
                {uploadQueue.map((item) => (
                  <div
                    key={item.id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      padding: "10px 14px",
                      borderRadius: 8,
                      backgroundColor: "#ffffff",
                      border: "1px solid #e5e5e5",
                    }}
                  >
                    <FileText size={16} style={{ color: "#666666", flexShrink: 0 }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <p
                        style={{
                          fontSize: 13,
                          color: "#1a1a1a",
                          margin: 0,
                          whiteSpace: "nowrap",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                        }}
                      >
                        {item.file.name}
                      </p>
                      <p style={{ fontSize: 11, color: "#999999", margin: "2px 0 0" }}>
                        {(item.file.size / 1024).toFixed(1)} KB
                        {item.message && (
                          <span
                            style={{
                              marginLeft: 8,
                              color: item.status === "error" ? "#ef4444" : "#10a37f",
                            }}
                          >
                            {item.message}
                          </span>
                        )}
                      </p>
                    </div>
                    {statusIcon(item.status)}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        removeUploadItem(item.id);
                      }}
                      style={{
                        display: "flex",
                        height: 24,
                        width: 24,
                        alignItems: "center",
                        justifyContent: "center",
                        borderRadius: 4,
                        border: "none",
                        background: "transparent",
                        cursor: "pointer",
                        color: "#999999",
                      }}
                      type="button"
                    >
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Document List */}
            <div>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: 10,
                }}
              >
                <p style={{ fontSize: 13, fontWeight: 500, color: "#1a1a1a", margin: 0 }}>
                  已上传文档 ({documents.length})
                </p>
                {documents.length > 0 && (
                  <button
                    onClick={handleClearDocs}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                      fontSize: 12,
                      color: "#ef4444",
                      background: "transparent",
                      border: "none",
                      cursor: "pointer",
                    }}
                    type="button"
                  >
                    <Trash2 size={12} />
                    清空
                  </button>
                )}
              </div>

              {docsLoading ? (
                <div style={{ textAlign: "center", padding: 30, color: "#999999" }}>
                  <Loader2 size={20} style={{ animation: "spin 1s linear infinite" }} />
                </div>
              ) : documents.length === 0 ? (
                <div style={{ textAlign: "center", padding: 40, color: "#999999" }}>
                  <p style={{ fontSize: 13 }}>暂无数据</p>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {documents.map((doc, i) => (
                    <div
                      key={i}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 10,
                        padding: "10px 14px",
                        borderRadius: 8,
                        backgroundColor: "#ffffff",
                        border: "1px solid #e5e5e5",
                      }}
                    >
                      <FileText size={16} style={{ color: "#10a37f", flexShrink: 0 }} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <p
                          style={{
                            fontSize: 13,
                            color: "#1a1a1a",
                            margin: 0,
                            whiteSpace: "nowrap",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                          }}
                        >
                          {doc.source}
                        </p>
                        <p style={{ fontSize: 11, color: "#999999", margin: "2px 0 0" }}>
                          类型: {doc.type} · 分块数: {doc.chunk_count}
                        </p>
                      </div>
                      <CheckCircle size={14} style={{ color: "#10a37f", flexShrink: 0 }} />
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab !== "files" && (
          <div style={{ textAlign: "center", padding: 60, color: "#999999" }}>
            <p style={{ fontSize: 14 }}>该功能即将上线</p>
          </div>
        )}
      </div>
    </div>
  );
}
