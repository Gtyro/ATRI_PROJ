const app = Vue.createApp({
  template: `
    <router-view></router-view>
  `
});

// 全局错误处理
app.config.errorHandler = (err, vm, info) => {
  console.error('全局错误:', err);
  ElementPlus.ElMessage.error('发生错误: ' + err.message);
};

// 注册全局组件
app.component('Navbar', Navbar);

// 使用路由
app.use(router);

// 使用Element Plus
app.use(ElementPlus);

// 挂载应用
app.mount('#app'); 