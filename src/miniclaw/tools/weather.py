"""
MiniClaw Weather Tools
Fetches weather information from weather API
"""

from typing import Dict, Any, Optional
import httpx

from miniclaw.config.settings import settings


async def fetch_weather_async(city: str) -> Dict[str, Any]:
    api_key = settings.WEATHER_API_KEY
    api_url = settings.WEATHER_API_URL
    
    if not api_key:
        return {
            "city": city,
            "temperature": "N/A",
            "condition": "API未配置",
            "humidity": "N/A",
            "wind": "N/A",
            "forecast": [],
            "message": "请配置 WEATHER_API_KEY 环境变量",
        }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{api_url}/current.json",
                params={"key": api_key, "q": city, "lang": "zh"},
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
            
            current = data.get("current", {})
            location = data.get("location", {})
            
            return {
                "city": location.get("name", city),
                "country": location.get("country", ""),
                "temperature": current.get("temp_c", "N/A"),
                "condition": current.get("condition", {}).get("text", "N/A"),
                "humidity": current.get("humidity", "N/A"),
                "wind": f"{current.get('wind_kph', 'N/A')} km/h",
                "feels_like": current.get("feelslike_c", "N/A"),
                "last_updated": current.get("last_updated", ""),
            }
    except httpx.HTTPError as e:
        return {
            "city": city,
            "error": str(e),
            "message": f"获取天气失败: {str(e)}",
        }
    except Exception as e:
        return {
            "city": city,
            "error": str(e),
            "message": f"发生错误: {str(e)}",
        }


def fetch_weather(city: str) -> Dict[str, Any]:
    api_key = settings.WEATHER_API_KEY
    api_url = settings.WEATHER_API_URL
    
    if not api_key:
        return {
            "city": city,
            "temperature": "N/A",
            "condition": "API未配置",
            "humidity": "N/A",
            "wind": "N/A",
            "message": "请配置 WEATHER_API_KEY 环境变量",
        }
    
    try:
        with httpx.Client() as client:
            response = client.get(
                f"{api_url}/current.json",
                params={"key": api_key, "q": city, "lang": "zh"},
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
            
            current = data.get("current", {})
            location = data.get("location", {})
            
            return {
                "city": location.get("name", city),
                "country": location.get("country", ""),
                "temperature": current.get("temp_c", "N/A"),
                "condition": current.get("condition", {}).get("text", "N/A"),
                "humidity": current.get("humidity", "N/A"),
                "wind": f"{current.get('wind_kph', 'N/A')} km/h",
                "feels_like": current.get("feelslike_c", "N/A"),
                "last_updated": current.get("last_updated", ""),
            }
    except httpx.HTTPError as e:
        return {
            "city": city,
            "error": str(e),
            "message": f"获取天气失败: {str(e)}",
        }
    except Exception as e:
        return {
            "city": city,
            "error": str(e),
            "message": f"发生错误: {str(e)}",
        }


def get_weather_suggestion(weather_data: Dict[str, Any]) -> str:
    condition = weather_data.get("condition", "").lower()
    temp = weather_data.get("temperature")
    
    suggestions = []
    
    if isinstance(temp, (int, float)):
        if temp < 10:
            suggestions.append("天气较冷，注意保暖")
        elif temp > 30:
            suggestions.append("天气炎热，注意防暑")
        elif 15 <= temp <= 25:
            suggestions.append("温度适宜，适合外出")
    
    if "雨" in condition:
        suggestions.append("有雨，记得带伞")
    elif "雪" in condition:
        suggestions.append("有雪，注意路滑")
    elif "晴" in condition:
        suggestions.append("天气晴朗")
    
    return "；".join(suggestions) if suggestions else "祝您出行愉快"
