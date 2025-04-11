from typing import List, Optional, Dict, Union, Set
from nonebot import get_plugin_config
from pydantic import BaseModel
from nonebot.compat import field_validator, model_validator

class HitokotoConfig(BaseModel):
    """一言插件配置类
    
    用于定义和验证一言插件的所有配置项，包括API设置、
    用户交互设置、频率限制、黑白名单等
    """
    # API地址设置
    api_url: str = "https://v1.hitokoto.cn"  # 一言API的基础URL
    
    # 默认句子类型设置
    # 可选值为 a, b, c, d, e, f, g, h, i, j, k, l
    # a: 动画 b: 漫画 c: 游戏 d: 文学 e: 原创 f: 网络 g: 其他
    # h: 影视 i: 诗词 j: 网易云 k: 哲学 l: 抖机灵
    # 若为None则随机获取所有类型
    default_type: Optional[str] = None
    
    # 用户交互设置
    command_aliases: Set[str] = {"一言", "hitokoto"}  # 命令别名
    enable_private_chat: bool = True    # 是否在私聊中启用
    enable_group_chat: bool = True      # 是否在群聊中启用
    
    # 频率限制（秒）
    rate_limit_private: int = 5      # 私聊冷却时间
    rate_limit_group: int = 10       # 群聊冷却时间
    
    # 黑白名单设置
    enable_whitelist: bool = False   # 是否启用白名单
    enable_blacklist: bool = False   # 是否启用黑名单
    whitelist_users: List[str] = []  # 白名单用户列表
    blacklist_users: List[str] = []  # 黑名单用户列表
    whitelist_groups: List[str] = [] # 白名单群组列表
    blacklist_groups: List[str] = [] # 黑名单群组列表
    
    # 收藏设置
    max_favorites_per_user: int = 100  # 每个用户最大收藏数量
    favorites_per_page: int = 5        # 收藏列表每页显示的句子数量
    favorite_timeout: int = 60        # 收藏超时时间（秒），在获取句子后多长时间内可以收藏
    max_details_per_request: int = 3   # 单次查看详情的最大数量
    
    @field_validator('default_type')
    def check_type(cls, v):
        """验证句子类型是否有效"""
        if v is not None and v not in "abcdefghijkl":
            raise ValueError("句子类型必须是 a,b,c,d,e,f,g,h,i,j,k,l 之一")
        return v 

    @field_validator('rate_limit_private', 'rate_limit_group', 'max_favorites_per_user', 'favorite_timeout', 'max_details_per_request')
    def check_positive_int(cls, v, info):
        """验证整数类型参数必须为正数"""
        if v <= 0:
            field_name = info.field_name
            raise ValueError(f"{field_name} 必须为正整数")
        return v

    @field_validator('command_aliases')
    def check_command_aliases(cls, v):
        """验证命令别名至少有一个有效值"""
        if not v or len(v) == 0:
            raise ValueError("命令别名至少需要设置一个")
        return v

    @model_validator(mode='after')
    def check_config_consistency(self):
        """验证配置的一致性和合理性"""
        # 验证黑白名单不能同时启用
        if self.enable_whitelist and self.enable_blacklist:
            raise ValueError("白名单与黑名单不能同时启用，请只启用其中一种")
        
        
        # 验证至少启用一种聊天模式
        if not (self.enable_private_chat or self.enable_group_chat):
            raise ValueError("私聊和群聊不能同时禁用，请至少启用一种聊天模式")
            
        # 验证频率限制的合理性
        if self.rate_limit_private < 1:
            raise ValueError("私聊频率限制不能小于1秒")
        if self.rate_limit_group < 1:
            raise ValueError("群聊频率限制不能小于1秒")
            
        return self 