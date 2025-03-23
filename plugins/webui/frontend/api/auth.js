// api/auth.js
import api from './index'

// 用户登录
export function login(username, password) {
  const formData = new FormData()
  formData.append('username', username)
  formData.append('password', password)
  return api.post('/auth/token', formData)
}

// 获取用户信息
export function getUserInfo() {
  return api.get('/auth/users/me')
}

// 退出登录
export function logout() {
  return api.post('/auth/logout')
}

// 注册新用户（如果需要）
export function register(userData) {
  return api.post('/auth/register', userData)
}