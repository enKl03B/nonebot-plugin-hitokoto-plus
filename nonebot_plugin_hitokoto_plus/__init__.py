from nonebot import get_driver, get_plugin_config, logger
from nonebot.plugin import PluginMetadata
from nonebot.adapters import Message, Event
from nonebot.typing import T_State
from nonebot.matcher import Matcher
from nonebot.permission import SUPERUSER
from nonebot.compat import type_validate_python

# Alconna相关导入
from nonebot_plugin_alconna import on_alconna, AlconnaMatch, AlconnaMatches, CommandResult, Query, Alconna, Args, Option, Subcommand
from nonebot_plugin_alconna.uniseg import UniMessage

# 适配器导入，提供跨平台支持
from nonebot.adapters.onebot.v11 import (
    Adapter as OneBotV11Adapter,
    Bot as OneBotV11Bot,
    GroupMessageEvent, 
    GROUP_ADMIN, 
    GROUP_OWNER
)

import httpx
import json
from typing import Optional, Dict, Any, List, Union, cast
import asyncio
from datetime import datetime, timedelta
import os
import re
import time

from .config import HitokotoConfig
from .api import HitokotoAPI, HitokotoSentence
from .rate_limiter import RateLimiter
from .cache import HitokotoCache

__plugin_meta__ = PluginMetadata(
    name="一言+",
    description="获取来自 hitokoto.cn 的一句话",
    usage="""
    使用方法：
    - 发送 /一言 获取随机一言
    - 发送 /一言 <类型> 获取指定类型的一言，类型可以是：
      - 动画: a
      - 漫画: b
      - 游戏: c
      - 文学: d
      - 原创: e
      - 网络: f
      - 其他: g
      - 影视: h
      - 诗词: i
      - 网易云: j
      - 哲学: k
      - 抖机灵: l
      
    收藏功能：
    - 发送 /一言收藏 将上一句添加到收藏
    - 发送 /一言收藏列表 [页码] 查看已收藏的句子，可选参数：页码
    - 发送 /一言收藏删除 <序号> 删除指定序号的收藏
    """,
    type="application",
    homepage="https://github.com/enKl03B/nonebot-plugin-hitokoto-plus",
    config=None,
)

# 插件配置
hitokoto_config = get_plugin_config(HitokotoConfig)

# 创建API客户端
api = HitokotoAPI(hitokoto_config.api_url)

# 创建频率限制器
rate_limiter = RateLimiter()

# 创建缓存管理器
cache = HitokotoCache(
    max_size=hitokoto_config.cache_size, 
    ttl=hitokoto_config.cache_ttl
)

# 用户收藏
# 格式: {user_id: [HitokotoSentence, ...]}
user_favorites: Dict[str, List[Dict[str, Any]]] = {}

# 最后获取的句子
# 格式: {user_id: {"sentence": HitokotoSentence, "timestamp": 时间戳}}
last_sentences: Dict[str, Dict[str, Any]] = {}

# 待确认的删除操作
# 格式: {user_id: {"index": index, "timestamp": timestamp}}
pending_deletes: Dict[str, Dict[str, Any]] = {}

# 删除确认超时时间（秒）
DELETE_CONFIRM_TIMEOUT = 60

# 自动保存间隔（秒）
AUTO_SAVE_INTERVAL = 300  # 5分钟

# 自动保存任务
auto_save_task = None

# 使用Alconna创建命令
hitokoto_alc = Alconna(
    "一言",
    Args["type?", str],
    Option("--help", help_text="显示帮助信息"),
    alias=list(hitokoto_config.command_aliases)
)

# 收藏命令
favorite_alc = Alconna(
    "一言收藏",
    Option("--help", help_text="显示帮助信息"),
    Subcommand("列表", Args["page?", int], help_text="查看收藏的句子列表，可选参数：页码"),
    Subcommand("删除", Args["index", int], help_text="删除指定序号的收藏")
)

# 使用Alconna注册命令
hitokoto_cmd = on_alconna(hitokoto_alc, priority=5)
favorite_cmd = on_alconna(favorite_alc, priority=5)

# 初始化
driver = get_driver()

