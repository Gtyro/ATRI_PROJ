# WebUI 管理面板

这是一个WebUI管理面板，提供了可视化的方式管理和监控您的数据库。

## 特性

- 🔐 **用户认证**: 安全的登录系统，保护您的管理面板
- 📝 **数据库管理**: 直接在网页上执行增删改查，查看数据库结构
- 📱 **响应式设计**: 支持在各种设备上访问管理面板
- 🔧 **模块化结构**: 使用FastAPI的路由系统组织代码，易于扩展和维护

## 安装与启动

### 需求

- Python 3.7+
- 数据库文件位于 `~/ATRI_PROJ/data/persona.db`

### 安装

1. 克隆仓库
2. 安装依赖

```bash
poetry install
```

### 启动

直接运行启动脚本：

```bash
python run.py
```

## 使用方法

1. 启动程序
2. 在浏览器中访问 `http://your-host:port/webui`
   - 默认为 `http://127.0.0.1:8080/webui`
3. 使用默认管理员账户登录:
   - 用户名: `admin`
   - 密码: `admin`
4. 首次登录后，请立即修改默认密码(todo)

## 安全提示

- 请在首次登录后立即修改默认管理员密码
- 生产环境中，请修改 `api/core/config.py` 中的 `SECRET_KEY` 为随机字符串

## 功能模块

### 数据库

- 数据管理: 可以对数据库进行CRUD
- SQL查询: 可以用SQL语句进行自定义查询
- 常用查询: 可以查看一些插件无关信息

## 技术栈

- **后端**: Python + FastAPI + SQLite/PostgreSQL
- **前端**: Vue 3 + Element Plus + ECharts
- **认证**: JWT (使用python-jose)

## 项目结构

```
├── backend/              # 后端代码
│   ├── __init__.py       # Backend package initialization
│   ├── api/              # FastAPI应用和路由
│   │   ├── __init__.py   # API modules initialization
│   │   ├── main.py       # API entry point
│   │   ├── auth/         # Authentication modules
│   │   ├── core/         # Core modules (e.g., config, database)
│   │   └── db/           # Database operations modules
│   ├── init_db.py        # Database initialization script
│   ├── pyproject.toml    # Python dependencies (Poetry)
│   └── test_api.py       # API tests
├── frontend/             # 前端代码 (Vue 3 + Element Plus)
│   ├── public/           # Static assets for frontend
│   ├── src/              # Frontend source code
│   │   ├── assets/       # Assets like images, fonts
│   │   ├── components/   # Vue components
│   │   ├── router/       # Vue router configuration
│   │   ├── stores/       # State management (e.g., Pinia)
│   │   ├── utils/        # Utility functions
│   │   ├── views/        # Vue views/pages
│   │   ├── App.vue       # Main Vue application component
│   │   └── main.js       # Frontend entry point
│   ├── .gitignore        # Git ignore file for frontend
│   ├── index.html        # Main HTML file for frontend SPA
│   ├── package.json      # Frontend dependencies and scripts
│   ├── vite.config.js    # Vite configuration
│   └── README.md         # Frontend specific README (if any)
├── static/               # 静态文件
│   └── webui/            # 静态资源
│       ├── assets/
│       └── index.html
├── __init__.py           # webui插件模块初始化文件
├── todo                  # TODO 任务列表文件
├── .cursorignore         # Cursor ignore file
└── README.md             # 本说明文档
```

## API 文档

启动应用后，可以通过访问 `/docs` 或 `/redoc` 路径查看自动生成的API文档。

## 注意事项

- 统计数据存储在 `~/ATRI_PROJ/data/persona.db` 中
- 默认仅允许管理员用户访问WebUI
