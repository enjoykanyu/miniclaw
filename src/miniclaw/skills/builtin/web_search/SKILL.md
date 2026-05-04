---
name: web_search
description: 当用户需要搜索实时信息时使用
agent: info        # 绑定到哪个 Agent
tools:             # 需要哪些工具
  - name: tavily
    condition: force_search  # 仅在 force_search=true 时注入
    required: true           # 强制要求调用（不是可选的）
---

# 网页搜索

当用户询问新闻、实时信息或需要联网搜索时：

1. 优先使用 tavily 工具进行联网搜索
2. 如果搜索失败，尝试使用 get_news 获取新闻
3. 总结搜索结果，给出准确、及时的回答