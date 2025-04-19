from typing import Optional, List
import math

from nonebot.adapters import Event
from nonebot.log import logger
from nonebot import get_plugin_config
from nonebot_plugin_alconna import on_alconna, Args, Alconna, CommandResult, Option
from nonebot_plugin_alconna.uniseg import UniMessage, Text, At
from nonebot import require

# 导入uninfo插件
require("nonebot_plugin_uninfo")
from nonebot_plugin_uninfo import Uninfo

from ..config import Config
from ..models import favorite_manager, HitokotoFavorite
from .basic import check_permission

# 获取插件配置
plugin_config = get_plugin_config(Config)

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
async def handle_favorite_list(event: Event, result: CommandResult, session: Uninfo) -> None:
    """处理收藏列表命令"""
    # 获取跨平台用户标识
    platform = session.adapter
    user_id = session.user.id
    user_name = session.user.name  # 获取用户昵称
    
    # 检查黑白名单
    if not check_permission(session):
        logger.info(f"用户 {platform}:{user_id} 因黑白名单限制被拒绝访问收藏列表")
        return
    
    # 获取页码参数
    page = 1
    if result.result and "-p" in result.result.options:
        page_arg = result.result.options["-p"]
        if page_arg and "page" in page_arg:
            page = max(1, page_arg["page"])
    
    # 获取用户收藏列表
    favorites = favorite_manager.get_favorites(platform, user_id)
    
    # 计算总页数
    page_size = plugin_config.hitokoto_favorite_list_limit
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
    msg_list = []
    msg_list.append(f"{user_name} 的一言收藏")
    msg_list.append(f"（{page}/{total_pages}页，共{len(favorites)}条）")
    msg_list.append("----------")
    for i, fav in enumerate(current_page_favorites, start=start_idx + 1):
        # 使用简短显示模板
        short_content = fav.content
        if len(short_content) > 30:
            short_content = short_content[:30] + "..."
        
        msg_list.append(f"{i}. {short_content}")
    
    msg_list.append("----------")
    msg_list.append("\n使用 /一言查看收藏 [序号] 可查看详情")
    msg_list.append("使用 /一言删除收藏 [序号] 可删除收藏")
    msg_list.append("使用 /一言收藏列表 -p [页码] 可查看其他页")
    
    await favorite_list_cmd.send("\n".join(msg_list))


@add_favorite_cmd.handle()
async def handle_add_favorite(event: Event, session: Uninfo) -> None:
    """处理添加收藏命令"""
    # 获取跨平台用户标识
    platform = session.adapter
    user_id = session.user.id
    
    # 检查黑白名单
    if not check_permission(session):
        logger.debug(f"用户 {platform}:{user_id} 因黑白名单限制被拒绝添加收藏")
        return
    
    # 添加收藏
    favorite = favorite_manager.add_favorite(platform, user_id)
    
    if favorite is None:
        await add_favorite_cmd.send("添加收藏失败，您可能尚未获取一言或已经收藏过该条目")
        return
    
    # 发送成功消息
    await add_favorite_cmd.send(f"已收藏：\n{favorite.content}")


@view_favorite_cmd.handle()
async def handle_view_favorite(event: Event, result: CommandResult, session: Uninfo) -> None:
    """处理查看收藏详情命令"""
    # 获取跨平台用户标识
    platform = session.adapter
    user_id = session.user.id
    
    # 检查黑白名单
    if not check_permission(session):
        logger.debug(f"用户 {platform}:{user_id} 因黑白名单限制被拒绝查看收藏")
        return
    
    # 获取序号参数
    index = 0
    if result.result and "index" in result.result.main_args:
        index = result.result.main_args["index"]
        
    # 索引转换（用户输入是从1开始，程序内部是从0开始）
    index = max(1, index) - 1
    
    # 获取指定收藏
    favorite = favorite_manager.get_favorite_by_index(platform, user_id, index)
    
    if favorite is None:
        await view_favorite_cmd.send(f"未找到序号为 {index + 1} 的收藏")
        return
    
    # 格式化收藏详情
    formatted_favorite = (
        f"{favorite.content}\n"
        f"----------\n"
        f"类型：{favorite.type_name}\n"
        f"作者：{favorite.creator}\n"
        f"来源：{favorite.source}\n"
        f"收藏时间：{favorite.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    await view_favorite_cmd.send(formatted_favorite)


@delete_favorite_cmd.handle()
async def handle_delete_favorite(event: Event, result: CommandResult, session: Uninfo) -> None:
    """处理删除收藏命令"""
    # 获取跨平台用户标识
    platform = session.adapter
    user_id = session.user.id
    
    # 检查黑白名单
    if not check_permission(session):
        logger.debug(f"用户 {platform}:{user_id} 因黑白名单限制被拒绝删除收藏")
        return
    
    # 获取序号参数
    index = 0
    if result.result and "index" in result.result.main_args:
        index = result.result.main_args["index"]
        
    # 索引转换（用户输入是从1开始，程序内部是从0开始）
    index = max(1, index) - 1
    
    # 删除收藏
    success = favorite_manager.remove_favorite(platform, user_id, index)
    
    if success:
        await delete_favorite_cmd.send(f"已删除序号为 {index + 1} 的收藏")
    else:
        await delete_favorite_cmd.send(f"删除失败，未找到序号为 {index + 1} 的收藏") 