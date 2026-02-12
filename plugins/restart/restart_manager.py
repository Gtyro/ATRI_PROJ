"""
重启管理器 - 处理机器人的重启逻辑
"""

import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from nonebot import get_driver

from .config import RestartConfig


class RestartManager:
    """重启管理器"""

    def __init__(self, config: RestartConfig):
        self.config = config
        self.status_file = "data/restart/status.json"
        self.driver = get_driver()
        self.start_time = time.time()
        self._status_lock = threading.Lock()

    async def initialize(self) -> None:
        """初始化重启管理器"""
        try:
            # 确保数据目录存在
            os.makedirs("data/restart", exist_ok=True)
            os.makedirs("scripts/restart", exist_ok=True)

            # 记录启动时间
            await self.record_startup()

            logging.info("重启管理器初始化完成")

        except Exception as e:
            logging.error(f"重启管理器初始化失败: {e}")
            raise

    async def perform_restart(self, reason: str = "未知原因", delay_seconds: int = 0) -> None:
        """执行重启操作

        Args:
            reason: 重启原因
            delay_seconds: 延迟时间（秒）
        """
        try:
            logging.info(f"开始执行重启操作，原因: {reason}")

            # 记录重启信息
            await self._record_restart_info(reason)

            # 如果有延迟，等待
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds)

            # 执行重启
            await self._execute_restart()

        except Exception as e:
            logging.error(f"重启操作失败: {e}")
            raise

    async def _execute_restart(self) -> None:
        """执行实际的重启逻辑"""
        try:
            # 1. 准备启动脚本
            startup_script = await self._prepare_startup_script()

            # 2. 创建重启脚本
            restart_script = await self._create_restart_script(startup_script)

            # 3. 启动重启脚本
            await self._launch_restart_script(restart_script)

            # 4. 安全关闭当前进程
            await self._safe_shutdown()

        except Exception as e:
            logging.error(f"重启执行失败: {e}")
            raise

    async def _prepare_startup_script(self) -> str:
        """准备启动脚本"""
        script_path = self.config.startup_script_path

        # 如果脚本不存在，创建默认脚本
        if not os.path.exists(script_path):
            await self._create_default_startup_script(script_path)

        # 确保脚本有执行权限
        os.chmod(script_path, 0o755)

        return os.path.abspath(script_path)

    async def _create_default_startup_script(self, script_path: str) -> None:
        """创建默认启动脚本"""
        try:
            # 确保scripts目录存在
            os.makedirs(os.path.dirname(script_path), exist_ok=True)

            # 获取当前工作目录和Python路径
            current_dir = os.getcwd()
            python_executable = sys.executable

            # 根据用户提供的信息，检测是否使用虚拟环境
            venv_path = os.path.join(current_dir, ".venv")
            use_venv = os.path.exists(venv_path)

            script_content = f"""#!/bin/bash

# ATRI机器人自动重启脚本
# 由重启系统自动生成

set -e

echo "开始启动ATRI机器人..."

# 切换到项目目录
cd "{current_dir}"

"""

            if use_venv:
                script_content += f"""
# 激活虚拟环境
source .venv/bin/activate
echo "虚拟环境已激活"

"""

            script_content += f"""
# 检查是否有现有的screen会话并杀死
if screen -list | grep -q "atri"; then
    echo "发现现有的atri会话，正在关闭..."
    screen -S atri -X quit || true
    sleep 2
fi

# 启动新的screen会话
echo "启动新的ATRI会话..."
screen -dmS atri bash -c "{python_executable} bot.py"

# 等待一下确保启动成功
sleep 3

# 检查是否成功启动
if screen -list | grep -q "atri"; then
    echo "ATRI机器人启动成功！"
    echo "使用 'screen -r atri' 连接到会话"
else
    echo "警告：ATRI机器人可能启动失败"
    exit 1
fi
"""

            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(script_content)

            logging.info(f"已创建默认启动脚本: {script_path}")

        except Exception as e:
            logging.error(f"创建启动脚本失败: {e}")
            raise

    async def _create_restart_script(self, startup_script: str) -> str:
        """创建重启脚本"""
        restart_script_path = "scripts/restart/restart_bot.sh"

        try:
            os.makedirs(os.path.dirname(restart_script_path), exist_ok=True)

            script_content = f"""#!/bin/bash

# ATRI机器人重启脚本
LOG_FILE="/tmp/atri_restart.log"

echo "=== ATRI重启脚本开始 ===" > $LOG_FILE
echo "时间: $(date)" >> $LOG_FILE
echo "启动脚本: {startup_script}" >> $LOG_FILE

# 等待原进程完全退出
sleep {self.config.restart_delay}

# 检查并清理旧的screen会话
if screen -list | grep -q "atri"; then
    echo "关闭现有atri会话..." >> $LOG_FILE
    screen -S atri -X quit || true
    sleep 2
fi

# 切换到项目目录
PROJECT_DIR="$(dirname "$(dirname "$(readlink -f "$0")")")"
cd "$PROJECT_DIR" || {{
    echo "错误：无法切换到项目目录 $PROJECT_DIR" >> $LOG_FILE
    exit 1
}}

# 执行启动脚本
if [ -x "{startup_script}" ]; then
    bash "{startup_script}" >> $LOG_FILE 2>&1
    EXIT_CODE=$?

    # 检查是否启动成功
    sleep 3
    if screen -list | grep -q "atri"; then
        echo "✅ ATRI机器人重启成功！" >> $LOG_FILE
    else
        echo "❌ ATRI机器人启动失败" >> $LOG_FILE
    fi
else
    echo "错误：启动脚本不存在: {startup_script}" >> $LOG_FILE
    exit 1
fi

echo "=== 重启脚本完成 ===" >> $LOG_FILE

# 清理脚本
sleep 5
rm -f "{os.path.abspath(restart_script_path)}"
"""

            with open(restart_script_path, 'w', encoding='utf-8') as f:
                f.write(script_content)

            os.chmod(restart_script_path, 0o755)
            return os.path.abspath(restart_script_path)

        except Exception as e:
            logging.error(f"创建重启脚本失败: {e}")
            raise

    async def _launch_restart_script(self, restart_script: str) -> None:
        """启动重启脚本"""
        try:
            # 确保脚本有执行权限
            os.chmod(restart_script, 0o755)

            # 在后台启动重启脚本
            process = subprocess.Popen(
                ["nohup", "bash", restart_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                cwd=os.getcwd(),
                env=os.environ.copy()
            )

            logging.info(f"重启脚本已启动: {restart_script} (PID: {process.pid})")

        except Exception as e:
            logging.error(f"启动重启脚本失败: {e}")
            raise

    async def _safe_shutdown(self) -> None:
        """安全关闭当前进程"""
        try:
            logging.info("开始安全关闭机器人...")

            # 给一点时间让日志写入
            await asyncio.sleep(1)

            # 发送SIGTERM信号给自己
            os.kill(os.getpid(), signal.SIGTERM)

        except Exception as e:
            logging.error(f"安全关闭失败: {e}")
            # 强制退出
            sys.exit(1)

    async def record_startup(self) -> None:
        """记录启动时间"""
        try:
            with self._status_lock:
                status_data = self._read_status_unlocked()
                status_data.update({
                    "last_startup": datetime.now().isoformat(),
                    "start_time": self.start_time
                })
                self._write_status_unlocked(status_data)
            logging.info("启动时间已记录")

        except Exception as e:
            logging.error(f"记录启动时间失败: {e}")

    async def _record_restart_info(self, reason: str) -> None:
        """记录重启信息"""
        try:
            with self._status_lock:
                status_data = self._read_status_unlocked()
                status_data.update({
                    "last_restart": datetime.now().isoformat(),
                    "restart_reason": reason,
                    "restart_count": int(status_data.get("restart_count", 0)) + 1,
                    "need_notification": self.config.restart_notification_enabled,
                    "notification_sent": False
                })
                self._write_status_unlocked(status_data)
            logging.info(f"重启信息已记录: {reason}")

        except Exception as e:
            logging.error(f"记录重启信息失败: {e}")

    async def check_and_send_restart_notification(self) -> None:
        """检查并发送重启完成通知"""
        try:
            with self._status_lock:
                status_data = self._read_status_unlocked()
            if not status_data:
                return

            # 检查是否需要发送通知且未发送
            need_notification = status_data.get("need_notification", False)
            notification_sent = status_data.get("notification_sent", False)

            if need_notification and not notification_sent:
                # 尝试发送通知
                success = await self._send_restart_notification(status_data)

                # 只有在发送成功时才标记为已发送
                if success:
                    with self._status_lock:
                        latest_data = self._read_status_unlocked()
                        latest_data["notification_sent"] = True
                        latest_data["notification_time"] = datetime.now().isoformat()
                        self._write_status_unlocked(latest_data)

                    logging.info("重启完成通知已成功发送并记录")
                else:
                    logging.warning("重启通知发送失败，状态未更新，将在下次连接时重试")

        except Exception as e:
            logging.error(f"检查重启通知失败: {e}")

    async def _send_restart_notification(self, status_data: Dict[str, Any]) -> bool:
        """发送重启完成通知给超级用户

        Returns:
            bool: 是否发送成功（至少发送给一个超级用户）
        """
        try:
            from nonebot import get_driver, get_bots

            # 获取超级用户列表
            driver = get_driver()
            superusers = driver.config.superusers

            if not superusers:
                logging.warning("没有配置超级用户，无法发送重启通知")
                return False

            # 获取当前机器人实例
            bots = get_bots()
            if not bots:
                logging.warning("没有活跃的机器人实例，无法发送重启通知")
                return False

            # 使用第一个可用的机器人
            bot = next(iter(bots.values()))

            # 构建通知消息
            restart_reason = status_data.get("restart_reason", "未知原因")
            restart_count = status_data.get("restart_count", 0)
            last_restart = status_data.get("last_restart", "未知时间")

            # 计算运行时长
            start_time = status_data.get("start_time", time.time())
            uptime_seconds = time.time() - start_time
            uptime_minutes = int(uptime_seconds // 60)
            uptime_hours = int(uptime_minutes // 60)

            if uptime_hours > 0:
                uptime_str = f"{uptime_hours}小时{uptime_minutes % 60}分钟"
            else:
                uptime_str = f"{uptime_minutes}分钟"

            notification_text = f"""
🎉 机器人重启完成通知

🔹 重启原因: {restart_reason}
🔹 重启时间: {last_restart[:19].replace('T', ' ')}
🔹 当前运行时长: {uptime_str}
🔹 总重启次数: {restart_count}

✅ 系统已恢复正常运行！
""".strip()

            # 发送通知给所有超级用户
            success_count = 0
            for user_id in superusers:
                try:
                    await bot.send_private_msg(user_id=int(user_id), message=notification_text)
                    success_count += 1
                    logging.info(f"重启通知已发送给超级用户: {user_id}")
                except Exception as e:
                    logging.error(f"向超级用户 {user_id} 发送重启通知失败: {e}")

            if success_count > 0:
                logging.info(f"重启完成通知发送成功，共发送给 {success_count} 个超级用户")
                return True
            else:
                logging.error("重启通知发送失败，没有成功发送给任何超级用户")
                return False

        except Exception as e:
            logging.error(f"发送重启通知失败: {e}")
            return False

    async def get_status_info(self) -> Dict[str, Any]:
        """获取状态信息"""
        try:
            with self._status_lock:
                status_data = self._read_status_unlocked()

            # 计算运行时长
            start_time = status_data.get('start_time', self.start_time)
            uptime_seconds = time.time() - start_time
            uptime_minutes = int(uptime_seconds // 60)
            uptime_hours = int(uptime_minutes // 60)
            uptime_days = int(uptime_hours // 24)

            if uptime_days > 0:
                uptime_str = f"{uptime_days}天{uptime_hours % 24}小时{uptime_minutes % 60}分钟"
            elif uptime_hours > 0:
                uptime_str = f"{uptime_hours}小时{uptime_minutes % 60}分钟"
            else:
                uptime_str = f"{uptime_minutes}分钟"

            # 格式化最后重启时间
            last_restart = status_data.get('last_restart', '从未重启')
            if last_restart != '从未重启':
                last_restart = last_restart[:19].replace('T', ' ')

            # 格式化最后启动时间
            last_startup = status_data.get('last_startup', '未知')
            if last_startup != '未知':
                last_startup = last_startup[:19].replace('T', ' ')

            return {
                'last_startup': last_startup,
                'last_restart': last_restart,
                'restart_reason': status_data.get('restart_reason', '无'),
                'restart_count': status_data.get('restart_count', 0),
                'uptime': uptime_str,
                'notification_enabled': self.config.restart_notification_enabled,
                'notification_sent': status_data.get('notification_sent', False),
                'notification_time': status_data.get('notification_time', '未发送')
            }

        except Exception as e:
            logging.error(f"获取状态信息失败: {e}")
            return {
                'last_startup': '未知',
                'last_restart': '未知',
                'restart_reason': '未知',
                'restart_count': 0,
                'uptime': '未知',
                'notification_enabled': False,
                'notification_sent': False,
                'notification_time': '未发送'
            }

    async def _load_status(self) -> Dict[str, Any]:
        """加载状态数据"""
        try:
            with self._status_lock:
                return self._read_status_unlocked()
        except Exception as e:
            logging.error(f"加载状态文件失败: {e}")
            return {}

    async def _save_status(self, status_data: Dict[str, Any]) -> None:
        """保存状态数据"""
        try:
            with self._status_lock:
                self._write_status_unlocked(status_data)
        except Exception as e:
            logging.error(f"保存状态文件失败: {e}")

    def _read_status_unlocked(self) -> Dict[str, Any]:
        """读取状态数据（调用方负责持有锁）。"""
        if not os.path.exists(self.status_file):
            return {}
        try:
            with open(self.status_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception as e:
            logging.error(f"读取状态文件失败: {e}")
            return {}

    def _write_status_unlocked(self, status_data: Dict[str, Any]) -> None:
        """原子写入状态数据（调用方负责持有锁）。"""
        status_dir = os.path.dirname(self.status_file) or "."
        os.makedirs(status_dir, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(prefix=".status.", suffix=".tmp", dir=status_dir)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(status_data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, self.status_file)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
