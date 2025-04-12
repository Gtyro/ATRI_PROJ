import logging
import time
from typing import Dict, List, Optional

from ..storage.repository import Repository

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
        self.last_decay_time = time.time()
        logging.info(f"记忆衰减管理器已创建，衰减率: {decay_rate}")
    
    async def apply_decay(self, force: bool = False) -> int:
        """应用记忆衰减
        
        Args:
            force: 是否强制执行，忽略时间间隔
            
        Returns:
            处理的节点数量
        """
        current_time = time.time()
        # 默认每天执行一次衰减（24*60*60=86400秒）
        if not force and (current_time - self.last_decay_time) < 86400:
            logging.info("记忆衰减间隔未到，跳过")
            return 0
            
        nodes = await self.repository.get_nodes()
        processed = 0
        
        for node in nodes:
            # 跳过激活水平很高的节点
            if node.act_lv > 0.8:
                continue
                
            # 应用衰减
            if await self.repository.apply_decay(str(node.id), self.decay_rate):
                processed += 1
        
        self.last_decay_time = current_time
        logging.info(f"记忆衰减完成，处理了 {processed} 个节点")
        return processed
    
    async def strengthen_memory(self, node_id: str, boost_factor: float = 0.1) -> bool:
        """增强特定节点的记忆强度
        
        Args:
            node_id: 节点ID
            boost_factor: 增强因子
            
        Returns:
            是否成功
        """
        try:
            nodes = await self.repository.get_nodes()
            for node in nodes:
                if str(node.id) == node_id:
                    # 增加激活水平，但最大为1.0
                    node.act_lv = min(1.0, node.act_lv + boost_factor)
                    await node.save()
                    logging.info(f"增强节点记忆: {node.name}, 新激活水平: {node.act_lv}")
                    return True
            return False
        except Exception as e:
            logging.error(f"增强记忆失败: {e}")
            return False
    
    async def forget_node(self, node_id: str) -> bool:
        """强制遗忘某个节点
        
        实际上只是将其激活水平设为很低的值
        
        Args:
            node_id: 节点ID
            
        Returns:
            是否成功
        """
        try:
            nodes = await self.repository.get_nodes()
            for node in nodes:
                if str(node.id) == node_id:
                    node.act_lv = 0.1
                    await node.save()
                    logging.info(f"已强制降低节点激活水平: {node.name}")
                    return True
            return False
        except Exception as e:
            logging.error(f"强制遗忘节点失败: {e}")
            return False 