@driver.on_startup
async def on_startup():
    """插件启动时的处理"""
    # 启动缓存清理任务
    if hitokoto_config.enable_cache:
        await cache.start_cleanup_task()
        
        # 尝试从文件加载缓存
        cache_dir = os.path.join(os.path.dirname(__file__), "data")
        cache_file = os.path.join(cache_dir, "cache.json")
        cache.load_from_file(cache_file)
        
        # 执行缓存预热
        if hitokoto_config.enable_cache_warmup:
            logger.info("开始执行缓存预热...")
            await cache.warmup(api, hitokoto_config.warmup_types)
            logger.info("缓存预热完成")
    
    # 加载收藏数据
    await load_favorites()
    
    # 启动自动保存任务
    global auto_save_task
    auto_save_task = asyncio.create_task(auto_save_favorites())

    # 注册适配器
    try:
        _adapters = driver.adapters.keys()
        logger.info(f"已注册的适配器: {', '.join(_adapters)}")
    except Exception as e:
        logger.warning(f"获取适配器列表失败: {e}")
    
    logger.info("一言插件已启动")

@driver.on_shutdown
async def on_shutdown():
    """插件关闭时的处理"""
    # 关闭API客户端
    await api.close()
    
    # 保存缓存
    if hitokoto_config.enable_cache:
        cache_dir = os.path.join(os.path.dirname(__file__), "data")
        cache_file = os.path.join(cache_dir, "cache.json")
        cache.save_to_file(cache_file)
    
    # 保存收藏数据
    await save_favorites()
    
    # 取消自动保存任务
    global auto_save_task
    if auto_save_task and not auto_save_task.done():
        auto_save_task.cancel()
        try:
            await auto_save_task
        except asyncio.CancelledError:
            pass
    
    logger.info("一言插件已关闭")

async def auto_save_favorites():
    """自动保存收藏数据的任务"""
    try:
        while True:
            # 等待指定的时间间隔
            await asyncio.sleep(AUTO_SAVE_INTERVAL)
            
            # 保存收藏数据
            await save_favorites()
            logger.debug("自动保存收藏数据完成")
    except asyncio.CancelledError:
        # 任务被取消，正常退出
        pass
    except Exception as e:
        # 发生异常，记录日志
        logger.error(f"自动保存收藏数据失败: {str(e)}")
        # 尝试重新启动任务
        global auto_save_task
        auto_save_task = asyncio.create_task(auto_save_favorites())

async def load_favorites():
    """从文件加载收藏数据"""
    global user_favorites
    try:
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(data_dir, exist_ok=True)
        file_path = os.path.join(data_dir, "favorites.json")
        backup_file_path = os.path.join(data_dir, "favorites.json.bak")
        
        # 尝试加载主文件
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    user_favorites = json.load(f)
                logger.info(f"已从主文件加载{sum(len(favs) for favs in user_favorites.values())}条收藏记录")
                return
            except Exception as e:
                logger.error(f"加载主文件失败: {str(e)}")
                # 如果主文件加载失败，尝试从备份文件加载
                if os.path.exists(backup_file_path):
                    try:
                        with open(backup_file_path, "r", encoding="utf-8") as f:
                            user_favorites = json.load(f)
                        # 如果备份文件加载成功，将其复制为主文件
                        os.replace(backup_file_path, file_path)
                        logger.info(f"已从备份文件加载{sum(len(favs) for favs in user_favorites.values())}条收藏记录")
                        return
                    except Exception as backup_error:
                        logger.error(f"加载备份文件失败: {str(backup_error)}")
        
        # 如果主文件和备份文件都不存在或都加载失败，初始化空收藏
        user_favorites = {}
        logger.info("未找到收藏数据，初始化空收藏")
    except Exception as e:
        logger.error(f"加载收藏数据失败: {str(e)}")
        user_favorites = {}

