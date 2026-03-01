<template>
  <div class="plugin-policy-page" data-testid="plugin-policy-page">
    <el-card class="box-card" shadow="never">
      <template #header>
        <div class="card-header-row">
          <h3>群组插件管理</h3>
          <el-alert
            title="说明"
            type="info"
            :closable="false"
            class="info-alert"
          >
            这里用于控制“群组 x 插件”启停开关；persona
            支持短期记忆（入库）/长期记忆（记忆提取）/被动回复/主动回复的分开关。
          </el-alert>
          <div class="header-actions">
            <el-button
              type="primary"
              size="small"
              :loading="loading"
              @click="loadMatrix"
              data-testid="policy-refresh"
            >
              刷新
            </el-button>
          </div>
        </div>
      </template>

      <el-table
        v-loading="loading"
        :data="rows"
        border
        height="100%"
        class="policy-table"
        style="width: 100%"
      >
        <el-table-column label="群组" min-width="200" fixed="left">
          <template #default="scope">
            <div class="group-name">{{ scope.row.group_name }}</div>
            <div class="group-id">ID: {{ scope.row.group_id }}</div>
          </template>
        </el-table-column>

        <el-table-column label="全组启用" min-width="120">
          <template #default="scope">
            <el-switch
              :model-value="isGroupAllEnabled(scope.row)"
              size="small"
              :disabled="loading || plugins.length === 0"
              @change="onToggleGroupAll(scope.row, $event)"
            />
          </template>
        </el-table-column>

        <el-table-column
          v-for="plugin in plugins"
          :key="plugin"
          :label="plugin"
          min-width="140"
        >
          <template #header>
            <div class="plugin-header">
              <div class="plugin-header-row">
                <span>{{ plugin }}</span>
                <el-switch
                  :model-value="isPluginAllEnabled(plugin)"
                  size="small"
                  :disabled="loading || groups.length === 0"
                  @change="onTogglePluginAll(plugin, $event)"
                />
              </div>
              <div
                v-for="control in getPluginControls(plugin)"
                :key="control.key"
                class="plugin-header-row"
              >
                <span>{{ control.label }}</span>
                <el-switch
                  :model-value="isPluginControlAllEnabled(plugin, control)"
                  size="small"
                  :disabled="loading || groups.length === 0"
                  @change="onTogglePluginControlAll(plugin, control, $event)"
                />
              </div>
            </div>
          </template>
          <template #default="scope">
            <div class="policy-cell">
              <div class="policy-row">
                <span>启用</span>
                <el-switch
                  v-model="scope.row.policies[plugin].enabled"
                  size="small"
                  @change="onTogglePlugin(scope.row, plugin)"
                  :data-testid="`policy-enabled-${scope.row.group_id}-${plugin}`"
                />
              </div>
              <div
                v-for="control in getPluginControls(plugin)"
                :key="control.key"
                class="policy-row"
              >
                <span>{{ control.label }}</span>
                <el-switch
                  :model-value="
                    getPolicyControlValue(scope.row, plugin, control)
                  "
                  size="small"
                  :disabled="isControlDisabled()"
                  @change="
                    onTogglePolicyControl(scope.row, plugin, control, $event)
                  "
                />
              </div>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import {
  batchUpdatePolicy,
  fetchPolicyMatrix,
  updatePolicy,
} from "@/api/plugin_policy";

const loading = ref(false);
const groups = ref([]);
const plugins = ref([]);
const policyMap = ref({});
const policyMeta = ref({});
const pluginDefaults = ref({
  global: { enabled: true, ingest_enabled: true, config: {} },
  plugins: {},
});

const resolveDefaults = (plugin) => {
  const defaults =
    pluginDefaults.value.plugins[plugin] || pluginDefaults.value.global;
  return {
    ...defaults,
    config: defaults?.config || {},
  };
};

const cloneConfig = (config) => {
  return JSON.parse(JSON.stringify(config || {}));
};

const clonePolicy = (policy) => {
  return JSON.parse(JSON.stringify(policy || {}));
};

