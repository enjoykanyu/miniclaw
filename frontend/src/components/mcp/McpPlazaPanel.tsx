"use client";

import { useState } from "react";
import {
  X,
  Plus,
  Server,
  Check,
  AlertCircle,
  Settings,
  Trash2,
  RefreshCw,
} from "lucide-react";

export type McpServer = {
  id: string;
  name: string;
  description: string;
  type: "builtin" | "custom";
  status: "connected" | "disconnected" | "error";
  config?: {
    command?: string;
    args?: string[];
    url?: string;
    env?: Record<string, string>;
  };
  tags?: string[];
};

// 初始为空数组，实际数据从后端 API 加载
const BUILTIN_SERVERS: McpServer[] = [];

export function McpPlazaPanel({ onClose }: { onClose: () => void }) {
  const [activeTab, setActiveTab] = useState<"builtin" | "custom">("builtin");
  const [servers, setServers] = useState<McpServer[]>(BUILTIN_SERVERS);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingServer, setEditingServer] = useState<McpServer | null>(null);

  const [formData, setFormData] = useState({
    name: "",
    description: "",
    command: "",
    args: "",
    url: "",
  });

  const handleAdd = () => {
    setFormData({ name: "", description: "", command: "", args: "", url: "" });
    setEditingServer(null);
    setShowAddModal(true);
  };

  const handleEdit = (server: McpServer) => {
    setFormData({
      name: server.name,
      description: server.description,
      command: server.config?.command || "",
      args: server.config?.args?.join(", ") || "",
      url: server.config?.url || "",
    });
    setEditingServer(server);
    setShowAddModal(true);
  };

  const handleSave = () => {
    if (!formData.name.trim()) return;

    const newServer: McpServer = {
      id: editingServer?.id || `custom-${Date.now()}`,
      name: formData.name,
      description: formData.description,
      type: "custom",
      status: "disconnected",
      config: {
        command: formData.command || undefined,
        args: formData.args ? formData.args.split(",").map((s) => s.trim()) : undefined,
        url: formData.url || undefined,
      },
    };

    if (editingServer) {
      setServers((prev) =>
        prev.map((s) => (s.id === editingServer.id ? newServer : s))
      );
    } else {
      setServers((prev) => [...prev, newServer]);
    }
    setShowAddModal(false);
  };

  const handleDelete = (id: string) => {
    if (confirm("确定要删除这个 MCP 服务器吗？")) {
      setServers((prev) => prev.filter((s) => s.id !== id));
    }
  };

  const toggleStatus = (id: string) => {
    setServers((prev) =>
      prev.map((s) =>
        s.id === id
          ? {
              ...s,
              status:
                s.status === "connected" ? "disconnected" : "connected",
            }
          : s
      )
    );
  };

  const filteredServers = servers.filter((s) =>
    activeTab === "builtin" ? s.type === "builtin" : s.type === "custom"
  );

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
          <Server size={20} style={{ color: "#10a37f" }} />
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: "#1a1a1a" }}>
            MCP 服务器
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

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          gap: 4,
          padding: "12px 20px 0",
          borderBottom: "1px solid #e5e5e5",
        }}
      >
        {(["builtin", "custom"] as const).map((tab) => (
          <button
            key={tab}
            style={{
              padding: "8px 16px",
              borderRadius: "6px 6px 0 0",
              border: "none",
              borderBottom:
                activeTab === tab ? "2px solid #10a37f" : "2px solid transparent",
              background: "transparent",
              color: activeTab === tab ? "#10a37f" : "#666666",
              fontSize: 13,
              fontWeight: 500,
              cursor: "pointer",
            }}
            onClick={() => setActiveTab(tab)}
            type="button"
          >
            {tab === "builtin" ? "内置服务器" : "自定义"}
          </button>
        ))}
        <div style={{ flex: 1 }} />
        <button
          style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
            padding: "6px 12px",
            borderRadius: 6,
            border: "1px solid #10a37f",
            backgroundColor: "#10a37f",
            color: "#ffffff",
            fontSize: 12,
            cursor: "pointer",
          }}
          onClick={handleAdd}
          type="button"
        >
          <Plus size={14} />
          添加服务器
        </button>
      </div>

      {/* Server Grid */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: 20,
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
          gap: 16,
        }}
      >
        {filteredServers.length === 0 ? (
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
            <Server size={48} style={{ marginBottom: 16, opacity: 0.3 }} />
            <p style={{ fontSize: 14, margin: 0 }}>
              {activeTab === "builtin"
                ? "暂无内置服务器，请从后端配置加载"
                : "暂无自定义服务器，点击右上角添加"}
            </p>
          </div>
        ) : (
          filteredServers.map((server) => (
          <div
            key={server.id}
            style={{
              border: "1px solid #e5e5e5",
              borderRadius: 10,
              padding: 16,
              backgroundColor: "#fafafa",
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
                marginBottom: 8,
              }}
            >
              <h3
                style={{
                  margin: 0,
                  fontSize: 14,
                  fontWeight: 600,
                  color: "#1a1a1a",
                }}
              >
                {server.name}
              </h3>
              <div style={{ display: "flex", gap: 4 }}>
                {server.status === "connected" && (
                  <Check size={14} style={{ color: "#10a37f" }} />
                )}
                {server.status === "error" && (
                  <AlertCircle size={14} style={{ color: "#ef4444" }} />
                )}
              </div>
            </div>

            <p
              style={{
                margin: "0 0 12px",
                fontSize: 12,
                color: "#666666",
                lineHeight: 1.5,
                display: "-webkit-box",
                WebkitLineClamp: 2,
                WebkitBoxOrient: "vertical",
                overflow: "hidden",
              }}
            >
              {server.description}
            </p>

            <div style={{ display: "flex", gap: 6, marginBottom: 12, flexWrap: "wrap" }}>
              {server.tags?.map((tag) => (
                <span
                  key={tag}
                  style={{
                    padding: "2px 8px",
                    borderRadius: 4,
                    fontSize: 11,
                    backgroundColor:
                      tag === "内置" ? "rgba(16, 163, 127, 0.1)" : "rgba(245, 158, 11, 0.1)",
                    color: tag === "内置" ? "#10a37f" : "#f59e0b",
                  }}
                >
                  {tag}
                </span>
              ))}
            </div>

            <div style={{ display: "flex", gap: 6 }}>
              <button
                style={{
                  flex: 1,
                  padding: "6px 0",
                  borderRadius: 6,
                  border: "1px solid #e5e5e5",
                  backgroundColor: "#ffffff",
                  color: "#666666",
                  fontSize: 12,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 4,
                }}
                onClick={() => handleEdit(server)}
                type="button"
              >
                <Settings size={12} />
                配置
              </button>
              <button
                style={{
                  flex: 1,
                  padding: "6px 0",
                  borderRadius: 6,
                  border:
                    server.status === "connected"
                      ? "1px solid #ef4444"
                      : "1px solid #10a37f",
                  backgroundColor:
                    server.status === "connected" ? "#fef2f2" : "#f0fdf4",
                  color: server.status === "connected" ? "#ef4444" : "#10a37f",
                  fontSize: 12,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 4,
                }}
                onClick={() => toggleStatus(server.id)}
                type="button"
              >
                <RefreshCw size={12} />
                {server.status === "connected" ? "断开" : "连接"}
              </button>
              {server.type === "custom" && (
                <button
                  style={{
                    padding: "6px 8px",
                    borderRadius: 6,
                    border: "1px solid #e5e5e5",
                    backgroundColor: "#ffffff",
                    color: "#999999",
                    cursor: "pointer",
                  }}
                  onClick={() => handleDelete(server.id)}
                  type="button"
                >
                  <Trash2 size={12} />
                </button>
              )}
            </div>
          </div>
        ))
        )}
      </div>

      {/* Add/Edit Modal */}
      {showAddModal && (
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
          onClick={() => setShowAddModal(false)}
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
              {editingServer ? "编辑 MCP 服务器" : "添加 MCP 服务器"}
            </h3>

            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div>
                <label style={{ fontSize: 12, color: "#666666", fontWeight: 500 }}>
                  名称
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="例如: @my-org/custom-server"
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
                  placeholder="描述这个服务器的功能..."
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
                  命令 (STDIO 模式)
                </label>
                <input
                  type="text"
                  value={formData.command}
                  onChange={(e) => setFormData({ ...formData, command: e.target.value })}
                  placeholder="例如: npx"
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
                  参数
                </label>
                <input
                  type="text"
                  value={formData.args}
                  onChange={(e) => setFormData({ ...formData, args: e.target.value })}
                  placeholder="例如: -y, @modelcontextprotocol/server-filesystem"
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
                  URL (SSE/HTTP 模式)
                </label>
                <input
                  type="text"
                  value={formData.url}
                  onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                  placeholder="例如: http://localhost:3000/sse"
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
                onClick={() => setShowAddModal(false)}
                type="button"
              >
                取消
              </button>
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
                onClick={handleSave}
                type="button"
              >
                保存
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
