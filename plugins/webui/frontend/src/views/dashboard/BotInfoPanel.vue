<template>
  <div class="panel-container">
    <h3>机器人信息</h3>
    <div class="panel-content">
      <el-descriptions direction="vertical" :column="1" border>
        <el-descriptions-item label="Bot 名称">ATRI</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag type="success">在线</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="版本">1.0.0</el-descriptions-item>
        <el-descriptions-item label="运行时间">12小时35分钟</el-descriptions-item>
      </el-descriptions>
    </div>
  </div>
</template>

<script setup>
// Bot信息面板组件
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