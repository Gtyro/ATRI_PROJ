<template>
  <div class="memory-admin">
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <h3>记忆管理</h3>
          <div class="header-controls">
            <el-select
              v-model="selectedConvId"
              placeholder="选择会话ID"
              clearable
              @change="loadGraphData"
            >
              <el-option
                v-for="conv in convOptions"
                :key="conv.value"
                :label="conv.label"
                :value="conv.value"
              />
            </el-select>
            <el-input-number
              v-model="nodeLimit"
              :min="10"
              :max="200"
              :step="10"
              size="small"
              @change="loadGraphData"
            >
              <template #prepend>节点数量限制:</template>
            </el-input-number>
            <el-button type="primary" @click="loadGraphData">刷新</el-button>
          </div>
        </div>
      </template>

      <div class="memory-content">
        <el-alert
          title="记忆管理面板"
          type="info"
          :closable="false"
        >
          这里是知识图谱可视化区域，您可以查看系统的认知节点和关联。节点按激活水平降序排列，显示前{{ nodeLimit }}个节点。
        </el-alert>

        <div class="graph-info-container">
          <div class="graph-info">
            <p><strong>当前视图：</strong> {{ graphTitle }}</p>
            <p><strong>节点数量：</strong> {{ nodeCount }}</p>
            <p><strong>关联数量：</strong> {{ linkCount }}</p>
          </div>

          <div class="graph-legend">
            <div class="legend-item">
              <div class="legend-color" style="background-color: #5470c6;"></div>
              <span>节点大小 - 表示激活水平(act_lv)</span>
            </div>
            <div class="legend-item">
              <div class="legend-line"></div>
              <span>线条粗细 - 表示关联强度(strength)</span>
            </div>
          </div>
        </div>

        <div class="graph-container" ref="graphContainer"></div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
import { getCognitiveNodes, getAssociations, getConversations } from '../api/db';
import * as echarts from 'echarts';

// 数据与状态
const graphContainer = ref(null);
const chart = ref(null);
const selectedConvId = ref('');  // 默认为空字符串，代表公共图谱
const nodeLimit = ref(50);  // 默认限制50个节点
const convOptions = ref([
  { label: '公共图谱', value: '' }  // 将值改为空字符串
]);
const nodes = ref([]);
const links = ref([]);
const loading = ref(false);
const error = ref(null);

// 计算属性
const nodeCount = computed(() => (nodes.value && nodes.value.length) || 0);
const linkCount = computed(() => (links.value && links.value.length) || 0);
const graphTitle = computed(() =>
  selectedConvId.value ? `会话 ${selectedConvId.value} 知识图谱` : '公共知识图谱'
);

// 初始化图表
const initChart = () => {
  if (!graphContainer.value) {
    console.error("图表容器不存在");
    return;
  }

  // 如果已经初始化过，先销毁
  if (chart.value) {
    chart.value.dispose();
  }

  chart.value = echarts.init(graphContainer.value);

  // 设置图表的基本配置
  const option = {
    title: {
      text: graphTitle.value,
      subtext: '节点大小表示激活水平，线条粗细表示关联强度',
      top: 'bottom',
      left: 'right'
    },
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        if (params.dataType === 'node') {
          return `
            <div style="font-weight:bold">${params.name}</div>
            <div>激活水平: ${params.data.value.toFixed(2)}</div>
            <div>会话ID: ${params.data.convId || '公共'}</div>
          `;
        } else {
          return `
            <div style="font-weight:bold">关联</div>
            <div>源: ${params.data.sourceName}</div>
            <div>目标: ${params.data.targetName}</div>
            <div>强度: ${params.data.value.toFixed(2)}</div>
          `;
        }
      }
    },
    legend: {
      show: false
    },
    animationDurationUpdate: 1500,
    animationEasingUpdate: 'quinticInOut',
    series: [{
      type: 'graph',
      layout: 'force',
      force: {
        repulsion: 100,
        gravity: 0.1,
        edgeLength: [50, 200],
        layoutAnimation: true
      },
      roam: true,
      label: {
        show: true,
        position: 'right',
        formatter: '{b}'
      },
      lineStyle: {
        color: 'source',
        curveness: 0.3,
        width: 1
      },
      emphasis: {
        focus: 'adjacency',
        lineStyle: {
          width: 3
        }
      },
      data: [],
      edges: []
    }]
  };

  // 应用配置
  chart.value.setOption(option);

  // 添加窗口大小调整事件
  window.addEventListener('resize', () => {
    chart.value && chart.value.resize();
  });

  return chart.value;
};