const mergePolicyConfig = (plugin, config) => {
  const defaults = resolveDefaults(plugin).config || {};
  return {
    ...defaults,
    ...(config || {}),
  };
};

const normalizePolicy = (policy) => {
  return {
    ...policy,
    config: mergePolicyConfig(policy.plugin_name, policy.config),
  };
};

const buildDefaultPolicy = (group, plugin) => {
  const defaults = resolveDefaults(plugin);
  return {
    gid: group.group_id,
    plugin_name: plugin,
    enabled: defaults.enabled,
    ingest_enabled: defaults.ingest_enabled,
    group_name: group.group_name,
    config: cloneConfig(defaults.config),
  };
};

const rows = computed(() => {
  return groups.value.map((group) => {
    const policies = {};
    plugins.value.forEach((plugin) => {
      const key = `${group.group_id}::${plugin}`;
      policies[plugin] =
        policyMap.value[key] || buildDefaultPolicy(group, plugin);
    });
    return {
      group_id: group.group_id,
      group_name: group.group_name,
      policies,
    };
  });
});

const isGroupAllEnabled = (row) => {
  if (plugins.value.length === 0) {
    return false;
  }
  return plugins.value.every((plugin) => row.policies[plugin]?.enabled);
};

const isPluginAllEnabled = (plugin) => {
  if (rows.value.length === 0) {
    return false;
  }
  return rows.value.every((row) => row.policies[plugin]?.enabled);
};

const getPluginControls = (plugin) => {
  return policyMeta.value?.[plugin]?.controls || [];
};

const getControlTarget = (control) => {
  const target = control?.target;
  return typeof target === "string" && target ? target : "config";
};

const getControlConfigKeys = (control) => {
  const keys = [];
  if (typeof control?.key === "string" && control.key) {
    keys.push(control.key);
  }
  if (Array.isArray(control?.also_set)) {
    control.also_set.forEach((item) => {
      if (typeof item === "string" && item && !keys.includes(item)) {
        keys.push(item);
      }
    });
  }
  return keys;
};

const getPolicyControlValue = (row, plugin, control) => {
  const policy = row.policies?.[plugin];
  if (!policy) {
    return false;
  }
  if (getControlTarget(control) === "ingest") {
    return policy.ingest_enabled ?? false;
  }
  const config = policy.config || {};
  const keys = getControlConfigKeys(control);
  if (keys.length === 0) {
    return false;
  }
  return keys.every((key) => Boolean(config[key]));
};

const isControlDisabled = () => {
  return loading.value;
};

const isPluginControlAllEnabled = (plugin, control) => {
  if (rows.value.length === 0) {
    return false;
  }
  return rows.value.every((row) => getPolicyControlValue(row, plugin, control));
};

const loadMatrix = async () => {
  loading.value = true;
  try {
    const { data } = await fetchPolicyMatrix();
    groups.value = data.groups || [];
    plugins.value = data.plugins || [];
    pluginDefaults.value = data.defaults || pluginDefaults.value;
    policyMeta.value = data.policy_meta || {};
    const map = {};
    (data.policies || []).forEach((policy) => {
      map[`${policy.gid}::${policy.plugin_name}`] = normalizePolicy(policy);
    });
    policyMap.value = map;
  } catch (error) {
    ElMessage.error("加载插件策略失败");
  } finally {
    loading.value = false;
  }
};

const onTogglePlugin = async (row, plugin) => {
  const key = `${row.group_id}::${plugin}`;
  const previous = clonePolicy(
    policyMap.value[key] || buildDefaultPolicy(row, plugin),
  );
  const current = row.policies[plugin];

  try {
    const { data } = await updatePolicy({
      gid: row.group_id,
      plugin_name: plugin,
      enabled: current.enabled,
      group_name: row.group_name,
    });
    policyMap.value = {
      ...policyMap.value,
      [key]: normalizePolicy(data.policy),
    };
    ElMessage.success("策略已更新");
  } catch (error) {
    policyMap.value = {
      ...policyMap.value,
      [key]: previous,
    };
    ElMessage.error("更新失败，已回滚");
  }
};

