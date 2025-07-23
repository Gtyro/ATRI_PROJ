#!/bin/bash

# ATRI重启系统主入口脚本

# 颜色输出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}ATRI重启系统管理工具${NC}"
echo "==============================="

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_DIR"

# 检查参数
if [ $# -eq 0 ]; then
    echo -e "${YELLOW}使用方法：${NC}"
    echo "  ./scripts/restart/restart.sh test      - 运行环境检测"
    echo "  ./scripts/restart/restart.sh check     - 检查插件状态"
    echo "  ./scripts/restart/restart.sh start     - 启动机器人"
    echo "  ./scripts/restart/restart.sh status    - 查看运行状态"
    echo ""
    echo -e "${YELLOW}QQ命令（需超级用户权限）：${NC}"
    echo "  @机器人 重启状态"
    echo "  @机器人 重启配置"
    echo "  @机器人 重启"
    exit 0
fi

case "$1" in
    "test")
        echo -e "${GREEN}运行环境检测...${NC}"
        cd "$PROJECT_DIR"
        ./scripts/restart/test_restart.sh
        ;;
    "check")
        echo -e "${GREEN}检查插件状态...${NC}"
        cd "$PROJECT_DIR"
        ./scripts/restart/check_restart_plugin.sh
        ;;
    "start")
        echo -e "${GREEN}启动机器人...${NC}"
        cd "$PROJECT_DIR"
        ./scripts/restart/start_bot.sh
        ;;
    "status")
        echo -e "${GREEN}查看运行状态...${NC}"
        if screen -list 2>/dev/null | grep -q "atri"; then
            echo -e "✅ 机器人正在运行"
            screen -list | grep atri
            
            if [ -f "data/restart/config.json" ]; then
                echo ""
                echo -e "${BLUE}重启配置：${NC}"
                cat data/restart/config.json | jq . 2>/dev/null || cat data/restart/config.json
            fi
            
            if [ -f "data/restart/status.json" ]; then
                echo ""
                echo -e "${BLUE}重启状态：${NC}"
                cat data/restart/status.json | jq . 2>/dev/null || cat data/restart/status.json
            fi
        else
            echo -e "❌ 机器人未运行"
            echo "使用 '$0 start' 启动机器人"
        fi
        ;;
    *)
        echo -e "❌ 未知命令: $1"
        echo "使用 '$0' 查看帮助"
        exit 1
        ;;
esac 