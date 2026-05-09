"use client";

import { useMemo } from "react";
import type { PetAction } from "./PixelPet";
import type { Message } from "@/lib/store";

// 将 AI 执行状态映射到宠物动作
export function usePetAction(
  messages: Message[],
  isStreaming: boolean,
  hasError: boolean = false
): PetAction {
  return useMemo(() => {
    // 如果有错误，显示失败
    if (hasError) {
      return "failed";
    }

    // 如果正在流式输出，显示思考中
    if (isStreaming) {
      return "thinking";
    }

    // 没有消息时显示空闲
    if (messages.length === 0) {
      return "idle";
    }

    // 获取最后一条消息
    const lastMessage = messages[messages.length - 1];

    // 如果最后一条是用户消息，等待 AI 回复
    if (lastMessage.role === "user") {
      return "inputting";
    }

    // 如果最后一条是 AI 消息
    if (lastMessage.role === "assistant") {
      // 检查是否有工具调用
      if (lastMessage.toolCalls && lastMessage.toolCalls.length > 0) {
        const lastTool = lastMessage.toolCalls[lastMessage.toolCalls.length - 1];
        // 如果工具没有输出，表示正在执行
        if (!lastTool.output) {
          return "executing";
        }
      }

      // 检查内容中是否包含成功/失败关键词
      const content = lastMessage.content.toLowerCase();
      if (content.includes("成功") || content.includes("完成") || content.includes("done")) {
        return "success";
      }
      if (content.includes("失败") || content.includes("错误") || content.includes("error")) {
        return "failed";
      }
      if (content.includes("阻塞") || content.includes("timeout")) {
        return "blocked";
      }

      // 默认显示成功（有回复内容）
      if (content.length > 0) {
        return "success";
      }

      return "idle";
    }

    return "idle";
  }, [messages, isStreaming, hasError]);
}
