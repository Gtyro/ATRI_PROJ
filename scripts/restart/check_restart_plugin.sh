#!/bin/bash

# 检查重启插件是否正常加载的脚本

# 颜色输出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}检查ATRI重启插件加载状态${NC}"
echo "==============================="

# 检查是否有机器人进程在运行
if screen -list 2>/dev/null | grep -q "atri"; then
    echo -e "✅ 发现机器人会话 'atri'"
else
    echo -e "❌ 未发现机器人会话"
    echo -e "${YELLOW}请先启动机器人: ./scripts/restart/start_bot.sh${NC}"
    exit 1
fi

# 检查最新日志文件
LOG_DIR="logs"
if [ -d "$LOG_DIR" ] && [ "$(ls -A $LOG_DIR 2>/dev/null)" ]; then
    LATEST_LOG=$(ls -t $LOG_DIR/*.log 2>/dev/null | head -1)
    
    if [ -n "$LATEST_LOG" ]; then
        echo -e "📄 检查日志文件: $LATEST_LOG"
        echo ""
        
        # 检查重启系统初始化
        if grep -q "重启系统初始化成功" "$LATEST_LOG"; then
            echo -e "✅ 重启系统初始化成功"
        else
            echo -e "❌ 重启系统未正确初始化"
            if grep -q "重启系统初始化失败" "$LATEST_LOG"; then
                echo -e "${RED}发现初始化失败信息${NC}"
                grep "重启系统初始化失败" "$LATEST_LOG" | tail -3
            fi
        fi
        
        # 检查定时任务设置
        if grep -q "已设置定时重启任务" "$LATEST_LOG"; then
            echo -e "✅ 定时重启任务设置成功"
            grep "已设置定时重启任务" "$LATEST_LOG" | tail -1
        else
            echo -e "⚠️  未发现定时重启任务设置信息"
        fi
        
        # 检查插件加载状态
        init_count=$(grep -c "重启系统初始化成功" "$LATEST_LOG")
        task_count=$(grep -c "已设置定时重启任务" "$LATEST_LOG")
        
        if [ "$init_count" -gt 0 ] && [ "$task_count" -gt 0 ]; then
            echo -e "✅ 重启插件已成功加载并初始化"
        elif grep -q "plugins.restart" "$LATEST_LOG"; then
            echo -e "✅ 重启插件已加载（部分功能可能未初始化）"
        else
            echo -e "❌ 重启插件可能未正确加载"
        fi
        
        # 检查错误信息
        echo ""
        echo -e "${BLUE}检查相关错误信息：${NC}"
        ERROR_COUNT=$(grep -c "ERROR.*restart\|ERROR.*重启" "$LATEST_LOG" 2>/dev/null | head -1 || echo "0")
        if [ "${ERROR_COUNT:-0}" -gt 0 ]; then
            echo -e "${RED}发现 $ERROR_COUNT 个重启相关错误：${NC}"
            grep "ERROR.*restart\|ERROR.*重启" "$LATEST_LOG" | tail -5
        else
            echo -e "✅ 未发现重启相关错误"
        fi
        
    else
        echo -e "❌ 未找到日志文件"
    fi
else
    echo -e "❌ 日志目录不存在或为空"
fi

# 检查配置文件
echo ""
echo -e "${BLUE}检查配置文件：${NC}"
if [ -f "data/restart/config.yaml" ]; then
    echo -e "✅ 重启配置文件存在"
    echo "配置内容："
    cat data/restart/config.yaml
else
    echo -e "⚠️  重启配置文件尚未创建（首次运行时会自动创建）"
fi

# 检查状态文件
if [ -f "data/restart/status.json" ]; then
    echo -e "✅ 重启状态文件存在"
else
    echo -e "⚠️  重启状态文件尚未创建（首次运行时会自动创建）"
fi

echo ""
echo -e "${GREEN}==============================="
echo -e "检查完成！${NC}"
echo ""
echo -e "${YELLOW}如果发现问题：${NC}"
echo "1. 查看完整日志: tail -f $LATEST_LOG"
echo "2. 重启机器人: screen -S atri -X quit && ./scripts/restart/start_bot.sh"
echo "3. 检查依赖: ./scripts/restart/test_restart.sh" 
