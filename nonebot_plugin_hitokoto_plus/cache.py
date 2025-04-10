import time
from typing import Dict, Any, List, Optional, Tuple, Set, OrderedDict
from collections import OrderedDict
from .api import HitokotoSentence
import json
import os
import asyncio
from datetime import datetime
import random
from nonebot import logger

class LRUCache:
    """LRU缓存实现"""
    
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = OrderedDict()
        
    def get(self, key: str) -> Optional[Any]:
        if key not in self.cache:
            return None
        # 移动到最新位置
        self.cache.move_to_end(key)
        return self.cache[key]
        
    def put(self, key: str, value: Any):
        if key in self.cache:
            # 更新现有项
            self.cache.move_to_end(key)
        self.cache[key] = value
        # 如果超出容量，删除最旧的项
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)
            
    def clear(self):
        self.cache.clear()

class HitokotoCache:
    """一言缓存管理器"""
    
    def __init__(self, max_size: int = 100, ttl: int = 3600):
        """
        初始化缓存管理器
        
        Args:
            max_size: 最大缓存条数
            ttl: 缓存过期时间（秒）
        """
        self.max_size = max_size
        self.ttl = ttl
        
        # 使用LRU缓存存储句子
        self.type_cache: Dict[str, LRUCache] = {}
        
        # 最近使用的句子记录，防止重复
        self.recently_used: Dict[str, Set[str]] = {}
        
        # 缓存统计信息
        self.stats = {
            "hits": 0,
            "misses": 0,
            "last_cleanup": time.time()
        }
        
        # 定期清理标志
        self.cleanup_running = False
        
        # 缓存预热标志
        self.warmup_running = False
    
    def add(self, sentence: HitokotoSentence, sentence_type: Optional[str] = None):
        """
        添加句子到缓存
        
        Args:
            sentence: 一言句子
            sentence_type: 句子类型
        """
        # 确定类型
        type_key = sentence_type or sentence.type or "default"
        
        # 确保该类型的LRU缓存存在
        if type_key not in self.type_cache:
            self.type_cache[type_key] = LRUCache(self.max_size)
            self.recently_used[type_key] = set()
        
        # 添加数据，包含时间戳
        data = sentence.dict()
        cache_item = {"data": data, "timestamp": time.time()}
        
        # 使用LRU缓存存储
        self.type_cache[type_key].put(str(sentence.id), cache_item)
    
    def get_random(self, sentence_type: Optional[str] = None) -> Optional[HitokotoSentence]:
        """
        从缓存获取一条随机句子，避免短时间内重复
        
        Args:
            sentence_type: 句子类型
            
        Returns:
            Optional[HitokotoSentence]: 随机句子或None
        """
        # 确定类型
        type_key = sentence_type or "default"
        
        # 检查是否有对应类型的缓存
        if type_key not in self.type_cache:
            self.stats["misses"] += 1
            return None
            
        # 获取当前时间戳
        current_time = time.time()
        
        # 获取所有未过期的句子
        valid_sentences = []
        lru_cache = self.type_cache[type_key]
        
        # 遍历LRU缓存获取有效句子
        for sentence_id, item in lru_cache.cache.items():
            if current_time - item["timestamp"] < self.ttl:
                valid_sentences.append(item)
        
        if not valid_sentences:
            self.stats["misses"] += 1
            return None
            
        # 确保每个类型的最近使用记录存在
        if type_key not in self.recently_used:
            self.recently_used[type_key] = set()
            
        # 过滤出未被最近使用的句子
        unused_sentences = [
            item for item in valid_sentences 
            if str(item["data"]["id"]) not in self.recently_used[type_key]
        ]
        
        # 如果所有句子都被使用过了，就清空最近使用记录
        chosen_item = None
        if not unused_sentences:
            logger.debug(f"所有缓存的 {type_key} 类型句子都已使用过，重置最近使用记录")
            self.recently_used[type_key].clear()
            chosen_item = random.choice(valid_sentences)
        else:
            # 从未使用的句子中随机选择
            chosen_item = random.choice(unused_sentences)
        
        # 添加到最近使用记录
        sentence_id = str(chosen_item["data"]["id"])
        self.recently_used[type_key].add(sentence_id)
        
        # 如果最近使用记录太大，清理一部分
        if len(self.recently_used[type_key]) > min(self.max_size // 2, 20):
            # 保留最近的一部分记录
            self.recently_used[type_key] = set(list(self.recently_used[type_key])[-10:])
            
        # 更新统计信息
        self.stats["hits"] += 1
            
        # 转换为句子对象
        return HitokotoSentence(**chosen_item["data"])
    
    async def start_cleanup_task(self):
        """启动定期清理任务"""
        if not self.cleanup_running:
            self.cleanup_running = True
            asyncio.create_task(self._cleanup_loop())
    
    async def _cleanup_loop(self):
        """定期清理过期缓存的循环任务"""
        try:
            while self.cleanup_running:
                self.cleanup()
                # 每半小时清理一次
                await asyncio.sleep(1800)
        except asyncio.CancelledError:
            self.cleanup_running = False
    
    def cleanup(self):
        """清理过期缓存"""
        current_time = time.time()
        
        for type_key in list(self.type_cache.keys()):
            lru_cache = self.type_cache[type_key]
            # 获取所有过期的键
            expired_keys = [
                key for key, item in lru_cache.cache.items()
                if current_time - item["timestamp"] >= self.ttl
            ]
            # 删除过期的项
            for key in expired_keys:
                del lru_cache.cache[key]
            
            # 如果缓存为空，删除整个类型缓存
            if not lru_cache.cache:
                del self.type_cache[type_key]
                if type_key in self.recently_used:
                    del self.recently_used[type_key]
                    
        # 更新清理时间
        self.stats["last_cleanup"] = current_time
        
        # 输出缓存统计信息
        total_items = sum(len(cache.cache) for cache in self.type_cache.values())
        hit_rate = self.stats["hits"] / (self.stats["hits"] + self.stats["misses"]) if (self.stats["hits"] + self.stats["misses"]) > 0 else 0
        logger.debug(f"缓存清理完成: 总条目数={total_items}, 命中率={hit_rate:.2%}")
    
    async def warmup(self, api_client, types: Optional[List[str]] = None):
        """缓存预热
        
        Args:
            api_client: API客户端实例
            types: 要预热的类型列表，如果为None则预热所有类型
        """
        if self.warmup_running:
            return
            
        self.warmup_running = True
        try:
            if types is None:
                types = list("abcdefghijkl")
                
            for type_key in types:
                try:
                    # 获取多条句子并缓存
                    for _ in range(min(10, self.max_size)):
                        sentence = await api_client.get_hitokoto(type_key)
                        self.add(sentence, type_key)
                    logger.info(f"类型 {type_key} 缓存预热完成")
                except Exception as e:
                    logger.error(f"类型 {type_key} 缓存预热失败: {e}")
                    
        finally:
            self.warmup_running = False
    
    def save_to_file(self, file_path: str):
        """保存缓存到文件"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 准备保存数据
            save_data = {
                "type_cache": {
                    type_key: {
                        "cache": dict(cache.cache),
                        "recently_used": list(self.recently_used.get(type_key, set()))
                    }
                    for type_key, cache in self.type_cache.items()
                },
                "stats": self.stats
            }
            
            # 写入文件
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
                
            return True
        except Exception as e:
            logger.error(f"保存缓存失败: {str(e)}")
            return False
    
    def load_from_file(self, file_path: str):
        """从文件加载缓存"""
        try:
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                    # 恢复类型缓存
                    self.type_cache = {}
                    for type_key, type_data in data.get("type_cache", {}).items():
                        lru_cache = LRUCache(self.max_size)
                        lru_cache.cache = OrderedDict(type_data["cache"])
                        self.type_cache[type_key] = lru_cache
                        
                        # 恢复最近使用记录
                        self.recently_used[type_key] = set(type_data["recently_used"])
                    
                    # 恢复统计信息
                    self.stats = data.get("stats", self.stats)
                    
                return True
            return False
        except Exception as e:
            logger.error(f"加载缓存失败: {str(e)}")
            return False 