"use client";

import { useState } from "react";
import {
  X,
  Plus,
  Wrench,
  Check,
  Download,
  Trash2,
  FileText,
  Zap,
} from "lucide-react";

export type SkillItem = {
  id: string;
  name: string;
  description: string;
  agent: string;
  installed: boolean;
  tools: string[];
  content?: string;
  author?: string;
  version?: string;
};

// 初始为空数组，实际数据从后端 API 加载
const MARKET_SKILLS: SkillItem[] = [];

export function SkillMarketPanel({ onClose }: { onClose: () => void }) {
  const [skills, setSkills] = useState<SkillItem[]>(MARKET_SKILLS);
  const [filter, setFilter] = useState<"all" | "installed" | "available">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [previewSkill, setPreviewSkill] = useState<SkillItem | null>(null);

  const [formData, setFormData] = useState({
    name: "",
    description: "",
    agent: "chat",
    tools: "",
  });

  const handleInstall = (id: string) => {
    setSkills((prev) =>
      prev.map((s) => (s.id === id ? { ...s, installed: true } : s))
    );
  };

  const handleUninstall = (id: string) => {
    setSkills((prev) =>
      prev.map((s) => (s.id === id ? { ...s, installed: false } : s))
    );
  };

  const handleCreate = () => {
    if (!formData.name.trim()) return;

    const newSkill: SkillItem = {
      id: `custom-${Date.now()}`,
      name: formData.name,
      description: formData.description,
      agent: formData.agent,
      installed: true,
      tools: formData.tools
        ? formData.tools.split(",").map((s) => s.trim())
        : [],
      author: "User",
      version: "0.1.0",
    };

    setSkills((prev) => [newSkill, ...prev]);
    setShowCreateModal(false);
    setFormData({ name: "", description: "", agent: "chat", tools: "" });
  };

  const filteredSkills = skills.filter((s) => {
    if (filter === "installed") return s.installed;
    if (filter === "available") return !s.installed;
    return true;
  }).filter((s) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      s.name.toLowerCase().includes(q) ||
      s.description.toLowerCase().includes(q) ||
      s.agent.toLowerCase().includes(q)
    );
  });

  const agentColors: Record<string, string> = {
    info: "#3b82f6",
    chat: "#10a37f",
    task: "#f59e0b",
    data: "#8b5cf6",
    learning: "#ec4899",
    health: "#ef4444",
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        backgroundColor: "#ffffff",
        borderRadius: 12,
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
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Zap size={20} style={{ color: "#f59e0b" }} />
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: "#1a1a1a" }}>
            Skill 技能市场
          </h2>
        </div>
        <button
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: 28,
            height: 28,
            borderRadius: 6,
            border: "none",
            background: "transparent",
            cursor: "pointer",
            color: "#999999",
          }}
          onClick={onClose}
          type="button"
        >
          <X size={16} />
        </button>
      </div>

      {/* Toolbar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "12px 20px",
          borderBottom: "1px solid #e5e5e5",
        }}
      >
        <div
          style={{
            display: "flex",
            gap: 4,
            backgroundColor: "#f5f5f5",
            borderRadius: 6,
            padding: 2,
          }}
        >
          {(["all", "installed", "available"] as const).map((f) => (
            <button
              key={f}
              style={{
                padding: "6px 14px",
                borderRadius: 5,
                border: "none",
                backgroundColor: filter === f ? "#ffffff" : "transparent",
                color: filter === f ? "#1a1a1a" : "#666666",
                fontSize: 12,
                fontWeight: 500,
                cursor: "pointer",
                boxShadow: filter === f ? "0 1px 2px rgba(0,0,0,0.05)" : "none",
              }}
              onClick={() => setFilter(f)}
              type="button"
            >
              {f === "all" ? "全部" : f === "installed" ? "已安装" : "可安装"}
            </button>
          ))}
        </div>

        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="搜索技能..."
          style={{
            flex: 1,
            padding: "6px 12px",
            borderRadius: 6,
            border: "1px solid #e5e5e5",
            fontSize: 13,
            outline: "none",
            maxWidth: 280,
          }}
        />

        <button
          style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
            padding: "6px 12px",
            borderRadius: 6,
            border: "1px solid #f59e0b",
            backgroundColor: "#f59e0b",
            color: "#ffffff",
            fontSize: 12,
            cursor: "pointer",
          }}
          onClick={() => setShowCreateModal(true)}
          type="button"
        >
          <Plus size={14} />
          新建 Skill
        </button>
      </div>

      {/* Skill Grid */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: 20,
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          gap: 16,
        }}
      >
        {filteredSkills.length === 0 ? (
          <div
            style={{
              gridColumn: "1 / -1",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              padding: 60,
              color: "#999999",
            }}
          >
            <Wrench size={48} style={{ marginBottom: 16, opacity: 0.3 }} />
            <p style={{ fontSize: 14, margin: 0 }}>
              {filter === "installed"
                ? "暂无已安装的技能"
                : filter === "available"
                ? "暂无可安装的技能"
                : "暂无技能，点击右上角新建"}
            </p>
          </div>
        ) : (
          filteredSkills.map((skill) => (
          <div
            key={skill.id}
            style={{
              border: "1px solid #e5e5e5",
              borderRadius: 10,
              padding: 16,
              backgroundColor: skill.installed ? "#fafafa" : "#ffffff",
              transition: "box-shadow 0.15s",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.boxShadow = "0 2px 8px rgba(0,0,0,0.08)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.boxShadow = "none";
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "flex-start",
                justifyContent: "space-between",
                marginBottom: 10,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Wrench
                  size={16}
                  style={{
                    color: agentColors[skill.agent] || "#666666",
                  }}
                />
                <h3
                  style={{
                    margin: 0,
                    fontSize: 14,
                    fontWeight: 600,
                    color: "#1a1a1a",
                  }}
                >
                  {skill.name}
                </h3>
              </div>
              {skill.installed && (
                <Check size={14} style={{ color: "#10a37f" }} />
              )}
            </div>

            <p
              style={{
                margin: "0 0 10px",
                fontSize: 12,
                color: "#666666",
                lineHeight: 1.5,
                display: "-webkit-box",
                WebkitLineClamp: 2,
                WebkitBoxOrient: "vertical",
                overflow: "hidden",
              }}
            >
              {skill.description}
            </p>

            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                marginBottom: 10,
                flexWrap: "wrap",
              }}
            >
              <span
                style={{
                  padding: "2px 8px",
                  borderRadius: 4,
                  fontSize: 11,
                  backgroundColor:
                    agentColors[skill.agent] || "#666666" + "20",
                  color: agentColors[skill.agent] || "#666666",
                }}
              >
                {skill.agent}
              </span>
              {skill.tools.map((tool) => (
                <span
                  key={tool}
                  style={{
                    padding: "2px 8px",
                    borderRadius: 4,
                    fontSize: 11,
                    backgroundColor: "#f0f0f0",
                    color: "#666666",
                  }}
                >
                  {tool}
                </span>
              ))}
            </div>

            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <span style={{ fontSize: 11, color: "#999999" }}>
                {skill.author} · v{skill.version}
              </span>
              <div style={{ display: "flex", gap: 6 }}>
                <button
                  style={{
                    padding: "4px 8px",
                    borderRadius: 4,
                    border: "1px solid #e5e5e5",
                    backgroundColor: "#ffffff",
                    color: "#666666",
                    fontSize: 11,
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 3,
                  }}
                  onClick={() => setPreviewSkill(skill)}
                  type="button"
                >
                  <FileText size={11} />
                  预览
                </button>
                {skill.installed ? (
                  <button
                    style={{
                      padding: "4px 8px",
                      borderRadius: 4,
                      border: "1px solid #ef4444",
                      backgroundColor: "#fef2f2",
                      color: "#ef4444",
                      fontSize: 11,
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 3,
                    }}
                    onClick={() => handleUninstall(skill.id)}
                    type="button"
                  >
                    <Trash2 size={11} />
                    卸载
                  </button>
                ) : (
                  <button
                    style={{
                      padding: "4px 8px",
                      borderRadius: 4,
                      border: "1px solid #10a37f",
                      backgroundColor: "#f0fdf4",
                      color: "#10a37f",
                      fontSize: 11,
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 3,
                    }}
                    onClick={() => handleInstall(skill.id)}
                    type="button"
                  >
                    <Download size={11} />
                    安装
                  </button>
                )}
              </div>
            </div>
          </div>
        ))
        )}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 10000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: "rgba(0, 0, 0, 0.4)",
          }}
          onClick={() => setShowCreateModal(false)}
        >
          <div
            style={{
              backgroundColor: "#ffffff",
              borderRadius: 12,
              padding: 24,
              width: 480,
              maxWidth: "90vw",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ margin: "0 0 16px", fontSize: 16, fontWeight: 600 }}>
              新建 Skill
            </h3>

            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div>
                <label style={{ fontSize: 12, color: "#666666", fontWeight: 500 }}>
                  名称
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) =>
                    setFormData({ ...formData, name: e.target.value })
                  }
                  placeholder="例如: 代码审查"
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    marginTop: 4,
                    borderRadius: 6,
                    border: "1px solid #e5e5e5",
                    fontSize: 13,
                    outline: "none",
                  }}
                />
              </div>

              <div>
                <label style={{ fontSize: 12, color: "#666666", fontWeight: 500 }}>
                  描述
                </label>
                <textarea
                  value={formData.description}
                  onChange={(e) =>
                    setFormData({ ...formData, description: e.target.value })
                  }
                  placeholder="描述这个 Skill 的功能..."
                  rows={3}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    marginTop: 4,
                    borderRadius: 6,
                    border: "1px solid #e5e5e5",
                    fontSize: 13,
                    outline: "none",
                    resize: "vertical",
                  }}
                />
              </div>

              <div>
                <label style={{ fontSize: 12, color: "#666666", fontWeight: 500 }}>
                  绑定 Agent
                </label>
                <select
                  value={formData.agent}
                  onChange={(e) =>
                    setFormData({ ...formData, agent: e.target.value })
                  }
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    marginTop: 4,
                    borderRadius: 6,
                    border: "1px solid #e5e5e5",
                    fontSize: 13,
                    outline: "none",
                    backgroundColor: "#ffffff",
                  }}
                >
                  <option value="chat">Chat (对话)</option>
                  <option value="info">Info (信息查询)</option>
                  <option value="task">Task (任务)</option>
                  <option value="data">Data (数据分析)</option>
                  <option value="learning">Learning (学习)</option>
                  <option value="health">Health (健康)</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: 12, color: "#666666", fontWeight: 500 }}>
                  工具列表 (逗号分隔)
                </label>
                <input
                  type="text"
                  value={formData.tools}
                  onChange={(e) =>
                    setFormData({ ...formData, tools: e.target.value })
                  }
                  placeholder="例如: tavily, think, analyze_code"
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    marginTop: 4,
                    borderRadius: 6,
                    border: "1px solid #e5e5e5",
                    fontSize: 13,
                    outline: "none",
                  }}
                />
              </div>
            </div>

            <div
              style={{
                display: "flex",
                gap: 8,
                justifyContent: "flex-end",
                marginTop: 20,
              }}
            >
              <button
                style={{
                  padding: "8px 16px",
                  borderRadius: 6,
                  border: "1px solid #e5e5e5",
                  backgroundColor: "#ffffff",
                  color: "#666666",
                  fontSize: 13,
                  cursor: "pointer",
                }}
                onClick={() => setShowCreateModal(false)}
                type="button"
              >
                取消
              </button>
              <button
                style={{
                  padding: "8px 16px",
                  borderRadius: 6,
                  border: "none",
                  backgroundColor: "#f59e0b",
                  color: "#ffffff",
                  fontSize: 13,
                  cursor: "pointer",
                }}
                onClick={handleCreate}
                type="button"
              >
                创建
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Preview Modal */}
      {previewSkill && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 10000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: "rgba(0, 0, 0, 0.4)",
          }}
          onClick={() => setPreviewSkill(null)}
        >
          <div
            style={{
              backgroundColor: "#ffffff",
              borderRadius: 12,
              padding: 24,
              width: 480,
              maxWidth: "90vw",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ margin: "0 0 12px", fontSize: 16, fontWeight: 600 }}>
              {previewSkill.name}
            </h3>
            <p style={{ margin: "0 0 16px", fontSize: 13, color: "#666666" }}>
              {previewSkill.description}
            </p>

            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 12, color: "#999999", marginBottom: 4 }}>
                绑定 Agent
              </div>
              <span
                style={{
                  padding: "4px 10px",
                  borderRadius: 4,
                  fontSize: 12,
                  backgroundColor:
                    (agentColors[previewSkill.agent] || "#666") + "15",
                  color: agentColors[previewSkill.agent] || "#666",
                }}
              >
                {previewSkill.agent}
              </span>
            </div>

            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 12, color: "#999999", marginBottom: 4 }}>
                包含工具
              </div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {previewSkill.tools.map((tool) => (
                  <span
                    key={tool}
                    style={{
                      padding: "4px 10px",
                      borderRadius: 4,
                      fontSize: 12,
                      backgroundColor: "#f0f0f0",
                      color: "#666666",
                    }}
                  >
                    {tool}
                  </span>
                ))}
              </div>
            </div>

            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 12, color: "#999999", marginBottom: 4 }}>
                元信息
              </div>
              <div style={{ fontSize: 12, color: "#666666" }}>
                作者: {previewSkill.author} · 版本: {previewSkill.version} ·
                状态:{" "}
                {previewSkill.installed ? "已安装" : "未安装"}
              </div>
            </div>

            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button
                style={{
                  padding: "8px 16px",
                  borderRadius: 6,
                  border: "1px solid #e5e5e5",
                  backgroundColor: "#ffffff",
                  color: "#666666",
                  fontSize: 13,
                  cursor: "pointer",
                }}
                onClick={() => setPreviewSkill(null)}
                type="button"
              >
                关闭
              </button>
              {previewSkill.installed ? (
                <button
                  style={{
                    padding: "8px 16px",
                    borderRadius: 6,
                    border: "1px solid #ef4444",
                    backgroundColor: "#fef2f2",
                    color: "#ef4444",
                    fontSize: 13,
                    cursor: "pointer",
                  }}
                  onClick={() => {
                    handleUninstall(previewSkill.id);
                    setPreviewSkill(null);
                  }}
                  type="button"
                >
                  卸载
                </button>
              ) : (
                <button
                  style={{
                    padding: "8px 16px",
                    borderRadius: 6,
                    border: "none",
                    backgroundColor: "#10a37f",
                    color: "#ffffff",
                    fontSize: 13,
                    cursor: "pointer",
                  }}
                  onClick={() => {
                    handleInstall(previewSkill.id);
                    setPreviewSkill(null);
                  }}
                  type="button"
                >
                  安装
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
