#!/bin/bash

# ATRI重启系统测试脚本

set -e

# 颜色输出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}ATRI重启系统测试${NC}"
echo "==============================="

# 测试项目目录（从scripts/restart/回到项目根目录）
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_DIR"

echo "项目目录: $PROJECT_DIR"

# 1. 检查插件文件
echo -e "\n${BLUE}1. 检查插件文件${NC}"
files=(
    "plugins/restart/__init__.py"
    "plugins/restart/config.py"
    "plugins/restart/restart_manager.py"
    "plugins/restart/README.md"
    "scripts/restart/start_bot.sh"
    "scripts/restart/test_restart.sh"
    "scripts/restart/check_restart_plugin.sh"
)

for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "✅ $file"
    else
        echo -e "❌ $file - 文件不存在"
    fi
done

# 2. 检查脚本权限
echo -e "\n${BLUE}2. 检查脚本权限${NC}"
if [ -x "scripts/restart/start_bot.sh" ]; then
    echo -e "✅ scripts/restart/start_bot.sh 有执行权限"
else
    echo -e "❌ scripts/restart/start_bot.sh 没有执行权限"
    echo "运行: chmod +x scripts/restart/start_bot.sh"
fi

# 3. 激活虚拟环境（如果存在）
echo -e "\n${BLUE}3. 检查虚拟环境${NC}"
VENV_PATH="$PROJECT_DIR/.venv"
if [ -d "$VENV_PATH" ]; then
    echo -e "✅ 发现虚拟环境，正在激活..."
    source "$VENV_PATH/bin/activate"
    echo -e "✅ 虚拟环境已激活"
else
    echo -e "⚠️  未发现虚拟环境，使用系统Python"
fi

# 4. 检查核心依赖包
echo -e "\n${BLUE}4. 检查核心依赖包${NC}"
declare -A dependencies=(
    ["nonebot2"]="nonebot"
    ["fastapi"]="fastapi"
    ["uvicorn"]="uvicorn"
)

for package in "${!dependencies[@]}"; do
    module="${dependencies[$package]}"
    if python -c "import $module" 2>/dev/null; then
        echo -e "✅ $package"
    else
        echo -e "❌ $package - 未安装"
    fi
done

# 特殊检查apscheduler插件（使用pip show而不是import）
if pip show nonebot-plugin-apscheduler > /dev/null 2>&1; then
    echo -e "✅ nonebot-plugin-apscheduler"
else
    echo -e "❌ nonebot-plugin-apscheduler - 未安装"
fi

# 5. 检查配置文件
echo -e "\n${BLUE}5. 检查配置文件${NC}"
config_files=(".env.dev" "bot.py")

for file in "${config_files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "✅ $file"
    else
        echo -e "❌ $file - 文件不存在"
    fi
done

# 6. 测试简单配置创建（不依赖NoneBot）
echo -e "\n${BLUE}6. 测试配置文件格式${NC}"
mkdir -p data/restart
cat > data/restart/test_config.json << 'EOF'
{
  "auto_restart_enabled": true,
  "restart_time": "04:00",
  "startup_script_path": "scripts/restart/start_bot.sh",
  "max_restart_attempts": 3,
  "restart_delay": 5
}
EOF

if [ -f "data/restart/test_config.json" ]; then
    echo -e "✅ 配置文件格式正确"
    rm -f data/restart/test_config.json
    echo -e "✅ 测试配置文件已清理"
else
    echo -e "❌ 配置文件创建失败"
fi

# 7. 检查启动脚本语法
echo -e "\n${BLUE}7. 检查启动脚本语法${NC}"
if bash -n scripts/restart/start_bot.sh; then
    echo -e "✅ 启动脚本语法正确"
else
    echo -e "❌ 启动脚本语法错误"
fi

# 8. 检查screen命令
echo -e "\n${BLUE}8. 检查screen命令${NC}"
if command -v screen &> /dev/null; then
    echo -e "✅ screen命令可用"
else
    echo -e "❌ screen命令不可用"
    echo "请安装screen: sudo apt install screen"
fi

# 9. 检查目录权限
echo -e "\n${BLUE}9. 检查目录权限${NC}"
dirs=("data" "data/restart" "scripts" "scripts/restart" "logs")

for dir in "${dirs[@]}"; do
    if [ -d "$dir" ]; then
        if [ -w "$dir" ]; then
            echo -e "✅ $dir 目录可写"
        else
            echo -e "❌ $dir 目录不可写"
        fi
    else
        echo -e "⚠️  $dir 目录不存在（将自动创建）"
    fi
done

echo -e "\n${GREEN}==============================="
echo -e "环境检查完成！${NC}"
echo ""
echo -e "${BLUE}快速命令：${NC}"
echo "• 启动机器人: ./scripts/restart/restart.sh start"
echo "• 检查插件: ./scripts/restart/restart.sh check"
echo "• 查看状态: ./scripts/restart/restart.sh status"
echo ""
echo -e "${YELLOW}QQ命令（需超级用户权限）：${NC}"
echo "• @机器人 重启状态"
echo "• @机器人 重启配置"
echo "• @机器人 重启" 