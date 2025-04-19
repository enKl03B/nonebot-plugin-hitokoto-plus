from typing import List

from nonebot.log import logger
from nonebot import get_plugin_config
from nonebot_plugin_alconna import on_alconna, Alconna, CommandResult, Subcommand

from ..config import Config

# 获取插件配置
plugin_config = get_plugin_config(Config)

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
        "插件功能：获取一言内容并支持收藏管理",
        "",
        "可用命令：",
        "1. /一言帮助 基础 - 获取基础命令帮助",
        "2. /一言帮助 收藏 - 获取收藏功能帮助",
        "3. /一言帮助 类型 - 获取支持的一言类型列表",
        "",
        "快速上手：",
        "- 发送 /一言 获取一条随机一言",
        "- 发送 /一言收藏 收藏上一次获取的一言",
        "- 发送 /一言收藏列表 查看已收藏的一言列表"
    ]
    return "\n".join(help_text)


def get_basic_help() -> str:
    """获取基础命令帮助"""
    help_text: List[str] = [
        "📖 一言基础命令帮助 📖",
        "------------------------",
        "命令格式：",
        "1. /一言 - 获取一条随机一言",
        "2. /一言 [类型] - 获取指定类型的一言",
        "",
        "示例：",
        "- /一言",
        "- /一言 动画",
        "- /一言 文学",
        "",
        "说明：",
        f"- 调用冷却时间为 {plugin_config.hitokoto_cd} 秒",
        "- 可使用 /一言帮助 类型 查看支持的类型"
    ]
    return "\n".join(help_text)


def get_favorite_help() -> str:
    """获取收藏功能帮助"""
    help_text: List[str] = [
        "💾 一言收藏功能帮助 💾",
        "------------------------",
        "命令列表：",
        "1. /一言收藏 - 收藏上一次获取的一言",
        "2. /一言收藏列表 - 查看收藏列表",
        "3. /一言收藏列表 -p [页码] - 查看指定页的收藏",
        "4. /一言查看收藏 [序号] - 查看指定序号的收藏详情",
        "5. /一言删除收藏 [序号] - 删除指定序号的收藏",
        "",
        "说明：",
        f"- 在获取一言后 {plugin_config.hitokoto_favorite_timeout} 秒内可以使用 /一言收藏 命令收藏",
        f"- 收藏列表每页显示 {plugin_config.hitokoto_favorite_list_limit} 条记录",
        "- 收藏序号从1开始计数"
    ]
    return "\n".join(help_text)


def get_types_help() -> str:
    """获取类型帮助信息"""
    type_map = plugin_config.hitokoto_type_map
    
    help_text: List[str] = [
        "📋 一言支持的类型 📋",
        "------------------------",
        "支持的类型列表："
    ]
    
    for name, code in type_map.items():
        help_text.append(f"- {name} (代码: {code})")
    
    help_text.extend([
        "",
        "使用方法：",
        "- /一言 [类型名称] - 例如：/一言 动画",
        "- 不指定类型则随机获取"
    ])
    
    return "\n".join(help_text) 