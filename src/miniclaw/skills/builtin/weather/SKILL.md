---
name: weather
description: 天气查询技能，获取天气信息和出行建议
agent: info
tools:
  - name: get_weather
  - name: get_forecast
  - name: get_suggestion
---

# 天气查询

当用户询问天气相关问题时：

1. 使用 get_weather 工具获取指定城市的当前天气信息
2. 如果用户需要未来天气，使用 get_forecast 工具获取天气预报
3. 使用 get_suggestion 工具获取出行建议
4. 以友好的方式总结天气信息，包括温度、湿度、风力、体感温度等

## 回复格式

- 先说明城市和当前天气状况
- 给出温度、湿度、风力等关键数据
- 最后提供出行建议