async def save_favorites():
    """保存收藏数据到文件"""
    try:
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(data_dir, exist_ok=True)
        file_path = os.path.join(data_dir, "favorites.json")
        
        # 先保存到临时文件
        temp_file_path = os.path.join(data_dir, "favorites.json.tmp")
        with open(temp_file_path, "w", encoding="utf-8") as f:
            json.dump(user_favorites, f, ensure_ascii=False, indent=2)
        
        # 如果临时文件保存成功，则替换原文件
        # 这样可以确保在写入过程中不会因为意外停止导致数据损坏
        if os.path.exists(file_path):
            # 备份原文件
            backup_file_path = os.path.join(data_dir, "favorites.json.bak")
            os.replace(file_path, backup_file_path)
        
        # 将临时文件重命名为正式文件
        os.replace(temp_file_path, file_path)
        
        # 如果一切正常，删除备份文件
        backup_file_path = os.path.join(data_dir, "favorites.json.bak")
        if os.path.exists(backup_file_path):
            os.remove(backup_file_path)
            
        logger.info(f"已保存{sum(len(favs) for favs in user_favorites.values())}条收藏记录")
    except Exception as e:
        logger.error(f"保存收藏数据失败: {str(e)}")
        # 如果保存失败，尝试恢复备份
        try:
            backup_file_path = os.path.join(data_dir, "favorites.json.bak")
            if os.path.exists(backup_file_path):
                os.replace(backup_file_path, file_path)
                logger.info("已从备份恢复收藏数据")
        except Exception as restore_error:
            logger.error(f"从备份恢复收藏数据失败: {str(restore_error)}")

@hitokoto_cmd.handle()
async def handle_hitokoto(
    event: Event, 
    matcher: Matcher,
    type_arg: AlconnaMatch["type"] = AlconnaMatch("type"),
    help_option: AlconnaMatch[bool] = AlconnaMatch("help")
):
    """处理一言命令"""
    # 检查是否请求帮助
    if help_option.available:
        help_text = """一言+插件使用帮助:
- /一言 - 获取随机一言
- /一言 <类型> - 获取指定类型的一言
  类型可以是: a(动画), b(漫画), c(游戏), d(文学), e(原创),
  f(网络), g(其他), h(影视), i(诗词), j(网易云), k(哲学), l(抖机灵)
- /一言收藏 - 收藏上一次获取的句子
- /一言收藏列表 - 查看已收藏的句子
- /一言收藏删除 <序号> - 删除指定序号的收藏
        """
        await UniMessage(help_text).send()
        return
    
    # 检查是否在群聊
    is_group = hasattr(event, "group_id") and event.group_id is not None
    
    # 检查是否在私聊
    is_private = (not is_group)
    
    # 检查是否启用对应的聊天类型
    if is_group and not hitokoto_config.enable_group_chat:
        return
        
    if is_private and not hitokoto_config.enable_private_chat:
        return
    
    # 获取用户ID和群组ID
    user_id = str(getattr(event, "user_id", ""))
    group_id = str(getattr(event, "group_id", "")) if is_group else ""
    
    # 检查黑白名单
    if hitokoto_config.enable_whitelist:
        if is_group and group_id not in hitokoto_config.whitelist_groups:
            return
        if user_id not in hitokoto_config.whitelist_users:
            return
            
    if hitokoto_config.enable_blacklist:
        if is_group and group_id in hitokoto_config.blacklist_groups:
            return
        if user_id in hitokoto_config.blacklist_users:
            return
    
    # 检查频率限制
    if is_group:
        allowed, remaining = rate_limiter.check_group(
            group_id,
            user_id, 
            hitokoto_config.rate_limit_group
        )
        if not allowed:
            await UniMessage(f"群组冷却中，请等待 {remaining:.1f} 秒").send()
            return
    else:
        allowed, remaining = rate_limiter.check_user(
            user_id, 
            hitokoto_config.rate_limit_private
        )
        if not allowed:
            await UniMessage(f"冷却中，请等待 {remaining:.1f} 秒").send()
            return
    
    # 处理参数，提取句子类型
    sentence_type = hitokoto_config.default_type
    
    # 解析类型参数
    if type_arg.available:
        arg_text = type_arg.result
        # 检查是否是合法的类型值
        type_match = re.search(r'([a-l])', arg_text)
        if type_match:
            sentence_type = type_match.group(1)
    
    try:
        sentence = None
        
        # 尝试从缓存获取句子
        if hitokoto_config.enable_cache:
            sentence = cache.get_random(sentence_type)
            
        # 缓存中没有找到，从API获取
        if sentence is None:
            sentence = await api.get_hitokoto(sentence_type)
            
            # 添加到缓存
            if hitokoto_config.enable_cache:
                cache.add(sentence, sentence_type)
        
        # 保存最后获取的句子和时间戳
        if isinstance(sentence, HitokotoSentence):
            sentence_dict = sentence.model_dump()
        else:
            sentence_dict = dict(sentence)
        
        # 更新用户最后获取的句子记录，添加时间戳
        last_sentences[user_id] = {
            "sentence": sentence_dict,
            "timestamp": time.time()
        }
        
        # 格式化输出
        message = api.format_sentence(sentence, with_source=True, with_author=True)
        
        # 获取命令前缀
        command_prefix = "/"  # 默认前缀
        try:
            # 尝试从驱动获取命令前缀
            if hasattr(driver, "config") and hasattr(driver.config, "COMMAND_START"):
                command_prefix = driver.config.COMMAND_START[0] if driver.config.COMMAND_START else "/"
        except:
            pass
        
        # 添加收藏提示
        message += f"\n\n在 {hitokoto_config.favorite_timeout} 秒内发送{command_prefix}一言收藏可收藏该句"
            
        await UniMessage(message).send()
    except Exception as e:
        logger.error(f"获取一言失败: {str(e)}")
        await UniMessage(f"获取一言失败: {str(e)}").send()

