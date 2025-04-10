from typing import Dict, Tuple, Optional
import time
from nonebot import logger

class RateLimiter:
    """请求频率限制器"""
    
    def __init__(self):
        # 存储格式：{user_id/group_id: 上次请求时间戳}
        self.user_limits: Dict[str, float] = {}
        self.group_limits: Dict[str, float] = {}
        
    def check_user(self, user_id: str, rate_limit: int = 5) -> Tuple[bool, Optional[float]]:
        """
        检查用户是否超过频率限制
        
        Args:
            user_id: 用户ID
            rate_limit: 频率限制（秒）
            
        Returns:
            (bool, float): (是否允许请求, 剩余冷却时间)
        """
        current_time = time.time()
        
        # 检查用户是否在频率限制中
        if user_id in self.user_limits:
            last_time = self.user_limits[user_id]
            elapsed = current_time - last_time
            
            if elapsed < rate_limit:
                remaining = rate_limit - elapsed
                return False, remaining
        
        # 更新用户最后请求时间
        self.user_limits[user_id] = current_time
        
        return True, None
    
    def check_group(self, group_id: str, user_id: str, rate_limit: int = 10) -> Tuple[bool, Optional[float]]:
        """
        检查群组是否超过频率限制
        
        Args:
            group_id: 群组ID
            user_id: 用户ID
            rate_limit: 频率限制（秒）
            
        Returns:
            (bool, float): (是否允许请求, 剩余冷却时间)
        """
        current_time = time.time()
        
        # 检查群组是否在频率限制中
        if group_id in self.group_limits:
            last_time = self.group_limits[group_id]
            elapsed = current_time - last_time
            
            if elapsed < rate_limit:
                remaining = rate_limit - elapsed
                return False, remaining
        
        # 更新群组最后请求时间
        self.group_limits[group_id] = current_time
        
        return True, None
    
    def clear_expired(self, expiry_time: int = 3600):
        """清理过期的频率限制记录"""
        current_time = time.time()
        
        # 清理用户记录
        expired_users = [
            user_id for user_id, last_time in self.user_limits.items()
            if current_time - last_time > expiry_time
        ]
        for user_id in expired_users:
            del self.user_limits[user_id]
            
        # 清理群组记录
        expired_groups = [
            group_id for group_id, last_time in self.group_limits.items()
            if current_time - last_time > expiry_time
        ]
        for group_id in expired_groups:
            del self.group_limits[group_id] 