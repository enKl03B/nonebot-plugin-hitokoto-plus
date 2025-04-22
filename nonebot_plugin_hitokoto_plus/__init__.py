from nonebot.plugin import PluginMetadata, inherit_supported_adapters
from nonebot import require

# 集中导入所有依赖的库插件
require("nonebot_plugin_alconna")
require("nonebot_plugin_uninfo")
require("nonebot_plugin_apscheduler")
require("nonebot_plugin_localstore")

from .config import Config
from .rate_limiter import rate_limiter
import importlib

from . import handlers

from .api import get_hitokoto
from .handlers import (
    hitokoto_cmd, 
    favorite_list_cmd, 
    add_favorite_cmd, 
    view_favorite_cmd, 
    delete_favorite_cmd,
    help_cmd
)


__plugin_meta__ = PluginMetadata(
    name="一言+",
    description="（可能是）更好的一言插件！",
    usage="使用 /一言帮助 获取详细帮助",
    homepage="https://github.com/enKl03B/nonebot-plugin-hitokoto-plus",
    type="application",
    config=Config,
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna", "nonebot_plugin_uninfo"),
) 