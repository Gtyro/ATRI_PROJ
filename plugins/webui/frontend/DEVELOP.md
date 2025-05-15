## WebUI 前端开发文档 (侧重代码实现)

### 1. 核心文件与结构概览

本项目前端的核心代码均位于 `src/` 目录下。

*   **`main.js`**: 应用的入口文件。它负责：
    *   创建 Vue 应用实例。
    *   引入并注册全局样式 (`style.css`)。
    *   引入根组件 `App.vue`。
    *   设置并使用 Vue Router (来自 `src/router/index.js`)。
    *   设置并使用 Pinia 状态管理 (来自 `src/stores/index.js`)。
    *   引入并配置 Axios 实例 (来自 `src/api/index.js`)，用于后续的 API 调用。
    *   完整引入并注册 Element Plus UI 组件库及其图标。
    *   将 Vue 应用挂载到 `index.html` 中的 `#app` DOM 元素。

*   **`App.vue`**: 应用的根 Vue 组件。
    *   使用 `<RouterView />` 来展示当前路由匹配到的组件。
    *   根据当前路由判断是否为登录页 (`isLoginPage`)，如果是，则显示 "ATRI WebUI" 标题。
    *   包含一些基本的应用容器和头部的样式。

*   **`index.html`**: HTML 入口文件。
    *   设置页面语言为中文 (`lang="zh-CN"`)。
    *   定义了应用的标题 "ATRI WebUI"。
    *   包含一个 `div` 元素 `<div id="app"></div>`，作为 Vue 应用的挂载点。
    *   通过 `<script type="module" src="/src/main.js"></script>` 加载并执行 `main.js`。

### 2. 路由管理 (`src/router/index.js`)

*   使用 `vue-router` 的 `createRouter` 和 `createWebHashHistory` (基于 URL hash 的路由模式)。
*   **路由配置 (`routes`)**:
    *   `/`: 重定向到 `/dashboard`。
    *   `/login`: 对应 `LoginPage.vue` 组件。`meta: { requiresAuth: false }` 表示此页面不需要认证。
    *   `/dashboard`: 对应 `AdminLayout.vue` 组件。`meta: { requiresAuth: true }` 表示此页面及其子路由需要认证。
        *   子路由:
            *   `/dashboard` (空路径): 重定向到 `/dashboard/db-admin`。
            *   `db-admin`: 对应 `DBAdmin.vue` 组件，需要认证。
            *   `memory-admin`: 对应 `MemoryAdmin.vue` 组件，需要认证。
    *   所有视图组件 (`LoginPage`, `AdminLayout`, `DBAdmin`, `MemoryAdmin`) 都通过动态导入 (懒加载) 的方式引入，以优化初始加载性能。
*   **全局前置守卫 (`router.beforeEach`)**:
    *   在每次路由跳转前执行。
    *   从 `authStore` (Pinia store) 获取用户认证状态 (`isAuthenticated`)。
    *   检查目标路由 (`to`) 是否需要认证 (`requiresAuth`)。
    *   **逻辑**:
        *   如果路由需要认证但用户未认证，则重定向到 `/login`。
        *   如果用户已认证但尝试访问 `/login` 页面，则重定向到 `/dashboard`。
        *   其他情况允许正常跳转。

### 3. 状态管理 (`src/stores/`)

使用 Pinia进行状态管理。

*   **`src/stores/index.js`**:
    *   创建并导出一个 Pinia 实例 (`pinia`)，该实例会在 `main.js` 中被 Vue 应用使用。

*   **`src/stores/auth.js`**: (Store ID: `auth`)
    *   管理用户认证相关状态和操作。
    *   **State**:
        *   `token`: 存储用户认证令牌，从 `localStorage` 初始化。
        *   `user`: 存储用户信息对象，从 `localStorage` 初始化。
    *   **Getters**:
        *   `isAuthenticated`: 计算属性，根据 `token` 是否存在判断用户是否已认证。
        *   `username`: 计算属性，获取当前用户的用户名。
    *   **Actions**:
        *   `login(username, password)`:
            *   调用 `api/auth.js` 中的 `login` 方法发送登录请求。
            *   成功后，将获取到的 `access_token` 存入 `state.token` 和 `localStorage`。
            *   调用 `fetchUserInfo` 获取并存储用户信息。
            *   处理登录错误，并在失败时重置认证状态。
        *   `fetchUserInfo()`:
            *   如果 `token` 存在，则调用 `api/auth.js` 中的 `getUserInfo` 方法获取用户信息。
            *   将获取到的用户信息存入 `state.user` 和 `localStorage`。
            *   处理获取用户信息失败的情况，并重置认证状态。
        *   `logout()`:
            *   调用 `api/auth.js` 中的 `logout` 方法 (当前实现仅为客户端清理)。
            *   调用 `resetAuth` 清理认证状态。
            *   跳转到 `/login` 页面。
        *   `resetAuth()`:
            *   清空 `state.token` 和 `state.user`。
            *   从 `localStorage` 中移除 `token` 和 `user`。

