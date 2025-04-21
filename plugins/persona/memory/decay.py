import logging
import time
from typing import Dict, List, Optional

from ..storage.repository import Repository
from ...models import GroupPluginConfig

class DecayManager:
    """记忆衰减管理器
    
    负责处理记忆衰减相关的功能
    """
    
    def __init__(self, repository: Repository, decay_rate: float = 0.01):
        """初始化记忆衰减管理器
        
        Args:
            repository: 存储仓库
            decay_rate: 衰减率
        """
        self.repository = repository
        self.decay_rate = decay_rate
        self.plugin_name = "persona"  # 插件名称
        self.max_nodes_per_conv = 1000  # 每个会话保留的最大节点数
        logging.info(f"记忆衰减管理器已创建，衰减率: {decay_rate}")
    
    async def apply_decay(self, force: bool = False) -> int:
        """应用记忆衰减
        
        Args:
            force: 是否强制执行，忽略时间间隔
            
        Returns:
            处理的节点数量
        """
            
        nodes = await self.repository.get_nodes(limit=None)  # 不限制数量，获取所有节点
        processed = 0
        
        for node in nodes:
            # 应用衰减到所有节点，不再跳过高激活水平的节点
            if await self.repository.apply_decay(str(node.id), self.decay_rate):
                processed += 1
        
        # 应用关联关系的衰减
        associations_processed = await self.repository.apply_association_decay(self.decay_rate)
        logging.info(f"关联关系衰减完成，处理了 {associations_processed} 个关联")
        
        logging.info(f"记忆衰减完成，处理了 {processed} 个节点和 {associations_processed} 个关联")
        
        # 执行完衰减后，检查是否需要清理过多的节点
        await self.cleanup_old_nodes()
        
        return processed
    
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
    
    async def forget_node_by_conv(self, conv_id: str) -> int:
        """为指定会话保留一定数量的节点，删除多余节点
        
        Args:
            conv_id: 会话ID
            
        Returns:
            清理的节点数量
        """
        try:
            # 获取该会话的节点总数
            all_nodes = await self.repository.get_nodes_by_conv_id(conv_id)
            total_nodes = len(all_nodes)
            
            # 如果节点数超过限制，删除多余的节点（从激活水平最低的开始删除）
            if total_nodes > self.max_nodes_per_conv:
                # 计算需要删除的数量
                to_delete_count = total_nodes - self.max_nodes_per_conv
                
                # 直接获取激活水平最低的节点
                nodes_to_delete = await self.repository.get_nodes_by_conv_id(
                    conv_id=conv_id,
                    order_by="act_lv",  # 按激活水平升序（从低到高）
                    limit=to_delete_count
                )
                
                # 删除这些节点
                deleted_count = 0
                for node in nodes_to_delete:
                    success = await self.repository.delete_node(str(node.id))
                    if success:
                        deleted_count += 1
                
                logging.info(f"会话 {conv_id} 清理了 {deleted_count} 个节点，保留了 {self.max_nodes_per_conv} 个")
                return deleted_count
            
            return 0  # 不需要清理
        except Exception as e:
            logging.error(f"清理会话 {conv_id} 的节点失败: {e}")
            return 0 