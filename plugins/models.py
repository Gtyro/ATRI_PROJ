from typing import List
from tortoise import Model, fields

class GroupPluginConfig(Model):
    id = fields.IntField(pk=True)
    gid = fields.CharField(max_length=20, index=True)
    '''group id'''
    name = fields.CharField(max_length=50)
    '''group name'''
    plugin_name = fields.CharField(max_length=50)
    '''plugin name'''
    plugin_config = fields.TextField()
    '''plugin config'''

    class Meta:
        table = "group_plugin_configs"
        unique_together = (('gid', 'plugin_name'))

    def __str__(self):
        return f"{self.name} - {self.plugin_name}"
    
    @classmethod
    async def get_config(cls, gid: str, plugin_name: str):
        '''获取群组插件配置'''
        config, _ = await cls.get_or_create(gid=gid, plugin_name=plugin_name, defaults={'plugin_config': {}})
        return config
    
    @classmethod
    async def update_config(cls, gid: str, plugin_name: str, config: dict):
        '''更新群组插件配置'''
        config = await cls.get_config(gid, plugin_name)
        config.plugin_config = config
        await config.save()

    @classmethod
    async def get_distinct_group_ids(cls, plugin_name: str) -> List[str]:
        '''获取所有不同的群组ID'''
        return await cls.filter(plugin_name=plugin_name).values_list('gid', flat=True)
