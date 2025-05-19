import json
import os

import httpx
import pandas as pd
import yaml
from nonebot import on_command
from nonebot.adapters.onebot.v11 import (Bot, GroupMessageEvent, Message,
                                         MessageEvent, MessageSegment)
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER
from nonebot.rule import to_me


# 加载配置文件
def load_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'config.yaml')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config
    except Exception as e:
        print(f"加载配置文件出错: {e}")
        return {}

config = load_config()
api_key = config.get('amap_weather_api_key', '')

# 检查API密钥
if not api_key:
    print("警告: 未找到高德地图API密钥，天气插件将无法正常工作")

# 加载城市编码数据
current_dir = os.path.dirname(os.path.abspath(__file__))
excel_path = os.path.join(current_dir, "AMap_adcode_citycode.xlsx")
city_data = pd.read_excel(excel_path, engine='openpyxl')
# 创建城市名到adcode的映射
city_to_adcode = {}
for _, row in city_data.iterrows():
    if not pd.isna(row.iloc[0]):  # 确保城市名不为空
        city_name = row.iloc[0].replace('市', '').replace('区', '').replace('县', '')
        city_to_adcode[city_name] = str(int(row.iloc[1]))  # adcode

# 注册天气查询命令处理器
weather = on_command("天气", aliases={"查天气", "weather"}, permission=SUPERUSER, priority=5, block=True)

@weather.handle()
async def handle_weather(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    # 获取命令参数（城市名称）
    city = args.extract_plain_text().strip()

    if not city:
        await weather.finish("请提供要查询的城市名称，例如：天气 北京")
        return

    # 找到城市对应的adcode
    adcode = find_adcode(city)
    if not adcode:
        await weather.finish(f"未找到{city}的编码信息，请检查城市名称是否正确。")
        return

    # 获取实时天气
    live_weather = await get_weather(adcode, "base")
    if not live_weather:
        await weather.finish(f"抱歉，未能获取到{city}的天气信息。")
        return

    # 获取天气预报
    forecast_weather = await get_weather(adcode, "all")

    # 构建回复消息
    reply = format_weather_reply(city, live_weather, forecast_weather)

    # 发送回复
    await weather.finish(reply)

def find_adcode(city_name):
    """查找城市的adcode"""
    # 处理城市名，移除"市"、"区"、"县"后缀
    city_name = city_name.replace('市', '').replace('区', '').replace('县', '')
    return city_to_adcode.get(city_name)

async def get_weather(adcode, extensions="base"):
    """
    调用高德天气API获取天气信息
    extensions: base为实况天气，all为预报天气
    """
    url = "https://restapi.amap.com/v3/weather/weatherInfo"
    params = {
        "key": api_key,
        "city": adcode,
        "extensions": extensions,
        "output": "JSON"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            data = response.json()

            if data["status"] == "1":
                if extensions == "base" and "lives" in data and data["lives"]:
                    return data["lives"][0]
                elif extensions == "all" and "forecasts" in data and data["forecasts"]:
                    return data["forecasts"][0]
            return None
    except Exception as e:
        print(f"天气API调用出错: {e}")
        return None

def format_weather_reply(city, live_weather, forecast_weather):
    """格式化天气回复消息"""
    reply = f"🌈 {city}天气信息：\n"

    if live_weather:
        reply += f"📍 当前天气：{live_weather['weather']}\n"
        reply += f"🌡️ 实时温度：{live_weather['temperature']}°C\n"
        reply += f"💧 湿度：{live_weather['humidity']}%\n"
        reply += f"🍃 风向：{live_weather['winddirection']}\n"
        reply += f"💨 风力：{live_weather['windpower']}\n"
        reply += f"🕒 发布时间：{live_weather['reporttime']}\n"

    if forecast_weather and "casts" in forecast_weather:
        reply += "\n⏱️ 未来天气预报：\n"
        for i, cast in enumerate(forecast_weather["casts"]):
            if i > 2:  # 只显示三天预报
                break
            day_label = "今天" if i == 0 else "明天" if i == 1 else "后天"
            reply += f"\n{day_label}：\n"
            reply += f"白天：{cast['dayweather']} {cast['daytemp']}°C {cast['daywind']}风{cast['daypower']}级\n"
            reply += f"夜间：{cast['nightweather']} {cast['nighttemp']}°C {cast['nightwind']}风{cast['nightpower']}级\n"

    return reply.strip()