import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import router from './router'
import pinia from './stores'
import './api/index.js'  // 引入axios配置

// 引入Element Plus
import 'element-plus/dist/index.css'

// 导入Element Plus
import ElementPlus from 'element-plus'

// 导入Element Plus图标
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

const app = createApp(App)
app.use(pinia)
app.use(router)

// 注册所有图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(ElementPlus, { size: 'default' })
app.mount('#app')
