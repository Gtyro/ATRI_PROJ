import axios from 'axios'

// 登录获取令牌
export function login(username, password) {
  // 使用URLSearchParams构建表单数据，这更符合OAuth2的要求
  const params = new URLSearchParams()
  params.append('username', username)
  params.append('password', password)
  params.append('grant_type', 'password') // OAuth2要求
  
  return axios.post('/auth/token', params, { // 没有api前缀，生产环境没有Vite代理重写
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
  return axios.get('/auth/users/me')
} 