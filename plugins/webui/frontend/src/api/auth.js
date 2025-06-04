import axios from 'axios'
import { request } from './index'

// 登录获取令牌
export function login(username, password) {
  // 使用URLSearchParams构建表单数据，这更符合OAuth2的要求
  const params = new URLSearchParams()
  params.append('username', username)
  params.append('password', password)
  params.append('grant_type', 'password') // OAuth2要求

  // 登录时使用原始axios，因为此时还没有令牌
  return axios.post('/auth/token', params, { 
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    }
  })
}

// 刷新令牌
export function refreshToken(refreshToken) {
  const params = new URLSearchParams()
  params.append('refresh_token', refreshToken)
  params.append('grant_type', 'refresh_token')
  
  // 刷新令牌时使用原始axios，因为此时令牌已经过期
  return axios.post('/auth/token', params, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    }
  })
}

// 退出登录
export function logout() {
  // 这里可能是一个登出API调用，或者只是客户端清理
  return Promise.resolve()
}

// 获取当前用户信息
export function getUserInfo() {
  // 使用封装的request，因为此时应该有有效的令牌
  return request.get('/auth/users/me')
}

// 注册新用户
export function register(userData) {
  // 注册时不需要令牌，但为了一致性使用封装的request
  return request.post('/auth/register', userData)
} 