const Login = {
  template: `
    <div class="login-container">
      <h2 class="login-title">数据库管理面板</h2>
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
            prefix-icon="el-icon-user"
          ></el-input>
        </el-form-item>
        
        <el-form-item label="密码" prop="password">
          <el-input 
            v-model="loginForm.password" 
            type="password" 
            placeholder="请输入密码"
            prefix-icon="el-icon-lock"
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
  `,
  setup() {
    const loginFormRef = Vue.ref(null);
    const loading = Vue.ref(false);
    
    const loginForm = Vue.reactive({
      username: '',
      password: ''
    });
    
    const loginRules = {
      username: [
        { required: true, message: '请输入用户名', trigger: 'blur' }
      ],
      password: [
        { required: true, message: '请输入密码', trigger: 'blur' }
      ]
    };
    
    const submitForm = () => {
      loginFormRef.value.validate((valid) => {
        if (valid) {
          loading.value = true;
          
          auth.login(loginForm.username, loginForm.password)
            .then(() => {
              ElementPlus.ElMessage.success('登录成功');
              router.push('/dashboard');
            })
            .catch(error => {
              ElementPlus.ElMessage.error('登录失败: ' + (error.response?.data?.detail || '用户名或密码错误'));
            })
            .finally(() => {
              loading.value = false;
            });
        }
      });
    };
    
    return {
      loginFormRef,
      loginForm,
      loginRules,
      loading,
      submitForm
    };
  }
}; 