@favorite_cmd.handle()
async def handle_favorite(
    event: Event, 
    matcher: Matcher,
    res: CommandResult = AlconnaMatches(),
    help_option: AlconnaMatch[bool] = AlconnaMatch("help")
):
    """处理收藏命令"""
    # 检查是否请求帮助
    if help_option.available:
        help_text = """收藏功能帮助:
- /一言收藏 - 收藏上一次获取的句子
- /一言收藏列表 [页码] - 查看收藏的句子列表，可选参数：页码
- /一言收藏删除 <序号> - 删除指定序号的收藏
        """
        await UniMessage(help_text).send()
        return
    
    # 获取用户ID
    user_id = str(getattr(event, "user_id", ""))
    
    # 根据子命令分发处理
    if res.result and res.result.find("列表"):
        page = res.result.query("列表.page")
        await handle_list_favorites(user_id, page)
        return
    
    if res.result and res.result.find("删除"):
        index = res.result.query("删除.index")
        if index is not None:
            await handle_delete_favorite(user_id, index)
        else:
            await UniMessage("请指定要删除的收藏序号").send()
        return
    
    # 默认行为：添加收藏
    await handle_add_favorite(user_id)

async def handle_add_favorite(user_id: str):
    """添加收藏处理"""
    if user_id not in last_sentences:
        await UniMessage("没有可收藏的句子，请先使用 /一言 获取一条句子").send()
        return
    
    # 检查是否超时
    current_time = time.time()
    last_data = last_sentences[user_id]
    
    if "timestamp" not in last_data:
        # 兼容旧版数据
        await UniMessage("没有可收藏的句子，请先使用 /一言 获取一条句子").send()
        return
    
    # 计算时间差
    time_diff = current_time - last_data["timestamp"]
    if time_diff > hitokoto_config.favorite_timeout:
        # 获取命令前缀
        command_prefix = "/"  # 默认前缀
        try:
            if hasattr(driver, "config") and hasattr(driver.config, "COMMAND_START"):
                command_prefix = driver.config.COMMAND_START[0] if driver.config.COMMAND_START else "/"
        except:
            pass
        
        await UniMessage(f"收藏超时，请在获取句子后 {hitokoto_config.favorite_timeout} 秒内使用{command_prefix}一言收藏进行收藏").send()
        return
    
    # 获取最后一次的句子
    sentence = last_data["sentence"]
    
    # 初始化用户收藏列表
    if user_id not in user_favorites:
        user_favorites[user_id] = []
    
    # 检查是否已经收藏
    for fav in user_favorites[user_id]:
        if fav.get("id") == sentence.get("id"):
            await UniMessage("该句子已经在收藏中了").send()
            return
    
    # 检查是否超过最大收藏数量
    if len(user_favorites[user_id]) >= hitokoto_config.max_favorites_per_user:
        await UniMessage(f"您的收藏已达到上限（{hitokoto_config.max_favorites_per_user}条），请删除一些收藏后再试").send()
        return
    
    # 添加到收藏
    user_favorites[user_id].append(sentence)
    
    # 保存收藏
    await save_favorites()
    
    await UniMessage("收藏成功！").send()

