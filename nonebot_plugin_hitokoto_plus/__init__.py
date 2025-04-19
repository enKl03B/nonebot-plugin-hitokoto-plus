from nonebot.plugin import PluginMetadata
from nonebot_plugin_alconna.uniseg import SupportAdapterModule
from nonebot_plugin_uninfo.constraint import SupportAdapterModule as UninfoSupportAdapterModule
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


__supported_adapters__ = set(m.value for m in SupportAdapterModule.__members__.values()) | set(m.value for m in UninfoSupportAdapterModule.__members__.values())

__plugin_meta__ = PluginMetadata(
    name="一言+",
    description="（可能是）更好的一言插件！",
    usage="使用 /一言帮助 获取详细帮助",
    homepage="https://github.com/enKl03B/nonebot-plugin-hitokoto-plus",
    type="application",
    config=Config,
    supported_adapters=__supported_adapters__,
) 