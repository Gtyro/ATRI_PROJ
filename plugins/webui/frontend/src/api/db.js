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

// 添加新记录
export function addRecord(tableName, data) {
  return axios.post(`/db/table/${tableName}`, data)
}

// 更新记录
export function updateRecord(tableName, id, data) {
  return axios.put(`/db/table/${tableName}/update?id=${encodeURIComponent(id)}`, data)
}

// 删除记录
export function deleteRecord(tableName, id) {
  return axios.delete(`/db/table/${tableName}/delete?id=${encodeURIComponent(id)}`)
}

// 获取认知节点数据
export function getCognitiveNodes(convId = '', limit = 50) {
  let url = '/db/memory/nodes';
  const params = new URLSearchParams();
  
  if (convId) {
    params.append('conv_id', convId);
  }
  
  if (limit) {
    params.append('limit', limit);
  }
  
  const queryString = params.toString();
  if (queryString) {
    url += `?${queryString}`;
  }
  
  return axios.get(url);
}

// 获取节点关联数据
export function getAssociations(convId = '', nodeIds = null, limit = 200) {
  let url = '/db/memory/associations';
  const params = new URLSearchParams();
  
  if (convId) {
    params.append('conv_id', convId);
  }
  
  if (nodeIds) {
    params.append('node_ids', nodeIds);
  }
  
  if (limit) {
    params.append('limit', limit);
  }
  
  const queryString = params.toString();
  if (queryString) {
    url += `?${queryString}`;
  }
  
  return axios.get(url);
}

// 获取所有可用的会话ID
export function getConversations() {
  return axios.get('/db/memory/conversations');
} 