// 转换数据为图表所需格式
const formatGraphData = () => {
  if (!nodes.value || !nodes.value.length) {
    console.warn("没有节点数据可用");
    // 应用空数据
    chart.value.setOption({
      title: {
        text: graphTitle.value
      },
      series: [{
        data: [],
        edges: []
      }]
    });
    return;
  }

  // 格式化节点数据
  const graphNodes = nodes.value.map(node => ({
    id: node.id,
    name: node.name,
    convId: node.conv_id,
    value: parseFloat(node.act_lv) || 1.0,
    symbolSize: Math.max(20, parseFloat(node.act_lv || 1.0) * 30),
    itemStyle: {
      color: '#5470c6'
    }
  }));

  // 格式化关联数据
  const graphLinks = links.value && links.value.length ? links.value.map(link => ({
    source: link.source_id,
    target: link.target_id,
    sourceName: link.source_name,
    targetName: link.target_name,
    value: parseFloat(link.strength) || 1.0,
    lineStyle: {
      width: Math.max(1, parseFloat(link.strength || 1.0) * 3)
    }
  })) : [];

  // 更新图表数据
  chart.value.setOption({
    title: {
      text: graphTitle.value
    },
    series: [{
      data: graphNodes,
      edges: graphLinks
    }]
  });
};

// 获取节点ID列表作为字符串
const getNodeIdsString = () => {
  if (!nodes.value || !nodes.value.length) return '';
  return nodes.value.map(node => node.id).join(',');
};

// 加载图表数据
const loadGraphData = async () => {
  loading.value = true;
  error.value = null;

  try {
    // 首先获取节点数据
    const nodesResponse = await getCognitiveNodes(selectedConvId.value, nodeLimit.value);
    nodes.value = nodesResponse.data.rows || [];

    // 获取节点ID字符串
    const nodeIds = getNodeIdsString();

    // 然后获取这些节点之间的关联数据
    const linksResponse = await getAssociations(selectedConvId.value, nodeIds);
    links.value = linksResponse.data.rows || [];

    // 更新图表
    formatGraphData();
  } catch (err) {
    console.error('加载图表数据失败:', err);
    error.value = '加载数据失败，请稍后再试';
  } finally {
    loading.value = false;
  }
};

// 加载可用的会话ID选项
const loadConvOptions = async () => {
  try {
    // 使用新API获取会话ID
    const result = await getConversations();
    // 修改数据访问方式，API返回的是{columns, rows}格式
    const conversations = result.data.rows || [];

    // 更新选项
    convOptions.value = [
      { label: '公共图谱', value: '' },  // 将值改为空字符串
      ...conversations.map(conv => ({
        label: `会话 ${conv.gid} (${conv.name})`,
        value: conv.gid
      }))
    ];
  } catch (err) {
    console.error('加载会话ID选项失败:', err);
  }
};

// 生命周期钩子
onMounted(async () => {
  try {
    // 初始化图表
    initChart();

    // 先加载会话选项
    await loadConvOptions();

    // 然后加载图表数据
    await loadGraphData();
  } catch (err) {
    console.error('初始化组件时出错:', err);
    error.value = '初始化组件时出错，请刷新页面重试';
  }
});
</script>

<style scoped>
.memory-admin {
  width: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-controls {
  display: flex;
  gap: 10px;
  align-items: center;
}

.graph-container {
  height: 600px;
  margin-top: 20px;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
}

.graph-info-container {
  display: flex;
  justify-content: space-between;
  margin-top: 20px;
  padding: 10px;
  background-color: #f9f9f9;
  border-radius: 4px;
}

.graph-legend {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.legend-color {
  width: 16px;
  height: 16px;
  border-radius: 50%;
}

.legend-line {
  width: 30px;
  height: 2px;
  background-color: #5470c6;
}
</style> 