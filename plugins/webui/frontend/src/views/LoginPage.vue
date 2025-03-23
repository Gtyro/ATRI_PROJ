<template>
  <div class="login-container">
    <h2 class="login-title">ATRI管理面板</h2>
    <el-form 
      :model="loginForm" 
      :rules="loginRules" 
      ref="loginFormRef" 
      label-position="top"
    >
      <el-form-item label="用户名" prop="username">
        <el-input 
          v-model="loginForm.username" 
          placeholder="请输入用户名"
          :prefix-icon="User"
        ></el-input>
      </el-form-item>
      
      <el-form-item label="密码" prop="password">
        <el-input 
          v-model="loginForm.password" 
          type="password" 
          placeholder="请输入密码"
          :prefix-icon="Lock"
          @keyup.enter="submitForm"
        ></el-input>
      </el-form-item>
      
      <el-form-item>
        <el-button 
          type="primary" 
          style="width: 100%;" 
          @click="submitForm" 
          :loading="loading"
        >
          登录
        </el-button>
      </el-form-item>
    </el-form>
    
    <div class="login-tips">
      <p>默认用户名: admin</p>
      <p>默认密码: admin</p>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const loginFormRef = ref(null)
const loading = ref(false)

const loginForm = reactive({
  username: '',
  password: ''
})

const loginRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' }
  ]
}

const submitForm = () => {
  if (!loginFormRef.value) return
  
  loginFormRef.value.validate((valid) => {
    if (valid) {
      loading.value = true
      
      authStore.login(loginForm.username, loginForm.password)
        .then(() => {
          ElMessage.success('登录成功')
          router.push('/dashboard')
        })
        .catch(error => {
          console.error('登录错误:', error)
          if (error.response) {
            const status = error.response.status
            if (status === 401) {
              ElMessage.error('用户名或密码错误')
            } else if (status === 429) {
              ElMessage.error('尝试次数过多，请稍后再试')
            } else {
              ElMessage.error(`登录失败: ${error.response.data?.detail || '服务器错误'}`)
            }
          } else if (error.request) {
            ElMessage.error('无法连接到服务器，请检查网络连接')
          } else {
            ElMessage.error(`登录失败: ${error.message}`)
          }
        })
        .finally(() => {
          loading.value = false
        })
    }
  })
}
</script>

<style scoped>
.login-container {
  width: 400px;
  margin: 100px auto;
  padding: 20px;
  border-radius: 5px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  background-color: #fff;
}

.login-title {
  text-align: center;
  margin-bottom: 20px;
  color: var(--primary-color);
}

.login-tips {
  margin-top: 20px;
  font-size: 14px;
  color: var(--info-color);
}
</style>