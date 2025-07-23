#!/bin/bash

# ATRI机器人启动脚本
# 支持虚拟环境和screen会话管理

set -e

# 配置变量
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PATH="$PROJECT_DIR/.venv"
SCREEN_SESSION="atri"
BOT_SCRIPT="bot.py"

# 颜色输出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}ATRI机器人启动脚本${NC}"
echo "项目目录: $PROJECT_DIR"

# 切换到项目目录
cd "$PROJECT_DIR"

# 检查虚拟环境
if [ -d "$VENV_PATH" ]; then
    echo -e "${GREEN}发现虚拟环境，正在激活...${NC}"
    source "$VENV_PATH/bin/activate"
    echo -e "${GREEN}虚拟环境已激活${NC}"
else
    echo -e "${YELLOW}警告：未找到虚拟环境 ($VENV_PATH)${NC}"
    echo -e "${YELLOW}将使用系统Python环境${NC}"
fi

# 检查bot.py文件
if [ ! -f "$BOT_SCRIPT" ]; then
    echo -e "${RED}错误：找不到 $BOT_SCRIPT 文件${NC}"
    exit 1
fi

# 检查Python依赖
echo "检查Python依赖..."
python -c "import nonebot" 2>/dev/null || {
    echo -e "${RED}错误：nonebot未安装，请运行 pip install -r requirements.txt${NC}"
    exit 1
}

# 检查现有的screen会话
if screen -list 2>/dev/null | grep -q "$SCREEN_SESSION"; then
    echo -e "${YELLOW}发现现有的 $SCREEN_SESSION 会话${NC}"
    
    # 询问是否要杀死现有会话
    read -p "是否要停止现有会话并重新启动？(y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}正在停止现有会话...${NC}"
        screen -S "$SCREEN_SESSION" -X quit || true
        sleep 2
    else
        echo -e "${BLUE}使用 'screen -r $SCREEN_SESSION' 连接到现有会话${NC}"
        exit 0
    fi
fi

# 启动新的screen会话
echo -e "${GREEN}启动新的 $SCREEN_SESSION 会话...${NC}"

# 构建启动命令
if [ -d "$VENV_PATH" ]; then
    # 使用虚拟环境
    START_CMD="cd '$PROJECT_DIR' && source '$VENV_PATH/bin/activate' && python $BOT_SCRIPT"
else
    # 使用系统Python
    START_CMD="cd '$PROJECT_DIR' && python $BOT_SCRIPT"
fi

# 启动screen会话
screen -dmS "$SCREEN_SESSION" bash -c "$START_CMD"

# 等待一下确保启动成功
sleep 3

# 检查是否成功启动
if screen -list 2>/dev/null | grep -q "$SCREEN_SESSION"; then
    echo -e "${GREEN}✅ ATRI机器人启动成功！${NC}"
    echo ""
    echo -e "${BLUE}📋 管理命令：${NC}"
    echo "  连接会话: screen -r $SCREEN_SESSION"
    echo "  分离会话: Ctrl+A, D"
    echo "  查看会话: screen -list"
    echo "  停止会话: screen -S $SCREEN_SESSION -X quit"
    echo ""
    echo -e "${BLUE}📊 日志查看：${NC}"
    echo "  实时日志: tail -f logs/\$(ls logs/ | tail -1)"
    echo "  查看日志: ls logs/"
else
    echo -e "${RED}❌ 警告：ATRI机器人可能启动失败${NC}"
    echo "请检查日志文件或手动运行 python $BOT_SCRIPT 查看错误信息"
    exit 1
fi 