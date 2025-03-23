import axios from 'axios'

// 创建axios实例
const service = axios.create({
  baseURL: '',  // 使用相对路径，配合vite的proxy
  timeout: 5000
})

// 请求拦截器
service.interceptors.request.use(
  config => {
    // 获取token并添加到请求头
    const token = localStorage.getItem('token')
    if (token) {
      // 确保使用Bearer格式
      config.headers['Authorization'] = `Bearer ${token}`
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器
service.interceptors.response.use(
  response => {
    return response
  },
  error => {
    // 401错误可能是token过期，清除token
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    }
    return Promise.reject(error)
  }
)

// 替换全局的axios默认值
axios.defaults.baseURL = service.defaults.baseURL
axios.defaults.timeout = service.defaults.timeout
Object.keys(service.interceptors).forEach(type => {
  axios.interceptors[type].handlers = service.interceptors[type].handlers
})

export default service 