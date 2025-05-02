from typing import Dict, Optional
import time
from datetime import datetime

from nonebot.adapters import Event
from nonebot.log import logger
from nonebot import get_driver

# 导入alconna
from nonebot_plugin_alconna import on_alconna, Args, Alconna, CommandResult
# 直接导入模块
from nonebot_plugin_uninfo import Uninfo
from nonebot_plugin_apscheduler import scheduler

from ..api import get_hitokoto, format_hitokoto, APIError
from ..config import Config, plugin_config
from ..models import favorite_manager
from ..rate_limiter import rate_limiter

# 创建一言命令
hitokoto_cmd = on_alconna(
    Alconna(
        "一言", 
        Args["type?", str]
    ),
    aliases={"hitokoto", "yiyan"},
    use_cmd_start=True,
    block=True
)

# 用于存储最后调用时间的字典
# 格式: {platform:user_id: last_time}
last_call_time: Dict[str, float] = {}

# 延迟导入，避免在模块加载时导入
def setup_scheduler():
    """设置定时任务"""
    # 使用 scheduler.scheduled_job 装饰器动态注册任务
    @scheduler.scheduled_job("interval", seconds=plugin_config.hitp_cooldown_cleanup_interval, id="hitokoto_cooldown_cleanup")
    async def cleanup_cooldown_records():
        """定时清理过期的冷却记录"""
        global last_call_time
        
        if not last_call_time:
            return
        
        current_time = time.time()
        current_time_str = datetime.fromtimestamp(current_time).strftime("%Y-%m-%d %H:%M:%S")
        
        # 直接在列表创建时添加过期的用户ID
        expired_users = [
            user_id for user_id, last_time in last_call_time.items()
            if current_time - last_time > plugin_config.hitp_user_retention_time
        ]
        
        if expired_users:
            # 删除过期记录
            for user_id in expired_users:
                del last_call_time[user_id]
            
            # 记录清理结果
            logger.info(f"[{current_time_str}] 已清理 {len(expired_users)} 条过期冷却记录，当前记录数: {len(last_call_time)}")
        else:
            logger.debug(f"[{current_time_str}] 没有过期冷却记录需要清理，当前记录数: {len(last_call_time)}")

# 添加插件初始化函数
driver = get_driver()

@driver.on_startup
async def _():
    """在机器人启动时进行初始化"""
    try:
        # 在这里进行初始化操作
        setup_scheduler()
        logger.info("一言+定时任务设置成功")
    except Exception as e:
        logger.error(f"一言+定时任务设置失败: {e}")


@hitokoto_cmd.handle()
async def handle_hitokoto(event: Event, result: CommandResult, session: Uninfo) -> None:
    """处理一言命令"""
    
    hitokoto_type: Optional[str] = None
    
    # 获取跨平台用户标识
    platform = session.adapter
    user_id = session.user.id
    # 创建复合ID用于频率限制
    composite_id = f"{platform}:{user_id}"
    
    # 检查黑白名单
    if not check_permission(session):
        logger.debug(f"用户 {composite_id} 因黑白名单限制被拒绝访问")
        return
    
    # 检查频率限制
    if not await rate_limiter.check_rate_limit(composite_id, hitokoto_cmd.send):
        return
    
    # 使用最原始的方式获取命令结果
    logger.debug(f"CommandResult: {result}")
    
    # 获取参数字典
    args_dict = result.result.main_args if result.result else {}
    logger.debug(f"参数字典: {args_dict}")
    
    # 获取类型参数
    if args_dict and (hitokoto_type := args_dict.get("type")):
        logger.debug(f"获取到一言类型: {hitokoto_type}")
    else:
        logger.debug("未指定一言类型，将使用随机类型")
    
    try:
        # 调用API获取一言
        logger.debug(f"准备调用API获取一言，类型参数: {hitokoto_type}")
        hitokoto_data = await get_hitokoto(hitokoto_type=hitokoto_type)
        
        # 记录用户获取的一言，用于后续收藏
        favorite_manager.set_last_hitokoto(platform, user_id, hitokoto_data)
        
        # 格式化一言数据
        logger.debug(f"获取一言成功，类型: {hitokoto_data.get('type_name', '未知类型')}")
        formatted_hitokoto = format_hitokoto(hitokoto_data)
        
        # 添加收藏提示
        formatted_hitokoto += f"\n----------\n在 {plugin_config.hitp_favorite_timeout} 秒内使用 /一言收藏 命令收藏该句"
        
        # 使用send方法发送消息，不使用finish
        await hitokoto_cmd.send(formatted_hitokoto)
        
    except APIError as e:
        # 处理API错误
        logger.error(f"API错误: {str(e)}")
        await hitokoto_cmd.send(f"获取一言失败: {str(e)}")
    except Exception as e:
        # 处理其他错误
        logger.exception("获取一言时发生未知错误")
        # 将未知错误转为APIError便于用户理解
        new_error = APIError(f"获取一言时发生未知错误: {str(e)}")
        await hitokoto_cmd.send(str(new_error))
        # 重新引发异常以便记录完整的错误栈
        raise new_error from e


def check_permission(session) -> bool:
    """
    检查黑白名单权限
    
    参数:
        session: 会话对象
        
    返回:
        bool: 是否有权限使用，True表示有权限，False表示无权限
    """
    # 获取用户标识
    platform = session.adapter
    user_id = session.user.id
    composite_id = f"{platform}:{user_id}"
    
    # 获取群组标识，如果有的话
    group_id = ""
    if hasattr(session, "group") and session.group and hasattr(session.group, "id"):
        group_id = session.group.id
        group_composite_id = f"{platform}:{group_id}"
    else:
        group_composite_id = ""
    
    # 判断模式：白名单模式还是黑名单模式
    if plugin_config.hitp_use_whitelist:
        # 白名单模式：只有在列表中的用户/群组才能使用
        return (composite_id in plugin_config.hitp_user_list or 
                (group_composite_id and group_composite_id in plugin_config.hitp_group_list))
    else:
        # 黑名单模式：不在列表中的用户/群组才能使用
        return (composite_id not in plugin_config.hitp_user_list and 
                (not group_composite_id or group_composite_id not in plugin_config.hitp_group_list)) 