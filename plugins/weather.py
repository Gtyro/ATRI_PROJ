from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, GroupMessageEvent, Message, MessageSegment
from nonebot.params import CommandArg
from nonebot.rule import to_me
import httpx
import json
from nonebot.permission import SUPERUSER
# 注册天气查询命令处理器
weather = on_command("天气", aliases={"查天气", "weather"},permission=SUPERUSER, priority=5)

@weather.handle()
async def handle_weather(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    # 获取命令参数（城市名称）
    city = args.extract_plain_text().strip()
    
    if not city:
        await weather.finish("请提供要查询的城市名称，例如：天气 北京")
        return
    
    # 模拟天气查询逻辑（实际应用中应替换为真实API调用）
    weather_info = await get_weather(city)
    
    # 构建回复消息
    if weather_info:
        reply = f"🌈 {city}天气信息：\n温度：{weather_info['temperature']}°C\n天气：{weather_info['weather']}\n湿度：{weather_info['humidity']}%\n风力：{weather_info['wind']}"
    else:
        reply = f"抱歉，未能获取到{city}的天气信息，请检查城市名称是否正确。"
    
    # 发送回复
    await weather.finish(reply)

async def get_weather(city: str):
    """
    模拟天气API查询
    实际应用中应替换为真实的天气API调用
    """
    # 这里仅作示范，返回模拟数据
    # 实际使用时应调用真实的天气API，如和风天气、心知天气等
    weather_data = {
        "北京": {"temperature": 22, "weather": "晴", "humidity": 40, "wind": "东北风3级"},
        "上海": {"temperature": 26, "weather": "多云", "humidity": 55, "wind": "东风4级"},
        "广州": {"temperature": 30, "weather": "阵雨", "humidity": 80, "wind": "南风2级"},
        "深圳": {"temperature": 31, "weather": "晴", "humidity": 75, "wind": "东南风3级"},
    }
    
    return weather_data.get(city, None) 