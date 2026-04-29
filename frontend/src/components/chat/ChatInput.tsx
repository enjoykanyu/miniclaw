"use client";

import { Send, Loader2 } from "lucide-react";
import { useState, useRef } from "react";

export function ChatInput({
  disabled,
  onSend
}: {
  disabled: boolean;
  onSend: (value: string) => Promise<void>;
}) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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

  return (
    <div style={{ borderTop: "1px solid #e5e5e5", backgroundColor: "#ffffff", padding: "12px 16px" }}>
      <div style={{ maxWidth: 768, margin: "0 auto" }}>
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
            placeholder="输入你的问题，按 Enter 发送，Shift+Enter 换行..."
            rows={1}
            value={value}
          />
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
