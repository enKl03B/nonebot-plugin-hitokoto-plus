from pydantic import AnyHttpUrl
from typing import Optional, Dict, Any, List, Set
from nonebot.compat import BaseModel


class Config(BaseModel):
    """一言+插件配置"""
    hitokoto_api_url: AnyHttpUrl = "https://v1.hitokoto.cn"
    hitokoto_default_type: Optional[str] = None  # 默认一言类型，None表示随机
    
    # 一言类型映射
    hitokoto_type_map: Dict[str, str] = {
        "动画": "a",
        "漫画": "b",
        "游戏": "c",
        "文学": "d",
        "原创": "e",
        "网络": "f",
        "其他": "g",
        "影视": "h",
        "诗词": "i",
        "网易云": "j",
        "哲学": "k",
        "抖机灵": "l"
    }
    
    # 固定回复模板，不允许用户自定义
    hitokoto_template: str = "{hitokoto}\n----------\n类型：{type_name}\n作者：{from_who_plain}\n来源：{from}"
    
    # 调用频率限制配置（秒）
    hitokoto_cd: int = 3  # 调用冷却时间，默认3秒
    hitokoto_cooldown_cleanup_interval: int = 150  # 冷却记录清理间隔（秒）
    hitokoto_user_retention_time: int = 250  # 用户记录保留时间（秒）
    
    # 收藏功能配置
    hitokoto_favorite_list_limit: int = 10  # 收藏列表每页显示数量
    hitokoto_favorite_template: str = "{content}\n——《{source}》{creator}"  # 收藏列表显示模板
    hitokoto_favorite_timeout: int = 30  # 收藏提示超时时间（秒）
    
    # 黑白名单配置
    hitokoto_use_whitelist: bool = False  # 是否启用白名单模式，True为白名单，False为黑名单
    hitokoto_user_list: Set[str] = set()  # 用户ID列表，格式为"platform:user_id"
    hitokoto_group_list: Set[str] = set()  # 群组ID列表，格式为"platform:group_id" 