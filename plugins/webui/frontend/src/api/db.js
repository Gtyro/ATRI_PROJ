import axios from 'axios'

// 获取数据库表列表
export function getTables() {
  return axios.get('/db/tables')
}

// 获取表结构
export function getTableStructure(tableName) {
  return axios.get(`/db/table/${tableName}`)
}

// 执行SQL查询
export function executeQuery(query) {
  return axios.post('/db/query', { query })
} 