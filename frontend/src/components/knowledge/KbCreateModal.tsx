"use client";

import { useState } from "react";
import { X, ChevronDown, ChevronUp, Info } from "lucide-react";

export type KbConfig = {
  name: string;
  description: string;
  embeddingModel: string;
  rerankModel: string;
  embeddingDimension: number;
  retrieveTopK: number;
  docProcessor: string;
  chunkSize: number;
  chunkOverlap: number;
  similarityThreshold: number;
};

const EMBEDDING_MODELS = [
  { value: "bge-large-zh", label: "Bge Large Zh", provider: "AiHubMix" },
  { value: "bge-m3", label: "Bge M3", provider: "AiHubMix" },
  { value: "text-embedding-3-small", label: "Text Embedding 3 Small", provider: "OpenAI" },
  { value: "text-embedding-3-large", label: "Text Embedding 3 Large", provider: "OpenAI" },
  { value: "e5-large-v2", label: "E5 Large V2", provider: "HuggingFace" },
];

const RERANK_MODELS = [
  { value: "qwen3-reranker-8b", label: "Qwen3 Reranker 8B", provider: "AiHubMix" },
  { value: "bge-reranker-large", label: "Bge Reranker Large", provider: "AiHubMix" },
  { value: "cohere-rerank", label: "Cohere Rerank", provider: "Cohere" },
  { value: "none", label: "不使用重排序", provider: "" },
];

const DOC_PROCESSORS = [
  { value: "mineru", label: "MinerU" },
  { value: "unstructured", label: "Unstructured" },
  { value: "pypdf", label: "PyPDF (轻量)" },
  { value: "fitz", label: "PyMuPDF (轻量)" },
];

