from langchain_core.tools import tool


@tool
def get_weather(city: str) -> str:
    """获取指定城市的天气信息"""
    return f"暂无{city}的实时天气数据，请配置天气API后使用。"


async def fetch_weather(city: str) -> str:
    return get_weather.invoke({"city": city})


async def fetch_weather_async(city: str) -> str:
    return await fetch_weather(city)
