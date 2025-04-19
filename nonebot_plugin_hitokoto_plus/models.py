from typing import Dict, List, Optional, Any, TypedDict, Union
from datetime import datetime
import json
import os
from pathlib import Path

from nonebot import get_driver, require
from nonebot.log import logger

# 导入localstore插件
require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as store


class HitokotoData(TypedDict, total=False):
    """一言API数据类型定义"""
    hitokoto: str  # 一言内容
    from_: str  # 来源，使用from_避免与Python关键字冲突
    from_who: Optional[str]  # 作者
    from_who_plain: str  # 格式化后的作者
    type: str  # 类型代码
    type_name: str  # 类型名称
    uuid: str  # 唯一标识


class HitokotoFavorite:
    """一言收藏数据模型"""
    
    def __init__(self, content: str, uuid: str, type_name: str, 
                 source: str, creator: str, created_at: Optional[datetime] = None) -> None:
        """
        初始化一言收藏
        
        参数:
            content: 一言内容
            uuid: 一言UUID
            type_name: 一言类型
            source: 一言来源
            creator: 一言创作者
            created_at: 收藏时间，默认为当前时间
        """
        self.content = content  # 一言内容
        self.uuid = uuid  # 一言UUID
        self.type_name = type_name  # 一言类型
        self.source = source  # 一言来源
        self.creator = creator  # 一言创作者
        self.created_at = created_at or datetime.now()  # 收藏时间
        
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "content": self.content,
            "uuid": self.uuid,
            "type_name": self.type_name,
            "source": self.source,
            "creator": self.creator,
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HitokotoFavorite":
        """从字典创建实例"""
        created_at = datetime.fromisoformat(data["created_at"]) if "created_at" in data else None
        return cls(
            content=data["content"],
            uuid=data["uuid"],
            type_name=data["type_name"],
            source=data["source"],
            creator=data["creator"],
            created_at=created_at
        )


class FavoriteManager:
    """收藏管理器"""
    
    def __init__(self) -> None:
        """初始化收藏管理器"""
        # 用户收藏数据 {user_id: [HitokotoFavorite, ...]}
        self._favorites: Dict[str, List[HitokotoFavorite]] = {}
        # 最后一次获取的一言内容 {user_id: HitokotoFavorite}
        self._last_hitokoto: Dict[str, HitokotoFavorite] = {}
        # 数据文件路径 - 使用localstore
        self.data_file = self._get_data_file_path()
        # 加载数据
        self._load_data()
        
    def _get_data_file_path(self) -> Path:
        """获取数据文件路径"""
        return store.get_plugin_data_file("favorites.json")
    
    def _load_data(self) -> None:
        """加载收藏数据"""
        if not self.data_file.exists():
            logger.debug("收藏数据文件不存在，将创建新文件")
            return
        
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for user_id, favorites in data.items():
                self._favorites[user_id] = [
                    HitokotoFavorite.from_dict(fav) for fav in favorites
                ]
            
            logger.debug(f"成功加载收藏数据: {len(self._favorites)}个用户")
        except Exception as e:
            logger.error(f"加载收藏数据失败: {e}")
    
    def _save_data(self) -> None:
        """保存收藏数据"""
        try:
            data: Dict[str, List[Dict[str, Any]]] = {}
            for user_id, favorites in self._favorites.items():
                data[user_id] = [fav.to_dict() for fav in favorites]
            
            # 确保父目录存在
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.debug("收藏数据保存成功")
        except Exception as e:
            logger.error(f"保存收藏数据失败: {e}")
    
    def set_last_hitokoto(self, platform: str, user_id: str, hitokoto_data: Dict[str, Any]) -> None:
        """
        设置最后一次获取的一言
        
        参数:
            platform: 平台标识
            user_id: 用户ID
            hitokoto_data: 一言数据
        """
        # 创建复合ID
        composite_id = f"{platform}:{user_id}"
        
        # 将API返回的数据转换为HitokotoFavorite对象
        self._last_hitokoto[composite_id] = HitokotoFavorite(
            content=hitokoto_data["hitokoto"],
            uuid=hitokoto_data.get("uuid", ""),
            type_name=hitokoto_data.get("type_name", "未知类型"),
            source=hitokoto_data.get("from", "未知来源"),
            creator=hitokoto_data.get("from_who_plain", "无")
        )
    
    def add_favorite(self, platform: str, user_id: str) -> Optional[HitokotoFavorite]:
        """
        添加收藏
        
        参数:
            platform: 平台标识
            user_id: 用户ID
            
        返回:
            Optional[HitokotoFavorite]: 添加成功返回收藏对象，已收藏过或无最后一言则返回None
        """
        # 创建复合ID
        composite_id = f"{platform}:{user_id}"
        
        if composite_id not in self._last_hitokoto:
            return None
        
        # 获取最后一次的一言
        favorite = self._last_hitokoto[composite_id]
        
        # 确保用户存在收藏列表
        if composite_id not in self._favorites:
            self._favorites[composite_id] = []
        
        # 检查是否已经收藏过
        for existing in self._favorites[composite_id]:
            if existing.uuid == favorite.uuid:
                return None  # 已收藏过，返回None
        
        # 添加到收藏列表
        self._favorites[composite_id].append(favorite)
        
        # 保存数据
        self._save_data()
        
        return favorite
    
    def get_favorites(self, platform: str, user_id: str) -> List[HitokotoFavorite]:
        """
        获取用户的收藏列表
        
        参数:
            platform: 平台标识
            user_id: 用户ID
            
        返回:
            List[HitokotoFavorite]: 用户的收藏列表
        """
        # 创建复合ID
        composite_id = f"{platform}:{user_id}"
        return self._favorites.get(composite_id, [])
    
    def get_favorite_by_index(self, platform: str, user_id: str, index: int) -> Optional[HitokotoFavorite]:
        """
        根据索引获取收藏
        
        参数:
            platform: 平台标识
            user_id: 用户ID
            index: 收藏索引
            
        返回:
            Optional[HitokotoFavorite]: 找到的收藏对象，未找到则返回None
        """
        # 创建复合ID
        composite_id = f"{platform}:{user_id}"
        favorites = self._favorites.get(composite_id, [])
        if 0 <= index < len(favorites):
            return favorites[index]
        return None
    
    def remove_favorite(self, platform: str, user_id: str, index: int) -> bool:
        """
        删除收藏
        
        参数:
            platform: 平台标识
            user_id: 用户ID
            index: 收藏索引
            
        返回:
            bool: 删除成功返回True，否则返回False
        """
        # 创建复合ID
        composite_id = f"{platform}:{user_id}"
        favorites = self._favorites.get(composite_id, [])
        if 0 <= index < len(favorites):
            favorites.pop(index)
            # 保存数据
            self._save_data()
            return True
        return False


# 创建全局收藏管理器实例
favorite_manager = FavoriteManager() 