*   **`src/stores/db.js`**: (Store ID: `db`)
    *   管理数据库（SQL 和 Neo4j）及记忆网络相关的数据和操作。
    *   **State**:
        *   `sqlTables`: 存储 SQL 数据表的列表。
        *   `currentTable`: 当前选中的 SQL 数据表名。
        *   `tableStructure`: 当前 SQL 数据表的结构信息。
        *   `queryResult`: SQL 查询结果，包含 `columns` 和 `rows`。
        *   `nodeLabels`: Neo4j 节点标签列表。
        *   `currentNodeLabel`: 当前选中的 Neo4j 节点标签。
        *   `cypherResult`: Cypher 查询结果，包含 `results` 和 `metadata`。
        *   `dataSource`: 当前数据源类型，可以是 `'sql'` 或 `'neo4j'`。
        *   `isLoading`: 布尔值，表示是否正在加载数据。
    *   **Actions**:
        *   `setDataSource(source)`: 设置当前数据源。
        *   **SQL 数据库操作**:
            *   `fetchTables()`: 调用 `api/db.js` 的 `getTables` 获取 SQL 表列表。
            *   `fetchTableStructure(tableName)`: 调用 `api/db.js` 的 `getTableStructure` 获取指定表的结构。
            *   `executeQuery(sqlQuery)`: 调用 `api/db.js` 的 `executeQuery` 执行 SQL 查询。
        *   **Neo4j 数据库操作**:
            *   `fetchNodeLabels()`: 调用 `api/db.js` 的 `getNodeLabels` 获取 Neo4j 节点标签。
            *   `executeCypherQuery(cypherQuery)`: 调用 `api/db.js` 的 `executeCypherQuery` 执行 Cypher 查询。
        *   `getAllDataSources()`: 合并获取 SQL 表和 Neo4j 节点标签，作为统一的数据源列表。

### 4. API 请求封装 (`src/api/`)

所有与后端 API 的交互都封装在此目录下。

*   **`src/api/index.js`**:
    *   创建并配置一个全局的 Axios 实例 (`service`)。
    *   **Base URL**: 设置为空字符串 (`''`)，意味着 API 请求路径是相对路径。这通常与 Vite 的开发服务器代理配置 (`vite.config.js` 中的 `server.proxy`) 结合使用，在开发时将特定前缀的请求代理到后端服务器。在生产环境中，这些请求会相对于当前域名发出。
    *   **Timeout**: 设置请求超时时间为 5000ms。
    *   **请求拦截器 (`service.interceptors.request`)**:
        *   在每个请求发送前执行。
        *   从 `localStorage` 获取 `token`。
        *   如果 `token` 存在，则将其以 `Bearer ${token}` 的形式添加到请求头的 `Authorization` 字段。
    *   **响应拦截器 (`service.interceptors.response`)**:
        *   在接收到响应后执行。
        *   如果发生 401 未授权错误 (通常表示 token 无效或过期)，则从 `localStorage` 中移除 `token` 和 `user`，引导用户重新登录。
    *   该文件还通过修改 `axios.defaults` 和 `axios.interceptors` 将此 `service` 实例的配置应用到全局 `axios` 对象，这意味着项目中直接使用 `import axios from 'axios'` 也会获得相同的拦截器和默认配置。

*   **`src/api/auth.js`**:
    *   封装认证相关的 API 调用。
    *   `login(username, password)`:
        *   向 `/auth/token` (实际请求路径，会经过 Vite proxy 或直接访问生产环境的 `/auth/token`) 发送 POST 请求以获取认证令牌。
        *   请求体使用 `application/x-www-form-urlencoded` 格式，包含 `username`, `password`, 和 `grant_type: 'password'` (符合 OAuth2 规范)。
    *   `logout()`: 目前此函数返回一个 resolved Promise，表示主要在客户端进行登出处理 (如清理 token)。实际项目中可能也需要调用后端登出接口。
    *   `getUserInfo()`: 向 `/auth/users/me` 发送 GET 请求以获取当前登录用户的信息。