export function KbCreateModal({
  onClose,
  onConfirm,
}: {
  onClose: () => void;
  onConfirm: (config: KbConfig) => void;
}) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [config, setConfig] = useState<KbConfig>({
    name: "",
    description: "",
    embeddingModel: "bge-large-zh",
    rerankModel: "qwen3-reranker-8b",
    embeddingDimension: 1024,
    retrieveTopK: 5,
    docProcessor: "mineru",
    chunkSize: 512,
    chunkOverlap: 50,
    similarityThreshold: 0.7,
  });

  const update = <K extends keyof KbConfig>(key: K, value: KbConfig[K]) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
  };

  const handleConfirm = () => {
    if (!config.name.trim()) return;
    onConfirm(config);
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 10000,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundColor: "rgba(0,0,0,0.4)",
          backdropFilter: "blur(4px)",
        }}
        onClick={onClose}
      />
      <div
        style={{
          position: "relative",
          zIndex: 10,
          width: 520,
          maxHeight: "90vh",
          backgroundColor: "#ffffff",
          borderRadius: 16,
          boxShadow: "0 20px 60px rgba(0,0,0,0.15)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "16px 20px",
            borderBottom: "1px solid #e5e5e5",
          }}
        >
          <span style={{ fontSize: 16, fontWeight: 600, color: "#1a1a1a" }}>添加知识库</span>
          <button
            onClick={onClose}
            style={{
              display: "flex",
              height: 32,
              width: 32,
              alignItems: "center",
              justifyContent: "center",
              borderRadius: 8,
              border: "none",
              background: "transparent",
              cursor: "pointer",
              color: "#999999",
            }}
            type="button"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
            {/* Name */}
            <Field label="名称">
              <input
                type="text"
                value={config.name}
                onChange={(e) => update("name", e.target.value)}
                placeholder="请输入知识库名称"
                style={inputStyle}
              />
            </Field>

            {/* Embedding Model */}
            <Field label="嵌入模型" tooltip="用于将文档转换为向量表示的模型">
              <select
                value={config.embeddingModel}
                onChange={(e) => update("embeddingModel", e.target.value)}
                style={selectStyle}
              >
                {EMBEDDING_MODELS.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </select>
            </Field>

            {/* Embedding Dimension */}
            <Field label="嵌入维度" tooltip="向量维度，影响存储和检索精度">
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input
                  type="number"
                  value={config.embeddingDimension}
                  onChange={(e) => update("embeddingDimension", Number(e.target.value))}
                  style={{ ...inputStyle, width: 120 }}
                />
                <button
                  onClick={() => update("embeddingDimension", 1024)}
                  style={{
                    padding: "6px 12px",
                    borderRadius: 6,
                    border: "1px solid #e5e5e5",
                    background: "#f5f5f5",
                    fontSize: 12,
                    cursor: "pointer",
                    color: "#666666",
                  }}
                  type="button"
                >
                  重置
                </button>
              </div>
            </Field>

            {/* Retrieve Top K */}
            <Field label="请求文档片段数量" tooltip="每次检索返回的文档片段数量">
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <input
                  type="range"
                  min={1}
                  max={50}
                  value={config.retrieveTopK}
                  onChange={(e) => update("retrieveTopK", Number(e.target.value))}
                  style={{ flex: 1 }}
                />
                <span style={{ fontSize: 14, fontWeight: 500, color: "#10a37f", minWidth: 28 }}>
                  {config.retrieveTopK}
                </span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#999999", marginTop: 2 }}>
                <span>1</span>
                <span>默认</span>
                <span>50</span>
              </div>
            </Field>

            {/* Advanced Settings */}
            <div
              style={{
                borderTop: "1px solid #e5e5e5",
                paddingTop: 12,
              }}
            >
              <button
                onClick={() => setShowAdvanced(!showAdvanced)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  fontSize: 13,
                  fontWeight: 500,
                  color: "#1a1a1a",
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  padding: 0,
                }}
                type="button"
              >
                {showAdvanced ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                高级设置
              </button>

              {showAdvanced && (
                <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 16 }}>
                  {/* Doc Processor */}
                  <Field label="文档处理" tooltip="用于解析 PDF、Word 等复杂文档的引擎">
                    <select
                      value={config.docProcessor}
                      onChange={(e) => update("docProcessor", e.target.value)}
                      style={selectStyle}
                    >
                      {DOC_PROCESSORS.map((p) => (
                        <option key={p.value} value={p.value}>
                          {p.label}
                        </option>
                      ))}
                    </select>
                  </Field>

                  {/* Rerank Model */}
                  <Field label="重排模型" tooltip="对检索结果进行重排序，提升相关性">
                    <select
                      value={config.rerankModel}
                      onChange={(e) => update("rerankModel", e.target.value)}
                      style={selectStyle}
                    >
                      {RERANK_MODELS.map((m) => (
                        <option key={m.value} value={m.value}>
                          {m.label}
                        </option>
                      ))}
                    </select>
                  </Field>

                  {/* Chunk Size */}
                  <Field label="分段大小" tooltip="每个文档片段的最大字符数">
                    <input
                      type="number"
                      value={config.chunkSize}
                      onChange={(e) => update("chunkSize", Number(e.target.value))}
                      placeholder="默认值（不建议修改）"
                      style={inputStyle}
                    />
                  </Field>

                  {/* Chunk Overlap */}
                  <Field label="重叠大小" tooltip="相邻片段之间的重叠字符数">
                    <input
                      type="number"
                      value={config.chunkOverlap}
                      onChange={(e) => update("chunkOverlap", Number(e.target.value))}
                      placeholder="默认值（不建议修改）"
                      style={inputStyle}
                    />
                  </Field>

                  {/* Similarity Threshold */}
                  <Field label="匹配度阈值" tooltip="相似度低于此值的检索结果将被过滤">
                    <input
                      type="number"
                      step={0.05}
                      min={0}
                      max={1}
                      value={config.similarityThreshold}
                      onChange={(e) => update("similarityThreshold", Number(e.target.value))}
                      style={inputStyle}
                    />
                  </Field>

                  <div
                    style={{
                      padding: "10px 14px",
                      borderRadius: 8,
                      backgroundColor: "#fef9e7",
                      border: "1px solid #f9e79f",
                      fontSize: 12,
                      color: "#b7950b",
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                    }}
                  >
                    <Info size={14} />
                    分段大小和重叠大小修改只针对新添加的内容有效
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            gap: 10,
            padding: "14px 20px",
            borderTop: "1px solid #e5e5e5",
          }}
        >
          <button
            onClick={onClose}
            style={{
              padding: "8px 20px",
              borderRadius: 8,
              border: "1px solid #e5e5e5",
              background: "#ffffff",
              fontSize: 14,
              cursor: "pointer",
              color: "#666666",
            }}
            type="button"
          >
            取消
          </button>
          <button
            onClick={handleConfirm}
            disabled={!config.name.trim()}
            style={{
              padding: "8px 20px",
              borderRadius: 8,
              border: "none",
              background: config.name.trim() ? "#10a37f" : "#cccccc",
              fontSize: 14,
              cursor: config.name.trim() ? "pointer" : "not-allowed",
              color: "#ffffff",
            }}
            type="button"
          >
            确认
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  tooltip,
  children,
}: {
  label: string;
  tooltip?: string;
  children: React.ReactNode;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
        <span style={{ fontSize: 13, fontWeight: 500, color: "#1a1a1a" }}>{label}</span>
        {tooltip && (
          <span title={tooltip} style={{ color: "#999999", cursor: "help", display: "flex" }}>
            <Info size={13} />
          </span>
        )}
      </div>
      {children}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  padding: "9px 12px",
  borderRadius: 8,
  border: "1px solid #e5e5e5",
  fontSize: 14,
  outline: "none",
  width: "100%",
  boxSizing: "border-box",
  color: "#1a1a1a",
};

const selectStyle: React.CSSProperties = {
  padding: "9px 12px",
  borderRadius: 8,
  border: "1px solid #e5e5e5",
  fontSize: 14,
  outline: "none",
  width: "100%",
  boxSizing: "border-box",
  color: "#1a1a1a",
  backgroundColor: "#ffffff",
  cursor: "pointer",
};
