// api/db.js
import api from './index'

// 获取数据库表列表
export function getTables() {
  return api.get('/db/tables')
}

// 获取表结构
export function getTableStructure(tableName) {
  return api.get(`/db/table/${tableName}`)
}

// 执行SQL查询
export function executeQuery(sqlQuery) {
  return api.post('/db/query', { query: sqlQuery })
}

// 其他数据库相关请求...