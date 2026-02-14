#!/bin/bash

# 显示颜色
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}开始安装记忆系统所需依赖...${NC}"

# 检查 poetry 是否安装
if ! command -v poetry &> /dev/null; then
    echo -e "${RED}错误: 未找到 poetry. 请先安装 poetry。${NC}"
    exit 1
fi

# 安装依赖
echo -e "${GREEN}安装Python依赖...${NC}"
poetry install

# 特别检查OpenAI库
if poetry run python -c "import openai" &> /dev/null; then
    echo -e "${GREEN}OpenAI库安装成功!${NC}"
else
    echo -e "${RED}警告: OpenAI库安装失败，请检查 poetry 输出日志。${NC}"
fi

echo ""
echo -e "${BLUE}依赖安装完成!${NC}"
echo -e "${GREEN}请确保在data/memory_config.yaml中设置了正确的API密钥和端点.${NC}"
echo -e "${GREEN}当前API端点: $(grep -o '"api_base": "[^"]*"' data/memory_config.yaml | cut -d'"' -f4)${NC}"
echo ""
echo -e "${BLUE}下一步:${NC}"
echo "1. 编辑 data/memory_config.yaml 设置你的API密钥"
echo "2. 运行 poetry run python bot.py 启动机器人" 
