from typing import Optional, List
import math
import time
from datetime import datetime

from nonebot.adapters import Event
from nonebot.log import logger
from nonebot import get_plugin_config, require, get_driver
from nonebot_plugin_alconna import on_alconna, Args, Alconna, CommandResult, Option
from nonebot_plugin_alconna.uniseg import UniMessage, Text, At

# 只声明导入，不实际导入
require("nonebot_plugin_uninfo")

from ..config import Config
from ..models import favorite_manager, HitokotoFavorite
from .basic import check_permission
from ..api import get_hitokoto, format_hitokoto, APIError
from ..rate_limiter import rate_limiter

# 获取插件配置
plugin_config = get_plugin_config(Config)

# 获取全局配置
global_config = get_driver().config
# 获取命令前缀，默认为 "/"
cmd_start = getattr(global_config, "command_start", {"/", })
cmd_prefix = next(iter(cmd_start)) if cmd_start else "/"

# 创建收藏相关命令
favorite_list_cmd = on_alconna(
    Alconna(
        "一言收藏列表",
        Option("-p|--page", Args["page", int], help_text="页码，默认为第1页")
    ),
    aliases={"hitokoto_favorite_list"},
    use_cmd_start=True,
    block=True
)

add_favorite_cmd = on_alconna(
    Alconna("一言收藏"),
    aliases={"hitokoto_add_favorite"},
    use_cmd_start=True,
    block=True
)

view_favorite_cmd = on_alconna(
    Alconna(
        "一言查看收藏",
        Args["index", int]
    ),
    aliases={"hitokoto_view_favorite"},
    use_cmd_start=True,
    block=True
)

delete_favorite_cmd = on_alconna(
    Alconna(
        "一言删除收藏",
        Args["index", int]
    ),
    aliases={"hitokoto_delete_favorite"},
    use_cmd_start=True,
    block=True
)


@favorite_list_cmd.handle()
async def handle_favorite_list(event: Event, result: CommandResult) -> None:
    """处理收藏列表命令"""
    # 延迟导入
    from nonebot_plugin_uninfo import Uninfo
    
    # 获取会话
    session = Uninfo.from_event(event)
    
    # 获取跨平台用户标识
    platform = session.adapter
    user_id = session.user.id
    user_name = session.user.name  # 获取用户昵称
    composite_id = f"{platform}:{user_id}"
    
    # 检查黑白名单
    if not check_permission(session):
        logger.debug(f"用户 {composite_id} 因黑白名单限制被拒绝访问收藏列表")
        return
    
    # 检查频率限制
    if not await rate_limiter.check_rate_limit(composite_id, favorite_list_cmd.send):
        return
    
    # 获取页码参数
    page = 1
    if result.result and "-p" in result.result.options and (page_arg := result.result.options["-p"]) and "page" in page_arg:
            page = max(1, page_arg["page"])
    
    # 获取用户收藏列表
    favorites = favorite_manager.get_favorites(platform, user_id)
    
    # 计算总页数
    page_size = plugin_config.HITP_FAVORITE_LIST_LIMIT
    total_pages = max(1, math.ceil(len(favorites) / page_size))
    
    # 确保页码有效
    page = min(page, total_pages)
    
    # 计算当前页的收藏
    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, len(favorites))
    current_page_favorites = favorites[start_idx:end_idx]
    
    if not favorites:
        await favorite_list_cmd.send("您还没有收藏任何一言")
        return
    
    # 构建收藏列表消息
    msg_list = [
        f"{user_name} 的一言收藏",
        f"（{page}/{total_pages}页，共{len(favorites)}条）",
        "----------"
    ]

    msg_list.extend([
        f"{i}. {fav.content[:30] + '...' if len(fav.content) > 30 else fav.content}"
        for i, fav in enumerate(current_page_favorites, start=start_idx + 1)
    ])
    
    msg_list.append("----------")
    
    # 根据总页数添加不同的提示
    if total_pages > 1:
        if page < total_pages:
            msg_list.append(f"使用 {cmd_prefix}一言收藏列表 -p {page+1} 查看下一页")
        else:
            msg_list.append(f"已经是最后一页")
        
        if page > 1:
            msg_list.append(f"使用 {cmd_prefix}一言收藏列表 -p {page-1} 查看上一页")
    
    # 添加操作提示
    msg_list.extend([
        f"使用 {cmd_prefix}一言查看收藏 [序号] 查看详情",
        f"使用 {cmd_prefix}一言删除收藏 [序号] 删除收藏"
    ])
    
    await favorite_list_cmd.send("\n".join(msg_list))


