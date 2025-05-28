import axios from 'axios'

// 获取词云数据
export function getWordCloudData(convId, limit = null, refresh = false) {
  let url = '/api/wordcloud/data';
  const params = new URLSearchParams();

  params.append('conv_id', convId);

  if (limit) {
    params.append('limit', limit);
  }

  if (refresh) {
    params.append('refresh', refresh);
  }

  const queryString = params.toString();
  if (queryString) {
    url += `?${queryString}`;
  }

  return axios.get(url);
}

// 获取历史词云数据
export function getWordCloudHistory(convId, date, hour = null) {
  let url = `/api/wordcloud/history?conv_id=${convId}&date=${date}`;
  
  if (hour !== null) {
    url += `&hour=${hour}`;
  }
  
  return axios.get(url);
}

// 手动生成词云数据
export function generateWordCloud(convId, wordLimit = null, hours = null) {
  let url = '/api/wordcloud/generate';
  const params = new URLSearchParams();
  
  params.append('conv_id', convId);
  
  if (wordLimit) {
    params.append('word_limit', wordLimit);
  }
  
  if (hours) {
    params.append('hours', hours);
  }
  
  const queryString = params.toString();
  if (queryString) {
    url += `?${queryString}`;
  }
  
  return axios.post(url);
}

// 获取所有会话ID
export function getConversations() {
  return axios.get('/api/wordcloud/conversations');
} 