from typing import List, Set

from nonebot.log import logger
from nonebot import get_driver
from nonebot_plugin_alconna import on_alconna, Alconna, CommandResult, Subcommand

from ..config import Config, plugin_config

# 获取全局配置
global_config = get_driver().config

# 获取命令前缀集合，如果没有配置则默认为 ["/"]
cmd_start: Set[str] = getattr(global_config, "command_start", {"/", })
# 使用第一个命令前缀作为帮助显示
cmd_prefix = next(iter(cmd_start)) if cmd_start else "/"

# 创建帮助命令
help_cmd = on_alconna(
    Alconna(
        "一言帮助",
        Subcommand("基础", help_text="获取一言基础命令帮助"),
        Subcommand("收藏", help_text="获取一言收藏功能帮助"),
        Subcommand("类型", help_text="获取一言支持的类型列表"),
    ),
    aliases={"hitokoto_help", "yiyan_help"},
    use_cmd_start=True,
    block=True
)


@help_cmd.handle()
async def handle_help(result: CommandResult) -> None:
    """处理帮助命令"""
    # 默认显示总帮助
    if not result.result:
        await help_cmd.send(get_general_help())
        return
    
    # 根据子命令提供不同的帮助信息
    if result.result.find("基础"):
        await help_cmd.send(get_basic_help())
    elif result.result.find("收藏"):
        await help_cmd.send(get_favorite_help())
    elif result.result.find("类型"):
        await help_cmd.send(get_types_help())
    else:
        await help_cmd.send(get_general_help())


def get_general_help() -> str:
    """获取总帮助信息"""
    help_text: List[str] = [
        "🌟 一言+插件帮助 🌟",
        "------------------------",
        "",
        "可用命令：",
        f"1. {cmd_prefix}一言帮助 基础 - 获取基础命令帮助",
        f"2. {cmd_prefix}一言帮助 收藏 - 获取收藏功能帮助",
        f"3. {cmd_prefix}一言帮助 类型 - 获取支持的一言类型列表",
        "",
        "快速上手：",
        f"- 发送 {cmd_prefix}一言 获取一条随机一言",
        f"- 发送 {cmd_prefix}一言收藏 收藏上一次获取的一言",
        f"- 发送 {cmd_prefix}一言收藏列表 查看已收藏的一言列表"
    ]
    return "\n".join(help_text)


def get_basic_help() -> str:
    """获取基础命令帮助"""
    help_text: List[str] = [
        "📖 一言+·基础命令帮助 📖",
        "------------------------",
        "命令格式：",
        f"1. {cmd_prefix}一言 - 获取一条随机一言",
        f"2. {cmd_prefix}一言 [类型] - 获取指定类型的一言",
        "",
        "示例：",
        f"- {cmd_prefix}一言",
        f"- {cmd_prefix}一言 动画",
        f"- {cmd_prefix}一言 文学",
        "",
        "说明：",
        f"- 调用冷却时间为 {plugin_config.hitp_cd} 秒",
        f"- 可使用 {cmd_prefix}一言帮助 类型 查看支持的类型"
    ]
    return "\n".join(help_text)


def get_favorite_help() -> str:
    """获取收藏功能帮助"""
    help_text: List[str] = [
        "💾 一言+·收藏功能帮助 💾",
        "------------------------",
        "命令列表：",
        f"1. {cmd_prefix}一言收藏 - 收藏上一次获取的一言",
        f"2. {cmd_prefix}一言收藏列表 - 查看收藏列表",
        f"3. {cmd_prefix}一言收藏列表 -p [页码] - 查看指定页的收藏",
        f"4. {cmd_prefix}一言查看收藏 [序号] - 查看指定序号的收藏详情",
        f"5. {cmd_prefix}一言删除收藏 [序号] - 删除指定序号的收藏",
        "",
        "说明：",
        f"- 在获取一言后 {plugin_config.hitp_favorite_timeout} 秒内可以使用 {cmd_prefix}一言收藏 命令收藏",
        f"- 收藏列表每页显示 {plugin_config.hitp_favorite_list_limit} 条记录",
        "- 收藏序号从1开始计数"
    ]
    return "\n".join(help_text)


def get_types_help() -> str:
    """获取类型帮助信息"""
    type_map = plugin_config.hitp_type_map
    
    help_text: List[str] = [
        "📋 一言支持的类型 📋",
        "------------------------",
        "支持的类型列表："
    ]
    
    # 使用列表推导式添加类型列表
    help_text.extend([f"- {name} (代码: {code})" for name, code in type_map.items()])
    
    help_text.extend([
        "",
        "使用方法：",
        f"- {cmd_prefix}一言 [类型名称] - 例如：{cmd_prefix}一言 动画",
        "- 不指定类型则随机获取"
    ])
    
    return "\n".join(help_text) 