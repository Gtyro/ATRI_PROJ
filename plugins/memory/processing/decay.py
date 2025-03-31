"""
记忆系统衰减管理模块 - 实现记忆衰减和整理机制

该模块负责记忆的时间衰减处理，模拟人类记忆随时间淡化的特性。
包含衰减规则的应用、弱记忆的清理等功能。
"""

import time
import logging
from typing import Optional

from tortoise.transactions import atomic
from tortoise.expressions import F

from ..storage import StorageManager, Memory, MemoryAssociation

class DecayManager:
    """负责记忆的衰减和整理"""
    
    def __init__(self, storage: StorageManager):
        self.storage = storage
        self.decay_rate = 0.05  # 默认衰减率
        self.last_decay_time = time.time()
    
    @atomic()
    async def apply_decay(self) -> None:
        """应用记忆衰减"""
        current_time = time.time()
        time_diff = (current_time - self.last_decay_time) / 3600  # 转换为小时
        
        # 仅当时间差足够大时才执行衰减
        if time_diff < 1:  # 至少1小时执行一次
            return
            
        # 计算衰减因子
        decay_factor = 1.0 - (self.decay_rate * time_diff)
        decay_factor = max(0.1, decay_factor)  # 防止衰减过度
        
        # 执行记忆衰减
        await Memory.filter(weight__gt=0.1).update(weight=F("weight") * decay_factor)
        
        # 执行关联衰减
        await MemoryAssociation.filter(strength__gt=0.1).update(strength=F("strength") * decay_factor)
        
        # 删除权重过低的关联
        await MemoryAssociation.filter(strength__lt=0.1).delete()
        
        self.last_decay_time = current_time
        
        logging.info(f"已应用记忆衰减，因子: {decay_factor:.4f}")
    
    def set_decay_rate(self, rate: float) -> None:
        """设置衰减率"""
        if 0.0 <= rate <= 1.0:
            self.decay_rate = rate
            logging.info(f"记忆衰减率已更新为: {rate}")
        else:
            logging.warning(f"衰减率设置无效: {rate}，应在0.0-1.0之间")
    
    async def consolidate_memories(self) -> None:
        """记忆整合 - 将类似记忆合并（未来扩展功能）"""
        # 此功能将在未来实现
        pass 