async def handle_list_favorites(user_id: str, page: Optional[int] = None):
    """列出收藏处理"""
    if user_id not in user_favorites or not user_favorites[user_id]:
        await UniMessage("您还没有收藏任何一言").send()
        return
    
    favorites = user_favorites[user_id]
    
    # 计算总页数
    per_page = hitokoto_config.favorites_per_page
    total_pages = (len(favorites) + per_page - 1) // per_page
    
    # 处理页码参数
    if page is None:
        page = 1
    elif page <= 0 or page > total_pages:
        await UniMessage(f"无效的页码，页码范围：1-{total_pages}").send()
        return
    
    # 计算当前页的起始和结束索引
    start_idx = (page - 1) * per_page
    end_idx = min(start_idx + per_page, len(favorites))
    
    # 获取当前页的收藏
    page_favorites = favorites[start_idx:end_idx]
    
    # 构建消息
    message = "一言+·收藏列表\n-------------------\n"
    
    for i, fav in enumerate(page_favorites, start_idx + 1):
        sentence = type_validate_python(HitokotoSentence, fav)
        # 只显示句子内容
        message += f"{i}. {sentence.hitokoto}\n"
    
    # 添加分割线和页码信息
    message += "-------------------\n"
    message += f"当前第 {page} 页，共有 {total_pages} 页\n"
    
    # 添加翻页提示
    if total_pages > 1:
        # 获取命令前缀
        command_prefix = "/"  # 默认前缀
        try:
            # 尝试从驱动获取命令前缀
            from nonebot import get_driver
            driver = get_driver()
            if hasattr(driver, "config") and hasattr(driver.config, "COMMAND_START"):
                command_prefix = driver.config.COMMAND_START[0] if driver.config.COMMAND_START else "/"
        except:
            pass
            
        # 添加翻页提示和示例
        message += f"使用 {command_prefix}一言收藏列表 [页码] 翻页，如 {command_prefix}一言收藏列表 2"
    
    await UniMessage(message.strip()).send()

async def handle_delete_favorite(user_id: str, index: int):
    """删除收藏处理"""
    if user_id not in user_favorites or not user_favorites[user_id]:
        await UniMessage("您还没有收藏任何一言").send()
        return
    
    favorites = user_favorites[user_id]
    
    # 检查序号是否有效
    if index <= 0 or index > len(favorites):
        await UniMessage(f"无效的序号，序号范围：1-{len(favorites)}").send()
        return
    
    # 检查是否有待确认的删除操作
    if user_id in pending_deletes:
        # 检查是否超时
        if time.time() - pending_deletes[user_id]["timestamp"] > DELETE_CONFIRM_TIMEOUT:
            # 超时，清除待确认状态
            del pending_deletes[user_id]
        else:
            # 未超时，检查是否是同一个序号
            if pending_deletes[user_id]["index"] == index:
                # 确认删除
                removed = favorites.pop(index - 1)
                
                # 保存收藏
                await save_favorites()
                
                # 清除待确认状态
                del pending_deletes[user_id]
                
                # 构建反馈消息
                sentence = type_validate_python(HitokotoSentence, removed)
                message = f"已删除收藏：\n{sentence.hitokoto}"
                
                await UniMessage(message).send()
                return
            else:
                # 不同的序号，更新待确认状态
                pending_deletes[user_id] = {
                    "index": index,
                    "timestamp": time.time()
                }
                
                # 获取要删除的句子
                sentence = type_validate_python(HitokotoSentence, favorites[index - 1])
                
                # 构建确认消息
                message = f"您确定要删除以下收藏吗？\n\n{sentence.hitokoto}\n\n请在 {DELETE_CONFIRM_TIMEOUT} 秒内再次发送相同命令确认删除。"
                
                await UniMessage(message).send()
                return
    
    # 没有待确认的删除操作，创建新的待确认状态
    pending_deletes[user_id] = {
        "index": index,
        "timestamp": time.time()
    }
    
    # 获取要删除的句子
    sentence = type_validate_python(HitokotoSentence, favorites[index - 1])
    
    # 构建确认消息
    message = f"您确定要删除以下收藏吗？\n\n{sentence.hitokoto}\n\n请在 {DELETE_CONFIRM_TIMEOUT} 秒内再次发送相同命令确认删除。"
    
    await UniMessage(message).send() 