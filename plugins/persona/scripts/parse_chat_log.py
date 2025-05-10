import re
import os
import yaml
from datetime import datetime

def read_bot_id():
    """从 persona.yaml 读取 bot_id"""
    try:
        with open('data/persona.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config.get('bot_id', '')
    except Exception as e:
        print(f"读取 bot_id 时出错: {e}")
        return ''

def parse_chat_log(file_path, bot_id):
    # 从文件路径获取 conv_id
    file_name = os.path.basename(file_path)
    conv_id = re.search(r'(\d+)', file_name).group(1) if re.search(r'(\d+)', file_name) else file_name
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 找到所有消息头的位置
    header_pattern = r'(\d{4}-\d{2}-\d{2} \d{1,2}:\d{2}:\d{2}) (.*?)\((\d+)\)'
    headers = [(m.group(1), m.group(2), m.group(3), m.start(), m.end()) 
               for m in re.finditer(header_pattern, content)]
    
    messages = []
    for i, (time_str, user_name, user_id, start_idx, end_idx) in enumerate(headers):
        # 去除用户名中的标题（【】包围）
        user_name = re.sub(r'【.*?】', '', user_name).strip()
        
        # 解析时间
        created_at = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
        
        # 提取消息内容
        if i < len(headers) - 1:
            next_start = headers[i+1][3]
            msg_content = content[end_idx:next_start].strip()
        else:
            msg_content = content[end_idx:].strip()
        
        # 检查消息是否来自机器人
        is_bot = (user_id == bot_id)
        
        # 创建消息字典
        message = {
            "conv_id": conv_id,
            "user_id": user_id,
            "user_name": user_name,
            "content": msg_content,
            "created_at": created_at,
            "is_bot": is_bot
        }
        
        messages.append(message)
    
    return messages

def main():
    # 读取 bot_id
    bot_id = read_bot_id()
    if not bot_id:
        print("警告: 无法获取 bot_id, 将使用空字符串")
        bot_id = ""
    
    # 解析聊天记录
    file_path = "scripts/591710353.txt"
    messages = parse_chat_log(file_path, bot_id)
    
    # 输出总消息数
    print(f"总共有 {len(messages)} 条消息")
    
    # 检查所有 user_id 是否都是纯数字
    all_numeric = all(message["user_id"].isdigit() for message in messages)
    print(f"所有的用户ID都是纯数字: {all_numeric}")
    
    return messages

if __name__ == "__main__":
    main()