*   **`src/api/db.js`**:
    *   封装与数据库和记忆网络相关的 API 调用。所有请求路径都以 `/db/` 开头。
    *   **SQL 数据库操作**:
        *   `getTables()`: GET `/db/tables` - 获取所有 SQL 表。
        *   `getTableStructure(tableName)`: GET `/db/table/{tableName}` - 获取指定 SQL 表的结构。
        *   `executeQuery(query)`: POST `/db/query` - 执行 SQL 查询，请求体为 `{ query: "SELECT ..." }`。
        *   `addRecord(tableName, data)`: POST `/db/table/{tableName}` - 向指定表添加新记录。
        *   `updateRecord(tableName, id, data)`: PUT `/db/table/{tableName}/update?id={id}` - 更新指定表中的记录。
        *   `deleteRecord(tableName, id)`: DELETE `/db/table/{tableName}/delete?id={id}` - 删除指定表中的记录。
    *   **Neo4j 数据库操作**:
        *   `executeCypherQuery(query)`: POST `/db/neo4j/query` - 执行 Cypher 查询，请求体为 `{ query: "MATCH ..." }`。
        *   `getNodeLabels()`: 内部调用 `executeCypherQuery` 执行 `MATCH (n) RETURN DISTINCT labels(n) as labels` 来获取所有节点标签。
    *   **记忆网络操作**:
        *   `getCognitiveNodes(convId, limit)`: GET `/db/memory/nodes` - 获取认知节点，可选参数 `conv_id` 和 `limit`。
        *   `getCognitiveNode(nodeId)`: GET `/db/memory/node/{nodeId}` - 获取单个认知节点。
        *   `createCognitiveNode(data)`: POST `/db/memory/node` - 创建认知节点。
        *   `updateCognitiveNode(nodeId, data)`: PUT `/db/memory/node/{nodeId}` - 更新认知节点。
        *   `deleteCognitiveNode(nodeId)`: DELETE `/db/memory/node/{nodeId}` - 删除认知节点。
        *   `getAssociations(convId, nodeIds, limit)`: GET `/db/memory/associations` - 获取节点关联，可选参数 `conv_id`, `node_ids`, `limit`。
        *   `createAssociation(sourceId, targetId, strength)`: POST `/db/memory/association` - 创建节点关联。
        *   `updateAssociation(sourceId, targetId, strength)`: PUT `/db/memory/association` - 更新节点关联。
        *   `deleteAssociation(sourceId, targetId)`: DELETE `/db/memory/association?source_id={sourceId}&target_id={targetId}` - 删除节点关联。
        *   `getConversations()`: GET `/db/memory/conversations` - 获取所有可用的会话 ID。

### 5. UI 组件 (`src/components/`)

此目录存放可复用的 Vue 组件。

*   **`NavbarHeader.vue`**: (推测) 应用的导航栏/头部组件，可能包含用户登出按钮、导航链接等。
*   **`DataTable.vue`**: (推测) 一个通用的数据表格组件，用于展示行列数据，可能基于 Element Plus 的 Table 组件封装。
*   **`SqlEditor.vue`**: (推测) SQL 查询编辑器组件，可能集成了代码编辑功能，用于输入和编辑 SQL 语句。
*   **`CypherEditor.vue`**: (推测) Cypher 查询编辑器组件，类似于 `SqlEditor.vue`，但用于 Neo4j 的 Cypher 查询语言。
*   **`TableManager.vue`**: (推测) 一个更复杂的组件，用于管理数据表，可能集成了表的展示、记录的增删改查、以及与 `SqlEditor.vue` 或 `DataTable.vue` 的交互。

### 6. 页面级视图 (`src/views/`)

此目录存放构成应用不同页面的 Vue 组件，通常与路由配置相对应。

*   **`LoginPage.vue`**: 登录页面组件。
    *   包含用户名和密码输入框，以及登录按钮。
    *   点击登录按钮时，会调用 `authStore` 的 `login` action。
    *   登录成功后，会通过路由守卫自动跳转到仪表盘页面。
    *   登录失败会显示错误提示。
*   **`AdminLayout.vue`**: 管理界面的主布局组件。
    *   通常包含一个侧边栏导航和主内容区域 (`<RouterView />`)。
    *   侧边栏可能包含指向 `DBAdmin.vue` 和 `MemoryAdmin.vue` 的链接。
    *   可能包含 `NavbarHeader.vue` 组件。
*   **`DBAdmin.vue`**: 数据库管理页面。
    *   (推测) 允许用户选择 SQL 表或 Neo4j 节点标签。
    *   提供查询界面 (可能使用 `SqlEditor.vue` 和 `CypherEditor.vue`)。
    *   展示查询结果 (可能使用 `DataTable.vue`)。
    *   可能提供对 SQL 表数据的增删改查功能 (可能使用 `TableManager.vue`)。
    *   与 `dbStore` 交互以获取数据和执行操作。
*   **`MemoryAdmin.vue`**: 记忆网络管理页面。
    *   (推测) 用于可视化和管理认知节点及其关联。
    *   可能包含节点和边的创建、编辑、删除功能。
    *   可能使用 ECharts 或其他图表库进行网络可视化。
    *   与 `dbStore` (特别是记忆网络相关的 actions) 和 `api/db.js` (记忆网络 API) 交互。
