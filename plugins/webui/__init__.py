from nonebot.plugin import PluginMetadata
# Import backend to ensure its lifecycle hooks are registered
from . import backend

# 插件元数据
__plugin_meta__ = PluginMetadata(
    name="WebUI管理面板",
    description="提供可视化的方式管理和监控您的数据库",
    usage="启动后访问 http://127.0.0.1:8080/webui",
    type="application",
    homepage="https://github.com/yourusername/nonebot-plugin-webui",
    config=None,
    supported_adapters={"~onebot.v11"}
)