@add_favorite_cmd.handle()
async def handle_add_favorite(event: Event) -> None:
    """处理收藏命令"""
    # 延迟导入
    from nonebot_plugin_uninfo import Uninfo
    
    # 获取会话
    session = Uninfo.from_event(event)
    
    # 获取跨平台用户标识
    platform = session.adapter
    user_id = session.user.id
    composite_id = f"{platform}:{user_id}"
    
    # 检查黑白名单
    if not check_permission(session):
        logger.debug(f"用户 {composite_id} 因黑白名单限制被拒绝访问收藏功能")
        return
    
    # 检查频率限制
    if not await rate_limiter.check_rate_limit(composite_id, add_favorite_cmd.send):
        return
    
    # 尝试获取用户上次获取的一言
    hitokoto_data = favorite_manager.get_last_hitokoto(platform, user_id)
    if not hitokoto_data:
        await add_favorite_cmd.send("您还没有获取过一言，或者收藏超时了")
        return
        
    # 检查是否已经收藏
    if favorite_manager.is_favorite_exists(platform, user_id, hitokoto_data.uuid):
        await add_favorite_cmd.send("该一言已经收藏过了")
        return
    
    # 添加收藏
    favorite_manager.add_favorite(platform, user_id, hitokoto_data)
    logger.info(f"用户 {composite_id} 收藏了一言: {hitokoto_data.content[:20]}...")
    
    # 使用send方法发送消息
    await add_favorite_cmd.send(f"收藏成功！可以使用 {cmd_prefix}一言收藏列表 命令查看您的收藏列表")
    

@view_favorite_cmd.handle()
async def handle_view_favorite(event: Event, result: CommandResult) -> None:
    """处理查看收藏命令"""
    # 延迟导入
    from nonebot_plugin_uninfo import Uninfo
    
    # 获取会话
    session = Uninfo.from_event(event)
    
    # 获取跨平台用户标识
    platform = session.adapter
    user_id = session.user.id
    composite_id = f"{platform}:{user_id}"
    
    # 检查黑白名单
    if not check_permission(session):
        logger.debug(f"用户 {composite_id} 因黑白名单限制被拒绝访问收藏功能")
        return
    
    # 检查频率限制
    if not await rate_limiter.check_rate_limit(composite_id, view_favorite_cmd.send):
        return
    
    # 获取收藏序号参数
    index = 0
    if result.result and result.result.main_args and (index_arg := result.result.main_args.get("index")):
        index = int(index_arg)
    
    if index <= 0:
        await view_favorite_cmd.send("收藏序号必须大于0")
        return
    
    # 获取用户收藏列表
    favorites = favorite_manager.get_favorites(platform, user_id)
    
    if not favorites:
        await view_favorite_cmd.send("您还没有收藏任何一言")
        return
    
    if index > len(favorites):
        await view_favorite_cmd.send(f"序号超出范围，您只有 {len(favorites)} 条收藏")
        return
    
    # 获取收藏的一言
    favorite = favorites[index-1]
    
    # 构建收藏消息
    msg = f"收藏序号: {index}\n"
    msg += f"内容: {favorite.content}\n"
    msg += f"类型: {favorite.type_name}\n"
    
    if favorite.source:
        msg += f"来源: {favorite.source}\n"
    
    if favorite.creator:
        msg += f"作者: {favorite.creator}\n"
    
    msg += f"收藏时间: {favorite.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
    
    await view_favorite_cmd.send(msg)


@delete_favorite_cmd.handle()
async def handle_delete_favorite(event: Event, result: CommandResult) -> None:
    """处理删除收藏命令"""
    # 延迟导入
    from nonebot_plugin_uninfo import Uninfo
    
    # 获取会话
    session = Uninfo.from_event(event)
    
    # 获取跨平台用户标识
    platform = session.adapter
    user_id = session.user.id
    composite_id = f"{platform}:{user_id}"
    
    # 检查黑白名单
    if not check_permission(session):
        logger.debug(f"用户 {composite_id} 因黑白名单限制被拒绝访问收藏功能")
        return
    
    # 检查频率限制
    if not await rate_limiter.check_rate_limit(composite_id, delete_favorite_cmd.send):
        return
    
    # 获取收藏序号参数
    index = 0
    if result.result and result.result.main_args and (index_arg := result.result.main_args.get("index")):
        index = int(index_arg)
    
    if index <= 0:
        await delete_favorite_cmd.send("收藏序号必须大于0")
        return
    
    # 获取用户收藏列表
    favorites = favorite_manager.get_favorites(platform, user_id)
    
    if not favorites:
        await delete_favorite_cmd.send("您还没有收藏任何一言")
        return
    
    if index > len(favorites):
        await delete_favorite_cmd.send(f"序号超出范围，您只有 {len(favorites)} 条收藏")
        return
    
    # 删除收藏
    favorite = favorites[index-1]
    short_content = favorite.content[:20] + "..." if len(favorite.content) > 20 else favorite.content
    favorite_manager.remove_favorite(platform, user_id, index-1)
    logger.info(f"用户 {composite_id} 删除了收藏: {short_content}")
    
    await delete_favorite_cmd.send(f"收藏已删除: {short_content}") 