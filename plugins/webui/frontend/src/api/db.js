import axios from 'axios'

// === SQL数据库操作 ===

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

// === Neo4j数据库操作 ===

// 执行Neo4j Cypher查询
export function executeCypherQuery(query) {
  return axios.post('/db/neo4j/query', { query })
}

// 获取Neo4j节点模型类型
export function getNodeLabels() {
  const query = "MATCH (n) RETURN DISTINCT labels(n) as labels"
  return executeCypherQuery(query)
}

// === 记忆网络操作 ===

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

// 获取单个认知节点
export function getCognitiveNode(nodeId) {
  return axios.get(`/db/memory/node/${nodeId}`);
}

// 创建认知节点
export function createCognitiveNode(data) {
  return axios.post('/db/memory/node', data);
}

// 更新认知节点
export function updateCognitiveNode(nodeId, data) {
  return axios.put(`/db/memory/node/${nodeId}`, data);
}

// 删除认知节点
export function deleteCognitiveNode(nodeId) {
  return axios.delete(`/db/memory/node/${nodeId}`);
}

// 获取节点关联数据
export function getAssociations(convId = '', nodeIds = null, limit = 200) {
  const url = '/db/memory/associations';
  const data = {
    conv_id: convId,
    limit: limit
  };
  
  if (nodeIds) {
    // 向后兼容，如果 nodeIds 是字符串，则将其转换为数组
    data.node_ids = typeof nodeIds === 'string' ? nodeIds.split(',') : nodeIds;
  }
  
  return axios.post(url, data);
}

// 创建节点关联
export function createAssociation(sourceId, targetId, strength = 1.0) {
  return axios.post('/db/memory/association', {
    source_id: sourceId,
    target_id: targetId,
    strength: strength
  });
}

// 更新节点关联
export function updateAssociation(sourceId, targetId, strength) {
  return axios.put('/db/memory/association', {
    source_id: sourceId,
    target_id: targetId,
    strength: strength
  });
}

// 删除节点关联
export function deleteAssociation(sourceId, targetId) {
  return axios.delete(`/db/memory/association?source_id=${sourceId}&target_id=${targetId}`);
}

// 获取所有可用的会话ID
export function getConversations() {
  return axios.get('/db/memory/conversations');
} 