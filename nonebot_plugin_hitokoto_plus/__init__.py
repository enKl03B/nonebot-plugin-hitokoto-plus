from nonebot import require
# 优先导入和初始化 localstore
require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as store
import nonebot_plugin_localstore.config as store_config

# 显式 require 依赖 uninfo
require("nonebot_plugin_uninfo")
from nonebot_plugin_uninfo import Uninfo 

# 设置插件标识符
store_config.plugin_name = "nonebot_plugin_hitokoto_plus"

# 显式 require 依赖 alconna
require("nonebot_plugin_alconna")

from nonebot import get_driver, get_plugin_config, logger
from nonebot.plugin import PluginMetadata
from nonebot.adapters import Message, Event
from nonebot.matcher import Matcher
from nonebot.compat import type_validate_python
from nonebot.rule import Rule
from nonebot.params import Depends 

# Alconna相关导入
from nonebot_plugin_alconna import on_alconna, Alconna, Args, Option, Subcommand, Match
from nonebot_plugin_alconna.uniseg import UniMessage


import json
from typing import Optional, Dict, Any, List, Union
import asyncio
import os
import re
import time
import random 

from .config import HitokotoConfig
from .api import HitokotoAPI, HitokotoSentence
from .rate_limiter import RateLimiter

__plugin_meta__ = PluginMetadata(
    name="一言+",
    description="（可能是）更好的一言插件！",
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
api = HitokotoAPI(hitokoto_config.hitp_api_url)

# 创建频率限制器
rate_limiter = RateLimiter()

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

# 定义一个匹配有效单字符类型或为空的正则表达式模式
valid_type_pattern = r"^[a-l]?$"
# 编译正则表达式模式
compiled_type_pattern = re.compile(valid_type_pattern)

hitokoto_alc = Alconna(
    "一言",
    # 直接在Args中使用编译后的正则表达式模式
    Args["type?", compiled_type_pattern],
    Option("--help", help_text="显示帮助信息"),
    separators=[" "]  # 明确指定分隔符，避免匹配到"一言收藏"等命令
)

# 收藏命令 - 明确定义一个完全独立的指令
favorite_alc = Alconna(
    "一言收藏",
    Option("--help", help_text="显示帮助信息"),
    Subcommand("列表", Args["page?", int], help_text="查看收藏的句子列表，可选参数：页码"),
    Subcommand("删除", Args["indexes", List[int]], help_text="删除指定序号的收藏，可以指定多个序号"),
    Subcommand("详情", Args["indexes", List[int]], help_text="查看指定序号收藏的详细信息，可以指定多个序号")
)

# 创建自定义规则，防止一言命令匹配到收藏命令
async def not_favorite_command(event: Event) -> bool:
    # 获取消息文本
    try:
        # 检查事件是否有message属性
        if hasattr(event, "get_message") and callable(event.get_message):
            msg = event.get_message().extract_plain_text().strip()
        elif hasattr(event, "get_plaintext") and callable(event.get_plaintext):
            msg = event.get_plaintext().strip()
        elif hasattr(event, "message"):
            msg = str(event.message).strip()
        else:
            # 如果无法获取消息文本，默认不匹配收藏命令
            return True
    except ValueError:
        # 事件没有消息，默认不匹配收藏命令
        return True
    except Exception as e:
        logger.warning(f"获取消息文本发生错误: {e}")
        return True
    
    # 获取可能的命令前缀
    command_start = "/"
    try:
        from nonebot import get_driver
        driver = get_driver()
        if hasattr(driver, "config") and hasattr(driver.config, "COMMAND_START"):
            if driver.config.COMMAND_START:
                command_start = list(driver.config.COMMAND_START)[0]
    except:
        pass
    
    # 如果消息以"一言收藏"开头(带前缀)，返回False（不匹配）
    if msg.startswith(f"{command_start}一言收藏"):
        return False
    return True

# 新增：权限检查规则
async def check_permission(session: Uninfo) -> bool: # 修改参数为 session
    """检查用户/群组是否满足黑白名单和启用配置 (使用 Uninfo)"""
    config = get_current_config()
    
    # 尝试获取 adapter_name 和 user_id
    user_id = session.user.id
    adapter_name = session.adapter.name if hasattr(session.adapter, 'name') else str(session.adapter)
    
    # 无法获取 user_id 或 adapter_name 则阻止
    if not user_id or not adapter_name:
        logger.debug("权限检查：无法从 session 获取 user_id 或 adapter_name")
        return False
        
    # 生成组合键
    combined_user_key = f"{adapter_name}:{user_id}"
        
    # 尝试判断是群聊还是私聊
    is_group = session.scene.is_group # 使用 session 判断
    group_id = None
    combined_group_key = None
    if is_group:
        group_id = session.scene.id # 从 session 获取
        if group_id: # 确保 group_id 有效
            combined_group_key = f"{adapter_name}:{group_id}"
    elif session.scene.parent and session.scene.parent.is_group: # 兼容频道内的群聊场景
         is_group = True
         group_id = session.scene.parent.id
         if group_id: # 确保 group_id 有效
             combined_group_key = f"{adapter_name}:{group_id}"
        
    # 检查是否启用对应聊天类型
    if not is_group and not config.hitp_enable_private_chat:
        logger.debug(f"权限检查：私聊已禁用，用户 {combined_user_key}")
        return False
    if is_group and not config.hitp_enable_group_chat:
        logger.debug(f"权限检查：群聊已禁用，群 {combined_group_key or group_id} 用户 {combined_user_key}")
        return False
        
    # 白名单模式
    if config.hitp_enable_whitelist:
        is_whitelisted = False
        # 使用组合键进行检查
        if combined_user_key in config.hitp_whitelist_users:
            is_whitelisted = True
            logger.debug(f"权限检查：用户 {combined_user_key} 在白名单中")
        # 检查群组白名单（如果存在组合键）
        if is_group and combined_group_key and combined_group_key in config.hitp_whitelist_groups:
            is_whitelisted = True
            logger.debug(f"权限检查：群 {combined_group_key} 在白名单中")
            
        if not is_whitelisted:
            logger.debug(f"权限检查：白名单模式下，用户 {combined_user_key} 或群 {combined_group_key or group_id} 不在白名单中")
            return False
        # 白名单检查通过，直接允许
        return True
        
    # 黑名单模式 (仅在白名单未启用时生效)
    elif config.hitp_enable_blacklist: # 使用带前缀的配置
        # 使用组合键进行检查
        if combined_user_key in config.hitp_blacklist_users: # 使用带前缀的配置
            logger.debug(f"权限检查：用户 {combined_user_key} 在黑名单中")
            return False
        # 检查群组黑名单（如果存在组合键）
        if is_group and combined_group_key:
            if combined_group_key in config.hitp_blacklist_groups: # 使用带前缀的配置
                logger.debug(f"权限检查：群 {combined_group_key} 在黑名单中")
                return False
        # 如果没有任何匹配，则允许
        return True
        
    # 未启用黑白名单，默认允许
    return True

# 创建包装函数以在 Rule 中使用基于 session 的权限检查
async def permission_checker(session: Uninfo) -> bool: # 直接使用类型注解
    return await check_permission(session)

# 创建自定义规则，只匹配收藏命令
async def is_favorite_command(event: Event) -> bool:
    # 获取消息文本
    try:
        # 检查事件是否有message属性
        if hasattr(event, "get_message") and callable(event.get_message):
            msg = event.get_message().extract_plain_text().strip()
        elif hasattr(event, "get_plaintext") and callable(event.get_plaintext):
            msg = event.get_plaintext().strip()
        elif hasattr(event, "message"):
            msg = str(event.message).strip()
        else:
            # 如果无法获取消息文本，默认不匹配收藏命令
            return False
    except ValueError:
        # 事件没有消息，默认不匹配收藏命令
        return False
    except Exception as e:
        logger.warning(f"获取消息文本发生错误: {e}")
        return False
    
    # 获取可能的命令前缀
    command_start = "/"
    try:
        from nonebot import get_driver
        driver = get_driver()
        if hasattr(driver, "config") and hasattr(driver.config, "COMMAND_START"):
            if driver.config.COMMAND_START:
                command_start = list(driver.config.COMMAND_START)[0]
    except:
        pass
    
    # 如果消息以"一言收藏"开头(带前缀)，返回True（匹配）
    return msg.startswith(f"{command_start}一言收藏")

# 获取系统配置的命令前缀用于备用处理器
command_prefix = "/"  # 默认前缀
try:
    from nonebot import get_driver
    driver = get_driver()
    if hasattr(driver, "config") and hasattr(driver.config, "COMMAND_START"):
        if driver.config.COMMAND_START:
            command_prefix = list(driver.config.COMMAND_START)[0]
except:
    pass

# 使用正则规则和自定义规则注册命令
favorite_cmd = on_alconna(favorite_alc, priority=1, use_cmd_start=True, block=True, 
                         rule=Rule(is_favorite_command) & Rule(permission_checker))
                         
hitokoto_cmd = on_alconna(hitokoto_alc, priority=10, aliases=list(hitokoto_config.hitp_command_aliases), 
                         use_cmd_start=True, rule=Rule(not_favorite_command) & Rule(permission_checker))

# 初始化
driver = get_driver()

@driver.on_startup
async def on_startup():
    """插件启动时的处理"""
    # 确保数据目录存在
    try:
        store.get_plugin_data_dir().mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.warning(f"创建数据目录失败: {e}")
    
    # 加载收藏数据
    await load_favorites()
    
    # 执行数据迁移（如果需要）
    await migrate_favorites_format()
    
    # 启动自动保存任务
    global auto_save_task
    auto_save_task = asyncio.create_task(auto_save_favorites())

    logger.info("一言+插件已启动")

async def migrate_favorites_format():
    """检查并迁移旧的收藏数据格式到新的 combined_key 格式"""
    global user_favorites
    # 检查是否需要迁移 (简单检查第一个键是否包含 ':')
    needs_migration = False
    if user_favorites:
        first_key = next(iter(user_favorites.keys()))
        if ":" not in str(first_key):
            needs_migration = True
            
    if needs_migration:
        logger.info("检测到旧版收藏数据格式，开始迁移...")
        migrated_favorites = {}
        # 默认迁移到 "legacy:" 前缀，表示来源未知
        default_prefix = "legacy:"
        count = 0
        for old_key, fav_list in user_favorites.items():
            new_key = f"{default_prefix}{old_key}"
            migrated_favorites[new_key] = fav_list
            count += len(fav_list)
        
        user_favorites = migrated_favorites
        logger.info(f"收藏数据迁移完成，共迁移 {len(user_favorites)} 个用户的 {count} 条记录")
        
        # 立即保存迁移后的数据
        try:
            await save_favorites()
            logger.info("已保存迁移后的收藏数据")
        except Exception as e:
            logger.error(f"保存迁移后的收藏数据失败: {e}")
    else:
        logger.debug("收藏数据格式无需迁移")

def get_current_config():
    """获取最新的配置"""
    global hitokoto_config
    # 重新加载配置
    hitokoto_config = get_plugin_config(HitokotoConfig)
    return hitokoto_config

@driver.on_shutdown
async def on_shutdown():
    """插件关闭时的处理"""
    # 关闭API客户端
    await api.close()
    
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
    
    logger.info("一言+插件已关闭")

async def auto_save_favorites():
    """自动保存收藏数据的任务"""
    try:
        while True:
            # 等待指定的时间间隔
            await asyncio.sleep(AUTO_SAVE_INTERVAL)
            
            # 保存收藏数据
            await save_favorites()
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
        # 使用 localstore 获取文件路径
        file_path = store.get_plugin_data_file("favorites.json")
        backup_file_path = store.get_plugin_data_file("favorites.json.bak")
        
        # 确保目录存在
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 尝试加载主文件
        if file_path.exists():
            logger.info(f"发现收藏数据文件: {file_path}")
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    user_favorites = json.load(f)
                logger.info(f"已加载{sum(len(favs) for favs in user_favorites.values())}条收藏记录")
                return
            except Exception as e:
                logger.error(f"加载主文件失败: {str(e)}")
                # 如果主文件加载失败，尝试从备份文件加载
                if backup_file_path.exists():
                    logger.info(f"尝试从备份文件加载: {backup_file_path}")
                    try:
                        with open(backup_file_path, "r", encoding="utf-8") as f:
                            user_favorites = json.load(f)
                        # 如果备份文件加载成功，将其复制为主文件
                        import shutil
                        shutil.copy2(backup_file_path, file_path)
                        logger.info(f"已从备份文件加载{sum(len(favs) for favs in user_favorites.values())}条收藏记录")
                        return
                    except Exception as backup_error:
                        logger.error(f"加载备份文件失败: {str(backup_error)}")
        else:
            logger.info(f"收藏数据文件不存在: {file_path}")
            # 尝试从备份文件加载
            if backup_file_path.exists():
                logger.info(f"尝试从备份文件加载: {backup_file_path}")
                try:
                    with open(backup_file_path, "r", encoding="utf-8") as f:
                        user_favorites = json.load(f)
                    # 如果备份文件加载成功，将其复制为主文件
                    import shutil
                    shutil.copy2(backup_file_path, file_path)
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
        # 使用 localstore 获取文件路径
        file_path = store.get_plugin_data_file("favorites.json")
        temp_file_path = store.get_plugin_data_file("favorites.json.tmp")
        backup_file_path = store.get_plugin_data_file("favorites.json.bak")
        
        # 确保目录存在
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 先保存到临时文件
        with open(temp_file_path, "w", encoding="utf-8") as f:
            json.dump(user_favorites, f, ensure_ascii=False, indent=2)
        
        # 如果原文件存在，则创建备份
        if file_path.exists():
            try:
                import shutil
                # 使用shutil.copy2而不是rename，避免跨设备问题
                shutil.copy2(file_path, backup_file_path)
            except Exception as e:
                logger.warning(f"收藏数据保存时创建备份文件失败，但将继续: {e}")
        
        # 将临时文件重命名为正式文件（使用replace避免文件不存在的异常）
        import os
        if os.name == 'nt':  # Windows系统
            # Windows可能会有文件锁定问题，先尝试删除目标文件
            if file_path.exists():
                os.remove(file_path)
            os.rename(temp_file_path, file_path)
        else:
            # Unix系统下可以直接替换
            temp_file_path.replace(file_path)
            
        # 如果一切正常，尝试删除备份文件（不影响主要功能）
        try:
            if backup_file_path.exists():
                backup_file_path.unlink()
        except Exception as e:
            logger.warning(f"删除备份文件失败，但不影响主要功能: {e}")
            
        logger.info(f"已保存{sum(len(favs) for favs in user_favorites.values())}条收藏记录")
    except Exception as e:
        logger.error(f"保存收藏数据失败: {str(e)}")
        # 如果保存失败，尝试恢复备份
        try:
            if backup_file_path.exists() and not file_path.exists():
                import shutil
                shutil.copy2(backup_file_path, file_path)
                logger.info("已从备份恢复收藏数据")
        except Exception as restore_error:
            logger.error(f"从备份恢复收藏数据失败: {str(restore_error)}")

@hitokoto_cmd.handle()
async def handle_hitokoto(matcher: Matcher, session: Uninfo): # 修改依赖注入
    """处理一言命令"""

    # 获取最新配置
    config = get_current_config()

    # 获取事件信息和用户ID - 改为从 session 获取
    try:
        # user_id = str(getattr(event, "user_id", "unknown")) # 旧方式
        user_id = session.user.id
        adapter_name = session.adapter.name if hasattr(session.adapter, 'name') else str(session.adapter)
        
        # 检查频率限制 - 需要 group_id，尝试从 session 获取
        group_id = None
        if session.scene.is_group:
            group_id = session.scene.id
        elif session.scene.parent and session.scene.parent.is_group:
            group_id = session.scene.parent.id
            
        if group_id: # 群聊消息
            allowed, remaining = rate_limiter.check_group(
                group_id, user_id, config.hitp_rate_limit_group
            )
            if not allowed:
                await UniMessage(f"别急，请等待 {remaining:.1f} 秒后再试").send()
                return
        else:  # 私聊消息
            allowed, remaining = rate_limiter.check_user(
                user_id, config.hitp_rate_limit_private # 使用带前缀的配置
            )
            if not allowed:
                await UniMessage(f"别急，请等待 {remaining:.1f} 秒后再试").send()
                return
    except Exception as e:
        logger.warning(f"检查频率限制时出错: {e}")
    
    # 尝试从Alconna解析结果获取类型
    sentence_type = None
    invalid_type = False
    input_type = None
    
    # 详细记录matcher.state内容用于调试
    for key in matcher.state:
        try:
            pass # 保持 try 块有效
        except Exception as e:
            logger.warning(f"记录matcher.state出错: {e}")
    
    # 查找Alconna解析结果
    alc_result = None
    for key in matcher.state:
        if '_alc_result' in key and matcher.state[key]:
            alc_result = matcher.state[key]
            break
    
    # 从Alconna结果中提取类型
    if alc_result:
        try:
            # 检查各种可能的属性，适应不同版本的Alconna
            if hasattr(alc_result, "main_args") and "type" in alc_result.main_args:
                input_type = alc_result.main_args.get("type")
            elif hasattr(alc_result, "result") and hasattr(alc_result.result, "main_args"):
                input_type = alc_result.result.main_args.get("type")
            elif hasattr(alc_result, "result") and isinstance(alc_result.result, dict) and "main_args" in alc_result.result:
                input_type = alc_result.result["main_args"].get("type")
            
            # 检查类型是否有效
            if input_type:
                # 如果是单字符且在有效范围内
                if isinstance(input_type, str) and len(input_type) == 1 and input_type in "abcdefghijkl":
                    sentence_type = input_type
                else:
                    invalid_type = True
        except Exception as e:
            logger.warning(f"从Alconna结果提取类型时出错: {e}")
    
    # 如果检测到无效类型，返回错误提示
    if invalid_type:
        # 获取命令前缀
        command_prefix = "/"  # 默认前缀
        try:
            if hasattr(driver, "config") and hasattr(driver.config, "COMMAND_START"):
                if driver.config.COMMAND_START:
                    command_prefix = list(driver.config.COMMAND_START)[0]
        except Exception as e:
            logger.warning(f"获取命令前缀失败: {e}")
        
        # 构建有效类型列表
        valid_types = [
            "a - 动画", "b - 漫画", "c - 游戏", "d - 文学", "e - 原创", 
            "f - 网络", "g - 其他", "h - 影视", "i - 诗词", 
            "j - 网易云", "k - 哲学", "l - 抖机灵"
        ]
        
        # 构建提示消息
        message = f"无效的句子类型「{input_type}」，有效类型为:\n"
        message += "\n".join(valid_types)
        message += f"\n\n正确用法示例: {command_prefix}一言 a"
        
        logger.info(f"用户请求的类型无效，发送无效类型提示")
        await UniMessage(message).send()
        return
    
    try:
        # 获取组合键
        combined_key = _get_combined_key(session) # 使用 session
        if not combined_key:
            logger.warning("无法获取组合键，跳过处理")
            try:
                await UniMessage("获取用户信息失败，无法完成操作").send()
            except:
                pass
            return
        
        # 直接尝试获取一言并发送
        logger.debug("开始获取一言并发送")
        
        # 获取一个随机一言，使用用户指定的类型或默认类型
        sentence = await api.get_hitokoto(sentence_type or config.hitp_default_type) # 使用带前缀的配置
        
        # 格式化一言消息
        message = api.format_sentence(sentence, with_source=True, with_author=True)
        
        # 保存最后获取的句子和时间戳，供收藏功能使用
        try:
            # 保存用户的最后句子，包含时间戳
            # 转换为字典进行存储
            sentence_dict = {}
            if isinstance(sentence, HitokotoSentence): # Pydantic 模型
                # 直接手动构建字典，避免 Pydantic 版本兼容性问题
                sentence_dict = {
                    "id": getattr(sentence, "id", 0),
                    "uuid": getattr(sentence, "uuid", ""),
                    "hitokoto": getattr(sentence, "hitokoto", ""),
                    "type": getattr(sentence, "type", ""),
                    "from": getattr(sentence, "from_", ""), # 注意这里的别名
                    "from_who": getattr(sentence, "from_who", None),
                    "creator": getattr(sentence, "creator", ""),
                    "creator_uid": getattr(sentence, "creator_uid", 0),
                    "reviewer": getattr(sentence, "reviewer", 0),
                    "commit_from": getattr(sentence, "commit_from", ""),
                    "created_at": getattr(sentence, "created_at", ""),
                    "length": getattr(sentence, "length", 0)
                }
            elif isinstance(sentence, dict):
                # 如果已经是字典，直接使用
                sentence_dict = sentence
            else:
                # 其他类型，尝试转换为字典或简化存储
                logger.debug(f"获取到的句子类型未知 ({type(sentence)})，尝试转换") # 保留此日志
                try:
                    sentence_dict = dict(sentence) # 尝试通用转换
                except Exception as e:
                    logger.warning(f"无法将未知类型转换为字典: {e}，仅存储 hitokoto 文本")
                    sentence_dict = {
                        "hitokoto": str(sentence)
                    }

            # 确保 sentence_dict 是有效的字典
            if not isinstance(sentence_dict, dict):
                logger.error("最终未能生成有效的字典用于存储 last_sentence，将使用空字典")
                sentence_dict = {}

            last_sentences[combined_key] = {
                "sentence": sentence_dict,
                "timestamp": time.time()
            }
            
            # 添加收藏提示
            command_prefix = "/"  # 默认前缀
            try:
                if hasattr(driver, "config") and hasattr(driver.config, "COMMAND_START"):
                    command_prefix = driver.config.COMMAND_START[0] if driver.config.COMMAND_START else "/"
            except:
                pass
            
            message += f"\n\n在 {config.hitp_favorite_timeout} 秒内发送{command_prefix}一言收藏可收藏该句" # 使用带前缀的配置
        except Exception as e:
            logger.warning(f"保存用户最后句子失败: {e}")
        
        # 使用UniMessage发送消息
        await UniMessage(message).send()
        logger.info("已获取一言内容并发送")
            
    except Exception as e:
        logger.error(f"handle_hitokoto处理过程中发生错误: {e}")
        logger.exception(e)
        # 尝试发送错误信息
        try:
            await UniMessage(f"获取一言时出现错误: {str(e)}").send()
        except:
            pass

@favorite_cmd.handle()
async def handle_favorite(matcher: Matcher, session: Uninfo): # 使用 Uninfo
    """处理收藏命令 (重构后)"""
    logger.debug("收藏命令被调用")
    
    # 提取组合键
    combined_key = _get_combined_key(session)
    if not combined_key:
        logger.warning("无法获取组合键，跳过处理")
        await UniMessage("获取用户信息失败，无法完成操作").send()
        return

    # 检查Alconna解析结果
    alconna_result = None
    for key in matcher.state:
        if 'alconna' in key.lower() and matcher.state[key]: # 查找包含 alconna 的键
            if hasattr(matcher.state[key], 'matched') and matcher.state[key].matched: # 确保是匹配成功的结果
                 alconna_result = matcher.state[key]
                 break
             # 兼容旧版或不同结构的 state
            elif isinstance(matcher.state[key], dict) and matcher.state[key].get('matched'):
                 alconna_result = matcher.state[key]
                 break

    # Alconna 会自动处理 --help，这里无需手动检查文本

    if alconna_result and hasattr(alconna_result, "subcommands") and alconna_result.subcommands:
        logger.debug(f"使用Alconna解析结果处理子命令: {alconna_result.subcommands}")
        # 检查是否有列表子命令
        if "列表" in alconna_result.subcommands:
            page = alconna_result.subcommands["列表"].get("page")
            await handle_list_favorites(combined_key, session, page)
            return
        # 检查是否有删除子命令
        elif "删除" in alconna_result.subcommands:
            indexes = alconna_result.subcommands["删除"].get("indexes")
            if not indexes:
                 await UniMessage("请指定要删除的收藏序号，例如：/一言收藏删除 1").send()
                 return
            await handle_delete_favorite(combined_key, indexes)
            return
        # 检查是否有详情子命令
        elif "详情" in alconna_result.subcommands:
            indexes = alconna_result.subcommands["详情"].get("indexes")
            if not indexes:
                 await UniMessage("请指定要查看详情的收藏序号，例如：/一言收藏详情 1").send()
                 return
            await handle_detail_favorite(combined_key, indexes)
            return
        else:
            # 存在子命令但无法识别 (理论上不应发生，除非 Alconna 定义有问题)
            logger.warning(f"无法识别的收藏子命令: {alconna_result.subcommands}")
            await UniMessage("无法识别的收藏子命令").send()
            return
    else:
        # 没有匹配到任何子命令，执行默认操作：添加收藏
        logger.debug("未匹配到收藏子命令，执行添加收藏操作")
        await handle_add_favorite(combined_key)

async def handle_add_favorite(combined_key: str):
    """添加收藏处理"""
    try:
        # 获取最新配置
        config = get_current_config()
        
        if combined_key not in last_sentences:
            msg = "没有可收藏的句子，请先使用 /一言 获取一条句子"
            await UniMessage(msg).send()
            return
        
        # 检查是否超时
        current_time = time.time()
        last_data = last_sentences[combined_key]
        
        if "timestamp" not in last_data:
            # 兼容旧版数据
            msg = "没有可收藏的句子，请先使用 /一言 获取一条句子"
            await UniMessage(msg).send()
            return
        
        # 计算时间差
        time_diff = current_time - last_data["timestamp"]
        if time_diff > config.hitp_favorite_timeout:
            # 获取命令前缀
            command_prefix = "/"  # 默认前缀
            try:
                if hasattr(driver, "config") and hasattr(driver.config, "COMMAND_START"):
                    command_prefix = driver.config.COMMAND_START[0] if driver.config.COMMAND_START else "/"
            except:
                pass
            
            msg = f"收藏超时，请在获取句子后 {config.hitp_favorite_timeout} 秒内使用 \"{command_prefix}一言收藏\" 进行收藏" # 使用带前缀的配置
            await UniMessage(msg).send()
            return
        
        # 获取最后一次的句子
        sentence = last_data["sentence"]
        
        # 初始化用户收藏列表
        if combined_key not in user_favorites:
            user_favorites[combined_key] = []
        
        # 检查是否已经收藏
        for fav in user_favorites[combined_key]:
            if fav.get("id") == sentence.get("id"):
                msg = "该句子已经在收藏中了"
                await UniMessage(msg).send()
                return
        
        # 检查是否超过最大收藏数量
        if len(user_favorites[combined_key]) >= config.hitp_max_favorites_per_user:
            msg = f"您的收藏已达到上限（{config.hitp_max_favorites_per_user}条），请删除一些收藏后再试" # 使用带前缀的配置
            await UniMessage(msg).send()
            return
        
        # 添加到收藏
        user_favorites[combined_key].append(sentence)
        
        # 保存收藏
        await save_favorites()
        
        msg = "收藏成功！"
        await UniMessage(msg).send()
    except Exception as e:
        logger.error(f"添加收藏时发生未预期的异常: {e}")
        logger.exception(e)  # 输出完整异常堆栈
        await UniMessage("添加收藏时出现错误，请稍后再试").send()

async def handle_list_favorites(combined_key: str, session: Uninfo, page: Optional[int] = None): # 修改依赖注入
    """列出收藏处理"""
    try:
        # 获取最新配置
        config = get_current_config()
        
        if combined_key not in user_favorites or not user_favorites[combined_key]:
            msg = "您还没有收藏任何一言"
            await UniMessage(msg).send()
            return
    
        favorites = user_favorites[combined_key]
        
        # 计算总页数
        per_page = config.hitp_favorites_per_page # 使用带前缀的配置
        total_pages = (len(favorites) + per_page - 1) // per_page
        
        # 处理页码参数
        if page is None:
            page = 1
        elif page <= 0 or page > total_pages:
            msg = f"无效的页码，页码范围：1-{total_pages}"
            await UniMessage(msg).send()
            return
        
        # 计算当前页的起始和结束索引
        start_idx = (page - 1) * per_page
        end_idx = min(start_idx + per_page, len(favorites))
        
        # 获取当前页的收藏
        page_favorites = favorites[start_idx:end_idx]
        
        # 尝试获取用户昵称 - 使用 Uninfo session
        user_nickname = session.user.name or (session.member.nick if session.member else None) or combined_key.split(":", 1)[-1]
            
        # 构建消息 - 修改标题部分
        message = f"{user_nickname} 的\n一言+·收藏列表\n-------------------\n"
        
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
    except Exception as e:
        logger.error(f"列出收藏时发生未预期的异常: {e}")
        logger.exception(e)  # 输出完整异常堆栈
        await UniMessage("列出收藏时出现错误，请稍后再试").send()

async def handle_detail_favorite(combined_key: str, indexes: List[int]):
    """查看收藏详情处理"""
    try:
        if combined_key not in user_favorites or not user_favorites[combined_key]:
            msg = "您还没有收藏任何一言"
            await UniMessage(msg).send()
            return
    
        favorites = user_favorites[combined_key]
        
        # 获取最新配置并限制单次最大查看数量，防止刷屏
        config = get_current_config()
        max_details = config.hitp_max_details_per_request # 使用带前缀的配置
        if len(indexes) > max_details:
            await UniMessage(f"单次最多只能查看 {max_details} 条收藏详情，您请求了 {len(indexes)} 条").send()
            # 完全拦截，不处理任何请求
            return
        
        # 检查序号是否有效
        invalid_indexes = []
        valid_indexes = []
        for index in indexes:
            if index <= 0 or index > len(favorites):
                invalid_indexes.append(index)
            else:
                valid_indexes.append(index)
        
        if invalid_indexes:
            await UniMessage(f"以下序号无效: {', '.join(map(str, invalid_indexes))}, 有效序号范围: 1-{len(favorites)}").send()
            if not valid_indexes:
                return
        
        # 处理有效序号
        for index in valid_indexes:
            favorite = favorites[index - 1]
            sentence = type_validate_python(HitokotoSentence, favorite)
            
            # 使用API的格式化方法构建消息
            message = api.format_sentence(sentence, with_source=True, with_author=True)
            
            # 添加序号信息
            message = f"收藏序号 {index}:\n{message}"
            
            # 发送消息
            await UniMessage(message).send()
            
            # 在发送下一条之前随机延迟
            if len(valid_indexes) > 1 and index != valid_indexes[-1]: # 如果有多条且不是最后一条
                delay = random.uniform(0.5, 1.5) # 随机延迟0.5到1.5秒
                await asyncio.sleep(delay)
            
    except Exception as e:
        logger.error(f"查看收藏详情时发生未预期的异常: {e}")
        logger.exception(e)  # 输出完整异常堆栈
        await UniMessage("查看收藏详情时出现错误，请稍后再试").send()

async def handle_delete_favorite(combined_key: str, indexes: List[int]):
    """删除收藏处理"""
    try:
        if combined_key not in user_favorites or not user_favorites[combined_key]:
            msg = "您还没有收藏任何一言"
            await UniMessage(msg).send()
            return
    
        favorites = user_favorites[combined_key]
        
        # 检查序号是否有效
        invalid_indexes = []
        valid_indexes = []
        for index in indexes:
            if index <= 0 or index > len(favorites):
                invalid_indexes.append(index)
            else:
                valid_indexes.append(index)
        
        if invalid_indexes:
            await UniMessage(f"以下序号无效: {', '.join(map(str, invalid_indexes))}, 有效序号范围: 1-{len(favorites)}").send()
            if not valid_indexes:
                return
        
        # 排序并逆序，先删大的索引再删小的，避免删除后索引变化
        valid_indexes.sort(reverse=True)
        
        # 检查是否有待确认的删除操作
        if combined_key in pending_deletes:
            # 检查是否超时
            if time.time() - pending_deletes[combined_key]["timestamp"] > DELETE_CONFIRM_TIMEOUT:
                # 超时，清除待确认状态
                del pending_deletes[combined_key]
            else:
                # 未超时，检查是否包含所有要删除的序号
                pending_indexes = [pending_deletes[combined_key]["index"]] if isinstance(pending_deletes[combined_key]["index"], int) else pending_deletes[combined_key]["index"]
                if set(valid_indexes) == set(pending_indexes):
                    # 确认删除全部
                    removed_sentences = []
                    for index in valid_indexes:
                        removed_sentences.append(favorites[index - 1])
                        
                    # 逆序删除，防止索引变化
                    for index in valid_indexes:
                        favorites.pop(index - 1)
                    
                    # 保存收藏
                    await save_favorites()
                    
                    # 清除待确认状态
                    del pending_deletes[combined_key]
                    
                    # 构建反馈消息
                    if len(removed_sentences) == 1:
                        sentence = type_validate_python(HitokotoSentence, removed_sentences[0])
                        message = f"已删除收藏：\n{sentence.hitokoto}"
                    else:
                        message = f"已删除 {len(removed_sentences)} 条收藏"
                    
                    await UniMessage(message).send()
                    return
                else:
                    # 不同的序号，更新待确认状态
                    pending_deletes[combined_key] = {
                        "index": valid_indexes,
                        "timestamp": time.time()
                    }
                    
                    # 构建确认消息
                    if len(valid_indexes) == 1:
                        index = valid_indexes[0]
                        sentence = type_validate_python(HitokotoSentence, favorites[index - 1])
                        message = f"您确定要删除以下收藏吗？\n\n{sentence.hitokoto}\n\n请在 {DELETE_CONFIRM_TIMEOUT} 秒内再次发送相同命令确认删除。"
                    else:
                        message = f"您确定要删除这 {len(valid_indexes)} 条收藏吗？请在 {DELETE_CONFIRM_TIMEOUT} 秒内再次发送相同命令确认删除。"
                    
                    await UniMessage(message).send()
                    return
        
        # 没有待确认的删除操作，创建新的待确认状态
        pending_deletes[combined_key] = {
            "index": valid_indexes,
            "timestamp": time.time()
        }
        
        # 构建确认消息
        if len(valid_indexes) == 1:
            index = valid_indexes[0]
            sentence = type_validate_python(HitokotoSentence, favorites[index - 1])
            message = f"您确定要删除以下收藏吗？\n\n{sentence.hitokoto}\n\n请在 {DELETE_CONFIRM_TIMEOUT} 秒内再次发送相同命令确认删除。"
        else:
            message = f"您确定要删除这 {len(valid_indexes)} 条收藏吗？请在 {DELETE_CONFIRM_TIMEOUT} 秒内再次发送相同命令确认删除。"
        
        await UniMessage(message).send()
    except Exception as e:
        logger.error(f"删除收藏时发生未预期的异常: {e}")
        logger.exception(e)  # 输出完整异常堆栈
        await UniMessage("删除收藏时出现错误，请稍后再试").send()

# --- 辅助函数 ---

def _get_combined_key(session: Uninfo) -> Optional[str]:
    """根据 Uninfo session 生成 adapter_name:user_id 的组合键"""
    try:
        # 获取用户ID
        user_id = session.user.id
        # 获取适配器名称，处理可能的枚举类型
        if hasattr(session.adapter, 'name'):
            adapter_name = session.adapter.name
        else:
            adapter_name = str(session.adapter)
        
        # 确保 user_id 和 adapter_name 不为空
        if not user_id or not adapter_name:
             logger.warning(f"无法从 session 获取有效的 user_id 或 adapter_name: user_id={user_id}, adapter_name={adapter_name}")
             return None
             
        return f"{adapter_name}:{user_id}"
    except AttributeError as e:
        logger.warning(f"从 session 生成组合键时缺少属性: {e}")
        return None
    except Exception as e:
        logger.warning(f"从 session 生成组合键时发生未知错误: {e}")
        return None 