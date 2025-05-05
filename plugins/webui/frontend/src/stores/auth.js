// store/modules/auth.js
import { defineStore } from 'pinia'
import { login, logout, getUserInfo } from '@/api/auth'
import { ElMessage } from 'element-plus'
import router from '@/router'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: JSON.parse(localStorage.getItem('user')) || null
  }),

  getters: {
    isAuthenticated: (state) => !!state.token,
    username: (state) => state.user?.username
  },

  actions: {
    async login(username, password) {
      try {
        console.log('尝试登录:', username)
        const response = await login(username, password)
        console.log('登录响应:', response)

        // 根据FastAPI OAuth2标准响应格式获取token
        const token = response.data.access_token
        if (!token) {
          throw new Error('响应中没有找到访问令牌')
        }

        this.token = token
        localStorage.setItem('token', token)
        await this.fetchUserInfo()
        return true
      } catch (error) {
        console.error('登录错误:', error)
        this.resetAuth()
        throw error
      }
    },

    async fetchUserInfo() {
      if (!this.token) return null

      try {
        const response = await getUserInfo()
        this.user = response.data
        localStorage.setItem('user', JSON.stringify(response.data))
        return this.user
      } catch (error) {
        ElMessage.error('获取用户信息失败: ' + error.message)
        this.resetAuth()
        throw error
      }
    },

    async logout() {
      try {
        await logout()
      } finally {
        this.resetAuth()
        router.push('/login')
      }
    },

    resetAuth() {
      this.token = ''
      this.user = null
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    }
  }
})