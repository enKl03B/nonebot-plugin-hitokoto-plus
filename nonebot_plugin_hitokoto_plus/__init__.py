from nonebot.plugin import PluginMetadata

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
    config=None,
    supported_adapters=None,
) 