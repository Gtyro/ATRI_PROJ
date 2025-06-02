<template>
  <div class="memory-filter">
    <el-form label-width="80px" size="default">
      <el-form-item label="会话选择">
        <el-select 
          v-model="selectedConv" 
          placeholder="请选择会话" 
          clearable
          @change="handleConvChange"
        >
          <el-option
            v-for="conv in conversations"
            :key="conv.id"
            :label="conv.name"
            :value="conv.id"
          />
        </el-select>
      </el-form-item>
      
      <el-form-item label="时间范围">
        <el-date-picker
          v-model="dateRange"
          type="datetimerange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          :shortcuts="shortcuts"
          @change="handleDateRangeChange"
        />
      </el-form-item>
      
      <el-form-item>
        <el-button type="primary" @click="applyFilter">应用筛选</el-button>
        <el-button @click="resetFilter">重置</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';

const props = defineProps({
  conversations: {
    type: Array,
    default: () => []
  },
  defaultConvId: {
    type: String,
    default: ''
  },
  timeRange: {
    type: Object,
    default: () => ({ start: null, end: null })
  }
});

const emit = defineEmits(['update:conv-id', 'update:time-range', 'filter']);

// 本地状态
const selectedConv = ref(props.defaultConvId);
const dateRange = ref(null);

// 日期快捷选项
const shortcuts = [
  {
    text: '最近一天',
    value: () => {
      const end = new Date();
      const start = new Date();
      start.setTime(start.getTime() - 3600 * 1000 * 24);
      return [start, end];
    },
  },
  {
    text: '最近一周',
    value: () => {
      const end = new Date();
      const start = new Date();
      start.setTime(start.getTime() - 3600 * 1000 * 24 * 7);
      return [start, end];
    },
  },
  {
    text: '最近一个月',
    value: () => {
      const end = new Date();
      const start = new Date();
      start.setMonth(start.getMonth() - 1);
      return [start, end];
    },
  },
  {
    text: '最近三个月',
    value: () => {
      const end = new Date();
      const start = new Date();
      start.setMonth(start.getMonth() - 3);
      return [start, end];
    },
  }
];

// 处理会话变更
const handleConvChange = (value) => {
  emit('update:conv-id', value);
};

// 处理日期范围变更
const handleDateRangeChange = (value) => {
  if (!value) {
    emit('update:time-range', { start: null, end: null });
    return;
  }
  
  emit('update:time-range', {
    start: value[0],
    end: value[1]
  });
};

// 应用筛选
const applyFilter = () => {
  emit('filter', {
    convId: selectedConv.value,
    timeRange: dateRange.value 
      ? { start: dateRange.value[0], end: dateRange.value[1] } 
      : { start: null, end: null }
  });
};

// 重置筛选条件
const resetFilter = () => {
  selectedConv.value = '';
  dateRange.value = null;
  
  emit('update:conv-id', '');
  emit('update:time-range', { start: null, end: null });
  emit('filter', {
    convId: '',
    timeRange: { start: null, end: null }
  });
};

// 监听props变化
watch(() => props.defaultConvId, (newVal) => {
  selectedConv.value = newVal;
});

watch(() => props.timeRange, (newVal) => {
  if (newVal.start && newVal.end) {
    dateRange.value = [newVal.start, newVal.end];
  } else {
    dateRange.value = null;
  }
}, { deep: true });
</script>

<style scoped>
.memory-filter {
  padding: 16px;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  margin-bottom: 16px;
}

.el-date-picker {
  width: 100%;
}
</style> 