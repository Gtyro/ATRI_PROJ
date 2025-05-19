<template>
  <div class="cypher-editor">
    <el-form>
      <el-form-item>
        <el-input
          v-model="query"
          :rows="6"
          type="textarea"
          placeholder="输入Cypher查询（例如：MATCH (n:CognitiveNode) RETURN n LIMIT 10）"
        ></el-input>
      </el-form-item>
      <el-form-item>
        <el-button
          type="primary"
          :loading="loading"
          @click="executeQuery"
        >
          执行查询
        </el-button>
        <el-button @click="query = ''">
          清空
        </el-button>
      </el-form-item>
    </el-form>

    <div class="examples" v-if="showExamples">
      <h4>常用Cypher查询示例：</h4>
      <div class="example-list">
        <div v-for="(example, index) in examples" :key="index" class="example-item">
          <div class="example-header">
            <span class="example-title">{{ example.title }}</span>
            <el-button size="small" @click="useExample(example.query)">使用</el-button>
          </div>
          <pre class="example-query">{{ example.query }}</pre>
          <p class="example-description">{{ example.description }}</p>
        </div>
      </div>
      <el-button
        size="small"
        @click="showExamples = false"
        style="margin-top: 10px"
      >
        隐藏示例
      </el-button>
    </div>
    <div v-else>
      <el-button
        size="small"
        type="info"
        @click="showExamples = true"
        style="margin-top: 10px"
      >
        显示Cypher查询示例
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { executeCypherQuery } from '@/api/db'

// 定义props
const props = defineProps({
  onResult: {
    type: Function,
    required: true
  }
})

const query = ref('')
const loading = ref(false)
const showExamples = ref(true)

// 查询示例
const examples = [
  {
    title: '获取所有节点标签',
    query: 'MATCH (n) RETURN DISTINCT labels(n) as labels',
    description: '返回数据库中所有节点的标签类型'
  },
  {
    title: '获取认知节点',
    query: 'MATCH (n:CognitiveNode) RETURN n.uid as id, n.name, n.conv_id, n.act_lv ORDER BY n.act_lv DESC LIMIT 20',
    description: '返回激活水平最高的20个认知节点'
  },
  {
    title: '获取节点关联',
    query: 'MATCH (n:CognitiveNode)-[r:ASSOCIATED_WITH]->(m:CognitiveNode) RETURN n.name as source, m.name as target, r.strength as strength ORDER BY r.strength DESC LIMIT 20',
    description: '返回强度最高的20个节点关联关系'
  },
  {
    title: '按会话ID查询节点',
    query: 'MATCH (n:CognitiveNode) WHERE n.conv_id = "YOUR_CONV_ID" RETURN n.uid as id, n.name, n.act_lv ORDER BY n.act_lv DESC',
    description: '返回特定会话ID的所有节点（需要替换YOUR_CONV_ID）'
  },
  {
    title: '添加新的认知节点',
    query: 'CREATE (n:CognitiveNode {name: "新节点", conv_id: "", act_lv: 1.0, is_permanent: false}) RETURN n',
    description: '创建一个新的认知节点并返回'
  }
]

// 使用示例查询
const useExample = (exampleQuery) => {
  query.value = exampleQuery
}

// 执行Neo4j查询
const executeQuery = async () => {
  if (!query.value.trim()) {
    ElMessage.warning('请输入查询语句')
    return
  }

  loading.value = true
  try {
    const response = await executeCypherQuery(query.value)

    // 处理Neo4j查询结果
    if (response.data && response.data.results) {
      const rows = []
      const columns = new Set()

      // 如果是返回整个节点的查询
      if (response.data.results.length > 0 &&
          response.data.results[0].length === 1 &&
          typeof response.data.results[0][0] === 'object' &&
          response.data.results[0][0]?.properties) {

        response.data.results.forEach(row => {
          if (row[0] && row[0].properties) {
            const nodeData = {
              ...row[0].properties,
              id: row[0].identity ? row[0].identity.toString() : 'unknown',
              labels: JSON.stringify(row[0].labels || [])
            }

            // 收集所有可能的列
            Object.keys(nodeData).forEach(key => columns.add(key))

            rows.push(nodeData)
          }
        })
      } else {
        // 处理返回特定属性的查询结果
        response.data.metadata.forEach(meta => {
          if (meta && meta.name) {
            columns.add(meta.name)
          }
        })

        response.data.results.forEach(row => {
          const rowData = {}
          row.forEach((value, index) => {
            if (response.data.metadata[index] && response.data.metadata[index].name) {
              const colName = response.data.metadata[index].name
              // 如果值是对象或数组，转换为JSON字符串
              if (typeof value === 'object' && value !== null) {
                rowData[colName] = JSON.stringify(value)
              } else {
                rowData[colName] = value
              }
            }
          })
          rows.push(rowData)
        })
      }

      const result = {
        columns: Array.from(columns),
        rows: rows
      }

      // 调用回调函数，传递查询结果
      props.onResult(result)
      ElMessage.success('查询执行成功')
    } else {
      // 没有数据
      props.onResult({ columns: [], rows: [] })
      ElMessage.info('查询执行成功，但没有返回数据')
    }
  } catch (error) {
    console.error('查询执行失败:', error)
    const detail = error.response?.data?.detail
    ElMessage.error('查询执行失败: ' + (detail || error.message))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.cypher-editor {
  margin-bottom: 20px;
}

.examples {
  margin-top: 15px;
  background-color: #f9f9f9;
  padding: 10px;
  border-radius: 4px;
}

.example-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 15px;
  margin-top: 10px;
}

.example-item {
  border: 1px solid #eaeaea;
  border-radius: 4px;
  padding: 10px;
  background-color: white;
}

.example-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.example-title {
  font-weight: bold;
}

.example-query {
  background-color: #f5f7fa;
  padding: 8px;
  border-radius: 4px;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 120px;
  overflow-y: auto;
}

.example-description {
  margin-top: 10px;
  font-size: 12px;
  color: #666;
}
</style> 