const onToggleGroupAll = async (row, enabled) => {
  try {
    await batchUpdatePolicy({
      gid: row.group_id,
      enabled,
    });
    ElMessage.success("已更新该群全部插件");
    await loadMatrix();
  } catch (error) {
    ElMessage.error("批量更新失败");
  }
};

const onTogglePluginAll = async (plugin, enabled) => {
  try {
    await batchUpdatePolicy({
      plugin_name: plugin,
      enabled,
    });
    ElMessage.success(`已更新插件 ${plugin} 在全部群组的状态`);
    await loadMatrix();
  } catch (error) {
    ElMessage.error("批量更新失败");
  }
};

const onTogglePluginControlAll = async (plugin, control, enabled) => {
  const target = getControlTarget(control);
  if (target === "ingest") {
    try {
      await batchUpdatePolicy({
        plugin_name: plugin,
        ingest_enabled: enabled,
      });
      ElMessage.success(`已更新插件 ${plugin} 的${control.label}开关`);
      await loadMatrix();
    } catch (error) {
      ElMessage.error("批量更新失败");
    }
    return;
  }
  const configKeys = getControlConfigKeys(control);
  if (configKeys.length === 0) {
    return;
  }
  const patch = {};
  configKeys.forEach((key) => {
    patch[key] = enabled;
  });
  try {
    await batchUpdatePolicy({
      plugin_name: plugin,
      config: patch,
    });
    ElMessage.success(`已更新插件 ${plugin} 的${control.label}开关`);
    await loadMatrix();
  } catch (error) {
    ElMessage.error("批量更新失败");
  }
};

const onTogglePolicyControl = async (row, plugin, control, enabled) => {
  const key = `${row.group_id}::${plugin}`;
  const previous = clonePolicy(
    policyMap.value[key] || buildDefaultPolicy(row, plugin),
  );
  const current = row.policies[plugin];
  const target = getControlTarget(control);
  if (target === "ingest") {
    current.ingest_enabled = enabled;
    try {
      const { data } = await updatePolicy({
        gid: row.group_id,
        plugin_name: plugin,
        ingest_enabled: enabled,
        group_name: row.group_name,
      });
      policyMap.value = {
        ...policyMap.value,
        [key]: normalizePolicy(data.policy),
      };
      ElMessage.success(`${control.label}已更新`);
    } catch (error) {
      policyMap.value = {
        ...policyMap.value,
        [key]: previous,
      };
      ElMessage.error("更新失败，已回滚");
    }
    return;
  }
  const configKeys = getControlConfigKeys(control);
  if (configKeys.length === 0) {
    return;
  }
  const nextConfig = {
    ...(current.config || {}),
  };
  configKeys.forEach((configKey) => {
    nextConfig[configKey] = enabled;
  });
  current.config = nextConfig;

  try {
    const { data } = await updatePolicy({
      gid: row.group_id,
      plugin_name: plugin,
      config: nextConfig,
      group_name: row.group_name,
    });
    policyMap.value = {
      ...policyMap.value,
      [key]: normalizePolicy(data.policy),
    };
    ElMessage.success("配置已更新");
  } catch (error) {
    policyMap.value = {
      ...policyMap.value,
      [key]: previous,
    };
    ElMessage.error("更新失败，已回滚");
  }
};

onMounted(loadMatrix);
</script>

<style scoped>
.plugin-policy-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

.box-card {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

:deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.card-header-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.card-header-row h3 {
  margin: 0;
  white-space: nowrap;
}

.header-actions {
  white-space: nowrap;
}

.info-alert {
  margin: 0 16px;
  flex: 1;
  padding: 8px 16px;
}

.policy-table :deep(.el-table__cell) {
  vertical-align: top;
}

.plugin-header {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.plugin-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  font-size: 12px;
}

.plugin-header-row span,
.policy-row span {
  flex: 1;
  min-width: 0;
}

.group-name {
  font-weight: 600;
}

.group-id {
  color: #8c8c8c;
  font-size: 12px;
  margin-top: 4px;
}

.policy-cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.policy-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  font-size: 12px;
}
</style>
