import axios from 'axios'

// 获取记忆时间线数据
export function getMemoryTimeline(convId = '', startTime = null, endTime = null, limit = 100) {
  const url = '/api/memory/timeline';
  const params = {};
  
  if (convId) {
    params.conv_id = convId;
  }
  
  if (startTime) {
    params.start_time = startTime;
  }
  
  if (endTime) {
    params.end_time = endTime;
  }
  
  params.limit = limit;
  
  return axios.get(url, { params });
}

// 获取记忆详情
export function getMemoryDetail(memoryId) {
  return axios.get(`/api/memory/detail/${memoryId}`);
}

// 获取记忆统计数据
export function getMemoryStats(convId = '') {
  const params = convId ? { conv_id: convId } : {};
  return axios.get('/api/memory/stats', { params });
}

// 使用现有的会话API，重用db.js中的getConversations方法
export { getConversations } from './db'; 