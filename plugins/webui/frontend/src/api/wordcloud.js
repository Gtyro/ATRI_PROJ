import { request } from './index'

// 获取词云数据
export function getWordCloudData(convId, limit = null, refresh = false) {
  const url = '/api/wordcloud/data';
  const params = {};

  params.conv_id = convId;

  if (limit) {
    params.limit = limit;
  }

  if (refresh) {
    params.refresh = refresh;
  }

  return request.get(url, params);
}

// 获取历史词云数据
export function getWordCloudHistory(convId, date, hour = null) {
  const params = {
    conv_id: convId,
    date: date
  };
  
  if (hour !== null) {
    params.hour = hour;
  }
  
  return request.get('/api/wordcloud/history', params);
}

// 手动生成词云数据
export function generateWordCloud(convId, wordLimit = null, hours = null) {
  const url = '/api/wordcloud/generate';
  const params = {
    conv_id: convId
  };
  
  if (wordLimit) {
    params.word_limit = wordLimit;
  }
  
  if (hours) {
    params.hours = hours;
  }
  
  return request.post(url, null, { params });
}

// 获取所有会话ID
export function getConversations() {
  return request.get('/api/wordcloud/conversations');
} 