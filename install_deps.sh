#!/bin/bash

# 显示颜色
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}开始安装记忆系统所需依赖...${NC}"

# 检查pip是否安装
if ! command -v pip &> /dev/null; then
    echo -e "${RED}错误: 未找到pip. 请先安装Python和pip.${NC}"
    exit 1
fi

# 安装依赖
echo -e "${GREEN}安装Python依赖...${NC}"
pip install -r requirements.txt

# 特别检查OpenAI库
if pip show openai &> /dev/null; then
    echo -e "${GREEN}OpenAI库安装成功!${NC}"
else
    echo -e "${RED}警告: OpenAI库安装失败. 尝试单独安装...${NC}"
    pip install openai
fi

echo ""
echo -e "${BLUE}依赖安装完成!${NC}"
echo -e "${GREEN}请确保在data/memory_config.yaml中设置了正确的API密钥和端点.${NC}"
echo -e "${GREEN}当前API端点: $(grep -o '"api_base": "[^"]*"' data/memory_config.yaml | cut -d'"' -f4)${NC}"
echo ""
echo -e "${BLUE}下一步:${NC}"
echo "1. 编辑 data/memory_config.yaml 设置你的API密钥"
echo "2. 运行 python bot.py 启动机器人" 