from typing import List

from tortoise import Model, fields


class PluginConfig(Model):
    id = fields.IntField(primary_key=True)
    plugin_name = fields.CharField(max_length=50)
    """plugin name"""
    plugin_config = fields.JSONField(default={})
    """plugin config"""

    class Meta:
        table = "plugin_configs"
        unique_together = (("plugin_name",),)
        connection_name = "default"


class GroupConfig(Model):
    id = fields.IntField(primary_key=True)
    """group id"""
    name = fields.CharField(max_length=50)
    """group name"""


class GroupPluginConfig(Model):
    id = fields.IntField(primary_key=True)
    gid = fields.CharField(max_length=20, db_index=True)
    """group id"""
    name = fields.CharField(max_length=50)
    """group name"""
    plugin_name = fields.CharField(max_length=50)
    """plugin name"""
    plugin_config = fields.JSONField(default={})
    """plugin config"""

    class Meta:
        table = "group_plugin_configs"
        unique_together = (("gid", "plugin_name"),)
        connection_name = "default"

    def __str__(self):
        return f"{self.name} - {self.plugin_name}"

    @classmethod
    async def get_config(cls, gid: str, plugin_name: str):
        """获取群组插件配置"""
        config, _ = await cls.get_or_create(
            gid=gid,
            name=gid,
            plugin_name=plugin_name,
            defaults={"plugin_config": {}},
        )
        return config

    @classmethod
    async def update_config(cls, gid: str, plugin_name: str, config: dict):
        """更新群组插件配置"""
        gpconfig = await cls.get_config(gid, plugin_name)
        gpconfig.plugin_config = config
        await gpconfig.save()

    @classmethod
    async def get_distinct_group_ids(cls, plugin_name: str) -> List[str]:
        """获取所有不同的群组ID"""
        return await cls.filter(plugin_name=plugin_name).values_list("gid", flat=True)


class GroupPluginPolicy(Model):
    id = fields.IntField(primary_key=True)
    gid = fields.CharField(max_length=20, db_index=True)
    """group id"""
    name = fields.CharField(max_length=50)
    """group name"""
    plugin_name = fields.CharField(max_length=50)
    """plugin name"""
    enabled = fields.BooleanField(default=True)
    """whether plugin is enabled for the group"""
    ingest_enabled = fields.BooleanField(default=True)
    """whether ingestion is enabled for the group"""
    policy_config = fields.JSONField(default={})
    """extra policy config"""

    class Meta:
        table = "group_plugin_policies"
        unique_together = (("gid", "plugin_name"),)
        connection_name = "default"

    def __str__(self):
        return f"{self.name} - {self.plugin_name}"


class ModuleMetricModule(Model):
    id = fields.IntField(primary_key=True)
    module_id = fields.CharField(max_length=160, unique=True)
    plugin_name = fields.CharField(max_length=50)
    module_name = fields.CharField(max_length=100)
    display_name = fields.CharField(max_length=100)
    is_active = fields.BooleanField(default=True)
    extra = fields.JSONField(default=dict)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "module_metric_modules"
        indexes = (
            ("plugin_name", "module_name"),
            ("is_active",),
        )
        connection_name = "default"


class ModuleMetricEvent(Model):
    id = fields.IntField(primary_key=True)
    module_id = fields.CharField(max_length=160)
    plugin_name = fields.CharField(max_length=50)
    module_name = fields.CharField(max_length=100)
    operation = fields.CharField(max_length=100)
    phase = fields.CharField(max_length=100, null=True)
    resolved_via = fields.CharField(max_length=100, null=True)
    conv_id = fields.CharField(max_length=50, null=True)
    message_id = fields.CharField(max_length=100, null=True)
    provider_name = fields.CharField(max_length=100, null=True)
    model = fields.CharField(max_length=100, null=True)
    request_id = fields.CharField(max_length=100, null=True)
    success = fields.BooleanField(default=True)
    prompt_tokens = fields.IntField(null=True)
    completion_tokens = fields.IntField(null=True)
    total_tokens = fields.IntField(null=True)
    error_type = fields.CharField(max_length=100, null=True)
    extra = fields.JSONField(default=dict)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "module_metric_events"
        indexes = (
            ("created_at",),
            ("module_id", "created_at"),
            ("plugin_name", "module_name", "created_at"),
            ("phase", "resolved_via", "created_at"),
            ("conv_id", "created_at"),
            ("request_id",),
        )
        connection_name = "default"


# 兼容旧引用路径，后续可移除。
PluginModuleMetricEvent = ModuleMetricEvent
