from typing import Dict, List, Optional
import time
from datetime import datetime

from nonebot.log import logger
from nonebot_plugin_apscheduler import scheduler

from .config import Config, plugin_config


class RateLimiter:
    """
    速率限制器类，用于管理命令调用的冷却时间和自动清理过期记录
    """
    
    def __init__(self):
        """初始化速率限制器"""
        # 用于存储最后调用时间的字典
        # 格式: {platform:user_id: last_time}
        self._last_call_time: Dict[str, float] = {}
        
        # 注册定时清理任务
        self._setup_cleanup_job()
    
    def _setup_cleanup_job(self):
        """设置定时清理任务"""
        # 注册定时任务，用于清理过期的冷却记录
        scheduler.add_job(
            self._cleanup_cooldown_records,
            "interval", 
            seconds=plugin_config.hitp_cooldown_cleanup_interval,
            id="hitokoto_cooldown_cleanup",
            replace_existing=True
        )
    
    async def _cleanup_cooldown_records(self):
        """定时清理过期的冷却记录"""
        if not self._last_call_time:
            return
        
        current_time = time.time()
        current_time_str = datetime.fromtimestamp(current_time).strftime("%Y-%m-%d %H:%M:%S")
        
        # 直接在列表创建时添加过期的用户ID
        expired_users = [
            user_id for user_id, last_time in self._last_call_time.items()
            if current_time - last_time > plugin_config.hitp_user_retention_time
        ]
        
        if expired_users:
            # 删除过期记录
            for user_id in expired_users:
                del self._last_call_time[user_id]
            
            # 记录清理结果
            logger.info(f"[{current_time_str}] 已清理 {len(expired_users)} 条过期冷却记录，当前记录数: {len(self._last_call_time)}")
        else:
            logger.debug(f"[{current_time_str}] 没有过期冷却记录需要清理，当前记录数: {len(self._last_call_time)}")
    
    async def check_rate_limit(self, composite_id: str, send_func=None) -> bool:
        """
        检查调用频率限制
        
        参数:
            composite_id: 用户标识（格式：platform:user_id）
            send_func: 可选的发送函数，用于发送冷却提示
            
        返回:
            bool: 是否允许调用，True表示允许，False表示不允许
        """
        current_time = time.time()
        current_time_str = datetime.fromtimestamp(current_time).strftime("%Y-%m-%d %H:%M:%S")
        
        # 检查是否在冷却中
        if composite_id in self._last_call_time and (elapsed := current_time - self._last_call_time[composite_id]) < plugin_config.hitp_cd:
            last_time_str = datetime.fromtimestamp(self._last_call_time[composite_id]).strftime("%Y-%m-%d %H:%M:%S")
            
            logger.debug(f"用户 {composite_id} 的冷却检查: 当前时间={current_time_str}, 上次调用={last_time_str}, 已过时间={elapsed:.2f}秒, 冷却时间={plugin_config.hitp_cd}秒")
            
            # 计算剩余冷却时间，确保至少为1秒
            remaining = max(1, round(plugin_config.hitp_cd - elapsed))
            logger.debug(f"用户 {composite_id} 仍在冷却中，剩余时间: {remaining}秒")
            
            # 如果提供了发送函数，则发送冷却提示
            if send_func:
                await send_func(f"冷却中...请等待{remaining}秒后再试")
                
            return False
        
        # 更新最后调用时间
        self._last_call_time[composite_id] = current_time
        last_time_str = datetime.fromtimestamp(current_time).strftime("%Y-%m-%d %H:%M:%S")
        logger.debug(f"用户 {composite_id} 的最后调用时间已更新为 {last_time_str}")
        return True
    
    def reset_limit(self, composite_id: str):
        """
        重置用户的冷却时间
        
        参数:
            composite_id: 用户标识（格式：platform:user_id）
        """
        if composite_id in self._last_call_time:
            del self._last_call_time[composite_id]
            logger.debug(f"已重置用户 {composite_id} 的冷却时间")
    
    def get_remaining_time(self, composite_id: str) -> Optional[float]:
        """
        获取用户的剩余冷却时间
        
        参数:
            composite_id: 用户标识（格式：platform:user_id）
            
        返回:
            Optional[float]: 剩余冷却时间（秒），如果不在冷却中则返回None
        """
        current_time = time.time()
        
        if composite_id in self._last_call_time and (elapsed := current_time - self._last_call_time[composite_id]) < plugin_config.hitp_cd:
            return plugin_config.hitp_cd - elapsed
                
        return None


# 创建全局速率限制器实例
rate_limiter = RateLimiter() 