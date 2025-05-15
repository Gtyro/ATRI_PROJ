<template>
  <div class="panel-container">
    <h3>系统运行信息</h3>
    <div class="panel-content">
      <el-descriptions direction="vertical" :column="1" border>
        <el-descriptions-item label="CPU 使用率">
          <el-progress :percentage="45" :format="percentFormat" />
        </el-descriptions-item>
        <el-descriptions-item label="内存使用率">
          <el-progress :percentage="68" :format="percentFormat" />
        </el-descriptions-item>
        <el-descriptions-item label="磁盘使用率">
          <el-progress :percentage="32" :format="percentFormat" />
        </el-descriptions-item>
      </el-descriptions>
    </div>
  </div>
</template>

<script setup>
const percentFormat = (val) => {
  return val + '%'
}
</script>

<style scoped>
.panel-container {
  height: 100%;
  padding: 15px;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0,0,0,0.1);
}

.panel-container h3 {
  margin-top: 0;
  padding-bottom: 10px;
  border-bottom: 1px solid #eaeaea;
  color: #606266;
}

.panel-content {
  margin-top: 15px;
}
</style> 