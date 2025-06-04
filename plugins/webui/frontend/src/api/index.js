import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

// 是否正在刷新token
let isRefreshing = false
// 请求队列
let requests = []

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
  async error => {
    const originalRequest = error.config
    
    // 如果是401错误且不是刷新token的请求且没有重试过
    if (error.response && error.response.status === 401 && 
        !originalRequest._retry && 
        !originalRequest.url.includes('/auth/refresh-token')) {
      
      if (!isRefreshing) {
        isRefreshing = true
        const authStore = useAuthStore()
        
        try {
          // 尝试刷新token
          await authStore.refreshToken()
          
          // 重新设置token
          originalRequest.headers['Authorization'] = `Bearer ${localStorage.getItem('token')}`
          originalRequest._retry = true
          
          // 执行队列中的请求
          requests.forEach(cb => cb())
          requests = []
          
          // 重新发送原始请求
          return service(originalRequest)
        } catch (refreshError) {
          // 刷新失败，清除token并跳转到登录页
          authStore.resetAuth()
          window.location.href = '/#/login'
          return Promise.reject(refreshError)
        } finally {
          isRefreshing = false
        }
      } else {
        // 正在刷新token，将请求加入队列
        return new Promise(resolve => {
          requests.push(() => {
            originalRequest.headers['Authorization'] = `Bearer ${localStorage.getItem('token')}`
            resolve(service(originalRequest))
          })
        })
      }
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

// API请求方法封装
export const request = {
  get: (url, params, config = {}) => service.get(url, { params, ...config }),
  post: (url, data, config = {}) => service.post(url, data, config),
  put: (url, data, config = {}) => service.put(url, data, config),
  delete: (url, config = {}) => service.delete(url, config)
}

export default service 