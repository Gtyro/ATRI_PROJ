from nonebot import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import MessageSegment, GroupMessageEvent
from nonebot.permission import SUPERUSER

from .word_analyzer import get_word_cloud_data
from .models import get_all_conversations

# 词云命令
wordcloud_cmd = on_command("wordcloud", aliases={"词云"}, permission=SUPERUSER, priority=5)

@wordcloud_cmd.handle()
async def handle_wordcloud(event: GroupMessageEvent, args: Message = CommandArg()):
    """处理词云命令"""
    # 获取当前会话ID
    conv_id = str(event.group_id) if hasattr(event, 'group_id') else str(event.user_id)
    
    arg_str = args.extract_plain_text().strip()
    limit = None
    custom_conv_id = None
    
    # 解析参数，格式: [会话ID] [数量限制]
    parts = arg_str.split()
    if len(parts) >= 1:
        if parts[0].isdigit() and len(parts) == 1:
            # 只有一个参数且为数字，视为数量限制
            limit = int(parts[0])
        else:
            # 第一个参数视为会话ID
            custom_conv_id = parts[0]
            # 如果有第二个参数且为数字，视为数量限制
            if len(parts) >= 2 and parts[1].isdigit():
                limit = int(parts[1])
    
    # 使用自定义会话ID或当前会话ID
    conv_id = custom_conv_id or conv_id
    
    # 获取词云数据
    word_data = await get_word_cloud_data(conv_id, limit=limit)
    
    if not word_data:
        await wordcloud_cmd.finish(f"会话 {conv_id} 暂无词云数据")
    
    # 格式化输出
    result = f"会话 {conv_id} 当前热门词汇：\n"
    for i, item in enumerate(word_data[:15], 1):  # 只显示前15个
        result += f"{i}. {item['word']} ({item['weight']})\n"
    
    await wordcloud_cmd.finish(result)

# 列出所有会话词云命令
wordcloud_list_cmd = on_command("wordcloud_list", aliases={"词云列表"}, permission=SUPERUSER, priority=5)

@wordcloud_list_cmd.handle()
async def handle_wordcloud_list():
    """处理词云列表命令"""
    conv_ids = await get_all_conversations()
    
    if not conv_ids:
        await wordcloud_list_cmd.finish("暂无任何会话的词云数据")
    
    result = "可用的会话词云列表：\n"
    for i, conv_id in enumerate(conv_ids, 1):
        result += f"{i}. {conv_id}\n"
    
    result += "\n使用 '词云 [会话ID]' 查看特定会话的词云"
    
    await wordcloud_list_cmd.finish(result)

# 这里预留词云图片生成功能的实现
# 如果需要实现图片生成，可以使用wordcloud库
# 示例代码:
# 
# from wordcloud import WordCloud
# import matplotlib.pyplot as plt
# from io import BytesIO
# import base64
# 
# async def generate_wordcloud_image(conv_id, word_data):
#     # 创建词频字典
#     word_freq = {item["word"]: item["weight"] for item in word_data}
#     
#     # 生成词云
#     wc = WordCloud(
#         width=800, 
#         height=400, 
#         background_color="white", 
#         font_path="path/to/font.ttf",  # 中文字体路径
#         max_words=100
#     )
#     wc.generate_from_frequencies(word_freq)
#     
#     # 转换为图片
#     plt.figure(figsize=(10, 5))
#     plt.imshow(wc, interpolation="bilinear")
#     plt.axis("off")
#     
#     # 保存到内存
#     img_buffer = BytesIO()
#     plt.savefig(img_buffer, format='PNG')
#     img_buffer.seek(0)
#     
#     return img_buffer
# 
# wordcloud_img_cmd = on_command("wordcloud_img", aliases={"词云图"}, priority=5)
# 
# @wordcloud_img_cmd.handle()
# async def handle_wordcloud_img(event: GroupMessageEvent, args: Message = CommandArg()):
#     conv_id = str(event.group_id) if hasattr(event, 'group_id') else str(event.user_id)
#     
#     arg_str = args.extract_plain_text().strip()
#     if arg_str:
#         conv_id = arg_str
#     
#     word_data = await get_word_cloud_data(conv_id)
#     
#     if not word_data:
#         await wordcloud_img_cmd.finish(f"会话 {conv_id} 暂无词云数据")
#     
#     # 生成词云图片
#     img_buffer = await generate_wordcloud_image(conv_id, word_data)
#     
#     # 发送图片
#     await wordcloud_img_cmd.finish(MessageSegment.image(img_buffer)) 