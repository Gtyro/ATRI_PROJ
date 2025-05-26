from nonebot import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import MessageSegment
from nonebot.permission import SUPERUSER

from .word_analyzer import get_word_cloud_data

# 词云命令
wordcloud_cmd = on_command("wordcloud", aliases={"词云"}, permission=SUPERUSER, priority=5)

@wordcloud_cmd.handle()
async def handle_wordcloud(args: Message = CommandArg()):
    """处理词云命令"""
    arg_str = args.extract_plain_text().strip()
    limit = None
    
    # 解析参数
    if arg_str and arg_str.isdigit():
        limit = int(arg_str)
    
    # 获取词云数据
    word_data = await get_word_cloud_data(limit=limit)
    
    if not word_data:
        await wordcloud_cmd.finish("暂无词云数据")
    
    # 格式化输出
    result = "当前热门词汇：\n"
    for i, item in enumerate(word_data[:15], 1):  # 只显示前15个
        result += f"{i}. {item['word']} ({item['weight']})\n"
    
    await wordcloud_cmd.finish(result)

# 这里预留词云图片生成功能的实现
# 如果需要实现图片生成，可以使用wordcloud库
# 示例代码:
# 
# from wordcloud import WordCloud
# import matplotlib.pyplot as plt
# from io import BytesIO
# import base64
# 
# async def generate_wordcloud_image(word_data):
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
# async def handle_wordcloud_img():
#     word_data = await get_word_cloud_data()
#     
#     if not word_data:
#         await wordcloud_img_cmd.finish("暂无词云数据")
#     
#     # 生成词云图片
#     img_buffer = await generate_wordcloud_image(word_data)
#     
#     # 发送图片
#     await wordcloud_img_cmd.finish(MessageSegment.image(img_buffer)) 