import logging
import time
from typing import Dict, List, Optional

from ..storage.memory_repository import MemoryRepository
from ...models import GroupPluginConfig, PluginConfig

class DecayManager:
    """记忆衰减管理器

    负责处理记忆衰减相关的功能
    """

    def __init__(self, memory_repo: MemoryRepository, decay_rate: float = 0.01):
        """初始化记忆衰减管理器

        Args:
            memory_repo: 记忆存储库
            decay_rate: 衰减率
        """
        self.memory_repo = memory_repo
        self.decay_rate = decay_rate
        self.plugin_name = "persona"  # 插件名称
        self.max_nodes_per_conv = 1000  # 每个会话保留的最大节点数

    async def initialize(self):
        """初始化衰减管理器，确保配置数据存在"""
        try:
            # 检查并初始化配置数据
            await self.load_next_decay_time()
            logging.debug("衰减管理器初始化完成")
        except Exception as e:
            logging.error(f"衰减管理器初始化失败: {e}")
            raise

    async def load_next_decay_time(self) -> int:
        # 使用get_or_create确保配置存在
        plugin_config, created = await PluginConfig.get_or_create(
            plugin_name=self.plugin_name,
            defaults={"plugin_config": {"next_decay_time": time.time()}}
        )

        # 如果是新创建的，记录日志
        if created:
            logging.info(f"创建了新的衰减时间配置，下次衰减时间: {plugin_config.plugin_config.get('next_decay_time')}")

        # 确保plugin_config字典中有next_decay_time键
        if "next_decay_time" not in plugin_config.plugin_config:
            plugin_config.plugin_config["next_decay_time"] = time.time()
            await plugin_config.save()

        # 获取next_decay_time
        next_decay_time = plugin_config.plugin_config.get("next_decay_time", time.time())
        return next_decay_time

    async def set_next_decay_time(self) -> None:
        # 使用get_or_create确保配置存在
        plugin_config, created = await PluginConfig.get_or_create(
            plugin_name=self.plugin_name,
            defaults={"plugin_config": {"next_decay_time": time.time() + 4*3600}}
        )

        # 更新plugin_config中的next_decay_time
        plugin_config.plugin_config["next_decay_time"] = time.time() + 4*3600
        await plugin_config.save()
        logging.info(f"设置下次衰减时间: {plugin_config.plugin_config['next_decay_time']}")

    async def apply_decay(self, force: bool = False) -> int:
        """应用记忆衰减

        Args:
            force: 是否强制执行，忽略时间间隔

        Returns:
            处理的节点数量
        """
        next_decay_time = await self.load_next_decay_time()
        if not force and time.time() < next_decay_time:
            logging.info(f"未到下次衰减时间，跳过衰减")
            return 0

        nodes = await self.memory_repo.get_nodes()  # 不限制数量，获取所有节点
        processed_nodes = 0

        for node in nodes:
            # 应用衰减到所有节点，不再跳过高激活水平的节点
            if await self.memory_repo.apply_decay(str(node.uid), self.decay_rate):
                processed_nodes += 1

        # 应用关联关系的衰减
        processed_associations = await self.memory_repo.apply_association_decay(self.decay_rate)
        # 应用记忆权重的衰减
        processed_memories = await self.memory_repo.apply_memory_decay(self.decay_rate)

        logging.info(f"记忆衰减完成，处理了 {processed_nodes} 个节点、{processed_associations} 个关联和 {processed_memories} 个记忆")

        # 执行完衰减后，检查是否需要清理过多的节点和记忆
        await self.cleanup_old_nodes()
        await self.cleanup_old_memories()
        await self.set_next_decay_time()
        return processed_nodes + processed_associations + processed_memories # 返回总处理数

    async def cleanup_old_nodes(self) -> int:
        """清理旧节点，为每个会话只保留指定数量的节点

        Returns:
            清理的节点数量
        """
        # 获取所有使用 persona 插件的会话 ID
        try:
            conv_ids = await GroupPluginConfig.get_distinct_group_ids(self.plugin_name)
            total_cleaned = 0

            # 对每个会话进行清理
            for conv_id in conv_ids:
                cleaned = await self.forget_node_by_conv(conv_id)
                total_cleaned += cleaned

            if total_cleaned > 0:
                logging.info(f"记忆清理完成，共清理 {total_cleaned} 个节点")
            return total_cleaned

        except Exception as e:
            logging.error(f"清理旧节点失败: {e}")
            return 0

    async def cleanup_old_memories(self) -> int:
        """清理旧记忆，为每个会话只保留指定数量的记忆

        Returns:
            清理的记忆数量
        """
        try:
            # 获取所有使用 persona 插件的会话 ID
            conv_ids = await GroupPluginConfig.get_distinct_group_ids(self.plugin_name)
            total_cleaned = 0

            # 对每个会话进行记忆清理
            for conv_id in conv_ids:
                # 每个会话保留500个非永久性记忆
                cleaned = await self.memory_repo.clean_old_memories_by_conv(conv_id, max_memories=500)
                total_cleaned += cleaned

            if total_cleaned > 0:
                logging.info(f"长期记忆清理完成，共清理 {total_cleaned} 个记忆")
            return total_cleaned

        except Exception as e:
            logging.error(f"清理旧记忆失败: {e}")
            return 0

    async def forget_node_by_conv(self, conv_id: str) -> int:
        """为指定会话保留一定数量的节点，删除多余节点

        Returns:
            清理的节点数量
        """
        try:
            # 只获取非常驻节点，常驻节点不会被计入限制
            non_permanent_nodes = await self.memory_repo.get_nodes_by_conv_id(conv_id, is_permanent=False)
            non_permanent_count = len(non_permanent_nodes)

            # 如果非常驻节点数量超过了允许的限制
            # 常驻节点不计入限制，所以直接与max_nodes_per_conv比较
            if non_permanent_count > self.max_nodes_per_conv:
                # 计算需要删除的数量
                to_delete_count = non_permanent_count - self.max_nodes_per_conv

                # 获取激活水平最低的非常驻节点
                nodes_to_delete = await self.memory_repo.get_nodes_by_conv_id(
                    conv_id=conv_id,
                    order_by="act_lv",  # 按激活水平升序（从低到高）
                    limit=to_delete_count,
                    is_permanent=False  # 只获取非常驻节点
                )

                # 删除这些节点
                deleted_count = 0
                for node in nodes_to_delete:
                    success = await self.memory_repo.delete_node(str(node.uid))
                    if success:
                        deleted_count += 1

                logging.info(f"会话 {conv_id} 清理了 {deleted_count} 个非常驻节点，保留了非常驻节点 {self.max_nodes_per_conv} 个")
                return deleted_count

            return 0  # 不需要清理
        except Exception as e:
            logging.error(f"清理会话 {conv_id} 的节点失败: {e}")
            return 0 