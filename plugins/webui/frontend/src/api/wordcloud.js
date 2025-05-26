import axios from 'axios'

// 获取词云数据
export function getWordCloudData(limit = null, refresh = false) {
  let url = '/api/wordcloud/data';
  const params = new URLSearchParams();

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
export function getWordCloudHistory(date, hour = null) {
  let url = `/api/wordcloud/history?date=${date}`;
  
  if (hour !== null) {
    url += `&hour=${hour}`;
  }
  
  return axios.get(url);
}

// 手动生成词云数据
export function generateWordCloud(wordLimit = null, hours = null) {
  let url = '/api/wordcloud/generate';
  const params = new URLSearchParams();
  
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