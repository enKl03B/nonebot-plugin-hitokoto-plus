from pydantic import AnyHttpUrl
from typing import Optional, Dict, Any, List, Set
from nonebot.compat import BaseModel


class Config(BaseModel):
    """一言+插件配置"""
    HITP_API_URL: AnyHttpUrl = "https://v1.hitokoto.cn"
    HITP_DEFAULT_TYPE: Optional[str] = None  # 默认一言类型，None表示随机
    
    # 一言类型映射
    HITP_TYPE_MAP: Dict[str, str] = {
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
    HITP_TEMPLATE: str = "{hitokoto}\n----------\n类型：{type_name}\n作者：{from_who_plain}\n来源：{from}"
    
    # 调用频率限制配置（秒）
    HITP_CD: int = 3  # 调用冷却时间，默认3秒
    HITP_COOLDOWN_CLEANUP_INTERVAL: int = 360  # 冷却记录清理间隔（秒），默认6分钟
    HITP_USER_RETENTION_TIME: int = 720  # 用户记录保留时间（秒），默认12分钟
    
    # 收藏功能配置
    HITP_FAVORITE_LIST_LIMIT: int = 10  # 收藏列表每页显示数量
    HITP_FAVORITE_TEMPLATE: str = "{content}\n——《{source}》{creator}"  # 收藏列表显示模板
    HITP_FAVORITE_TIMEOUT: int = 30  # 收藏提示超时时间（秒）
    
    # 黑白名单配置
    HITP_USE_WHITELIST: bool = False  # 是否启用白名单模式，True为白名单，False为黑名单
    HITP_USER_LIST: List[str] = []  # 用户ID列表，格式为"platform:user_id"
    HITP_GROUP_LIST: List[str] = []  # 群组ID列表，格式为"platform:group_id" 