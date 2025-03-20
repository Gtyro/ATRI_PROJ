// 创建Vue应用
console.log("正在加载Vue应用...");

// 导入element-plus图标
const ElementPlusIconsVue = window["@element-plus/icons-vue"];

const { createApp, ref, reactive, onMounted, watch } = Vue;

const app = createApp({
    setup() {
        console.log("Vue组件开始初始化...");
        // 认证状态
        const isAuthenticated = ref(false);
        const token = ref('');
        const currentUser = ref({});
        const loading = ref(false);
        const currentPage = ref('dashboard');
        const loginError = ref(''); // 登录错误信息
        
        // 登录表单
        const loginForm = reactive({
            username: 'admin',  // 默认填写admin便于用户登录
            password: ''
        });

        // 修改密码表单
        const passwordDialogVisible = ref(false);
        const passwordLoading = ref(false);
        const passwordForm = reactive({
            oldPassword: '',
            newPassword: '',
            confirmPassword: ''
        });

        // 数据
        const botStatus = ref({});
        const pluginsInfo = ref({});
        const statsDays = ref(7);
        const dbQuery = ref('SELECT * FROM users LIMIT 10');
        const queryResult = ref(null);
        const queryLoading = ref(false);
        const dbSchema = ref(null);

        // 检查是否已登录
        const checkAuth = () => {
            console.log("检查认证状态...");
            const savedToken = localStorage.getItem('token');
            if (savedToken) {
                token.value = savedToken;
                isAuthenticated.value = true;
                getUserInfo();
                return true;
            }
            return false;
        };

        // 设置axios默认配置
        const setupAxios = () => {
            console.log("配置Axios...");
            axios.defaults.baseURL = window.location.origin;
            axios.interceptors.request.use(config => {
                if (token.value) {
                    config.headers.Authorization = `Bearer ${token.value}`;
                }
                return config;
            });

            axios.interceptors.response.use(
                response => response,
                error => {
                    console.error("请求错误:", error);
                    if (error.response && error.response.status === 401) {
                        logout();
                    }
                    return Promise.reject(error);
                }
            );
        };

        // 登录方法
        const login = async () => {
            // 清除之前的错误
            loginError.value = '';
            
            // 检查输入
            if (!loginForm.username || !loginForm.password) {
                loginError.value = '请输入用户名和密码';
                return;
            }
            
            try {
                console.log("尝试登录...", loginForm);
                loading.value = true;
                const params = new URLSearchParams();
                params.append('username', loginForm.username);
                params.append('password', loginForm.password);

                console.log("发送登录请求...");
                const response = await axios.post('/api/webui/token', params, {
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded'
                    }
                });

                console.log("登录成功，获取到token", response.data);
                token.value = response.data.access_token;
                localStorage.setItem('token', token.value);
                isAuthenticated.value = true;
                
                // 获取用户信息
                await getUserInfo();
                
                // 加载初始数据
                await loadInitialData();
            } catch (error) {
                console.error("登录失败:", error);
                loginError.value = error.response?.data?.detail || "用户名或密码错误";
            } finally {
                loading.value = false;
            }
        };

        // 退出登录
        const logout = () => {
            console.log("退出登录");
            token.value = '';
            localStorage.removeItem('token');
            isAuthenticated.value = false;
            currentUser.value = {};
        };

        // 获取用户信息
        const getUserInfo = async () => {
            try {
                console.log("获取用户信息...");
                const response = await axios.get('/api/webui/users/me');
                currentUser.value = response.data;
                console.log("获取到用户信息:", currentUser.value);
            } catch (error) {
                console.error('获取用户信息错误:', error);
            }
        };

        // 加载初始数据
        const loadInitialData = async () => {
            try {
                console.log("正在加载初始数据...");
                await Promise.all([
                    refreshBotStatus(),
                    getPlugins(),
                    getStats(),
                    getDbSchema()
                ]);
                setTimeout(() => {
                    initDashboardChart();
                }, 500);
            } catch (error) {
                console.error('加载初始数据错误:', error);
            }
        };

        // 修改密码
        const changePassword = async () => {
            if (passwordForm.newPassword !== passwordForm.confirmPassword) {
                alert('两次输入的密码不一致');
                return;
            }

            try {
                passwordLoading.value = true;
                const response = await axios.post('/api/webui/users/change-password', null, {
                    params: {
                        old_password: passwordForm.oldPassword,
                        new_password: passwordForm.newPassword
                    }
                });

                if (response.data.code === 200) {
                    alert('密码修改成功');
                    passwordDialogVisible.value = false;
                    // 重置表单
                    passwordForm.oldPassword = '';
                    passwordForm.newPassword = '';
                    passwordForm.confirmPassword = '';
                } else {
                    alert(response.data.message || '修改失败');
                }
            } catch (error) {
                alert('修改密码失败: ' + (error.response?.data?.message || error.message));
            } finally {
                passwordLoading.value = false;
            }
        };

        // 获取机器人状态
        const refreshBotStatus = async () => {
            try {
                console.log("刷新机器人状态...");
                const response = await axios.get('/api/webui/bot/status');
                if (response.data.code === 200) {
                    botStatus.value = response.data.data;
                    console.log("机器人状态:", botStatus.value);
                }
            } catch (error) {
                console.error('获取机器人状态错误:', error);
            }
        };

        // 获取插件列表
        const getPlugins = async () => {
            try {
                console.log("获取插件列表...");
                const response = await axios.get('/api/webui/plugins');
                if (response.data.code === 200) {
                    pluginsInfo.value = response.data.data;
                    console.log("插件列表:", pluginsInfo.value);
                }
            } catch (error) {
                console.error('获取插件列表错误:', error);
            }
        };

        // 获取统计数据
        const getStats = async () => {
            try {
                console.log("获取统计数据...");
                const response = await axios.get('/api/webui/stats', {
                    params: { days: statsDays.value }
                });
                if (response.data.code === 200) {
                    updateStatsChart(response.data.data);
                }
            } catch (error) {
                console.error('获取统计数据错误:', error);
            }
        };

        // 执行数据库查询
        const executeQuery = async () => {
            if (!dbQuery.value.trim()) return;

            try {
                console.log("执行查询:", dbQuery.value);
                queryLoading.value = true;
                const response = await axios.post('/api/webui/database/query', {
                    query: dbQuery.value,
                    params: []
                });
                
                if (response.data.code === 200) {
                    queryResult.value = response.data.data;
                } else {
                    alert(response.data.message);
                }
            } catch (error) {
                alert('查询错误: ' + (error.response?.data?.message || error.message));
            } finally {
                queryLoading.value = false;
            }
        };

        // 获取数据库结构
        const getDbSchema = async () => {
            try {
                console.log("获取数据库结构...");
                const response = await axios.get('/api/webui/database/schema');
                if (response.data.code === 200) {
                    dbSchema.value = response.data.data;
                }
            } catch (error) {
                console.error('获取数据库结构错误:', error);
            }
        };

        // 初始化仪表盘图表
        const initDashboardChart = () => {
            console.log("初始化仪表盘图表...");
            const chartDom = document.getElementById('dashboardChart');
            if (!chartDom) {
                console.error("未找到仪表盘图表DOM元素");
                return;
            }
            
            try {
                const chart = echarts.init(chartDom);
                chart.setOption({
                    title: {
                        text: '最近活动'
                    },
                    tooltip: {
                        trigger: 'axis'
                    },
                    legend: {
                        data: ['消息数', '命令数']
                    },
                    grid: {
                        left: '3%',
                        right: '4%',
                        bottom: '3%',
                        containLabel: true
                    },
                    xAxis: {
                        type: 'category',
                        boundaryGap: false,
                        data: ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
                    },
                    yAxis: {
                        type: 'value'
                    },
                    series: [
                        {
                            name: '消息数',
                            type: 'line',
                            data: [150, 230, 224, 218, 135, 147, 260]
                        },
                        {
                            name: '命令数',
                            type: 'line',
                            data: [50, 80, 77, 101, 42, 35, 85]
                        }
                    ]
                });
                
                window.addEventListener('resize', () => {
                    chart.resize();
                });
            } catch (e) {
                console.error("初始化图表错误:", e);
            }
        };

        // 更新统计图表
        const updateStatsChart = (data) => {
            console.log("更新统计图表...");
            const chartDom = document.getElementById('statsChart');
            if (!chartDom) {
                console.error("未找到统计图表DOM元素");
                return;
            }
            
            try {
                const chart = echarts.init(chartDom);
                const stats = data.stats || [];
                const metrics = data.metrics || [];
                const dates = stats.map(item => item.date);
                
                const series = metrics.map(metric => {
                    return {
                        name: metric,
                        type: 'line',
                        data: stats.map(item => item[metric] || 0)
                    };
                });
                
                chart.setOption({
                    title: {
                        text: '数据统计'
                    },
                    tooltip: {
                        trigger: 'axis'
                    },
                    legend: {
                        data: metrics
                    },
                    grid: {
                        left: '3%',
                        right: '4%',
                        bottom: '3%',
                        containLabel: true
                    },
                    xAxis: {
                        type: 'category',
                        boundaryGap: false,
                        data: dates
                    },
                    yAxis: {
                        type: 'value'
                    },
                    series: series
                });
                
                window.addEventListener('resize', () => {
                    chart.resize();
                });
            } catch (e) {
                console.error("更新图表错误:", e);
            }
        };

        // 处理菜单选择
        const handleSelect = (key) => {
            console.log("菜单选择:", key);
            currentPage.value = key;
            
            // 如果切换到数据统计页面，需要重新渲染图表
            if (key === 'statistics') {
                setTimeout(() => {
                    getStats();
                }, 100);
            }
        };

        // 处理下拉菜单命令
        const handleCommand = (command) => {
            console.log("处理命令:", command);
            if (command === 'logout') {
                logout();
            } else if (command === 'password') {
                passwordDialogVisible.value = true;
            }
        };

        // 页面加载时执行
        onMounted(() => {
            console.log("Vue组件已挂载");
            setupAxios();
            if (checkAuth()) {
                loadInitialData();
            }
        });

        return {
            isAuthenticated,
            loginForm,
            loading,
            loginError,
            currentUser,
            currentPage,
            botStatus,
            pluginsInfo,
            passwordDialogVisible,
            passwordForm,
            passwordLoading,
            statsDays,
            dbQuery,
            queryResult,
            queryLoading,
            dbSchema,
            login,
            logout,
            refreshBotStatus,
            getPlugins,
            handleSelect,
            handleCommand,
            changePassword,
            getStats,
            executeQuery,
            getDbSchema
        };
    }
});

// 注册所有Element Plus图标
try {
    for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
        app.component(key, component);
    }
    console.log("已注册Element Plus图标组件");
} catch (e) {
    console.error("注册图标组件失败:", e);
}

// 挂载Vue应用
try {
    console.log("正在挂载Vue应用...");
    app.mount('#app');
    console.log("Vue应用挂载完成");
} catch (e) {
    console.error("Vue应用挂载失败:", e);
} 