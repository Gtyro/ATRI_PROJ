# 人格系统 Neo4j 重构说明

本次重构将原人格系统的长期记忆部分（`Memory`、`CognitiveNode`、`Association`模型）从关系型数据库迁移到Neo4j图数据库，同时保留消息队列（`MessageQueue`）在原关系型数据库中。

## 1. 重构目标

- 将图数据（记忆网络）存储在专为图数据设计的Neo4j数据库，提高检索效率
- 保留消息队列（短期记忆）在关系型数据库，方便高频读写操作
- 优化数据模型，降低系统耦合度
- 保持API兼容，减少对上层应用的影响

## 2. 准备工作

### 2.1 安装Neo4j

使用Docker安装Neo4j:

```bash
docker run \
    --name neo4j \
    -p 7474:7474 -p 7687:7687 \
    -e NEO4J_AUTH=neo4j/password \
    -v $HOME/neo4j/data:/data \
    -v $HOME/neo4j/logs:/logs \
    -v $HOME/neo4j/import:/import \
    -v $HOME/neo4j/plugins:/plugins \
    neo4j:4.4
```

### 2.2 安装依赖

安装必要的Python依赖:

```bash
pip install neomodel
```

## 3. 配置说明

在配置文件`data/persona.yaml`中添加Neo4j连接信息:

```yaml
neo4j_config:
  uri: "bolt://localhost:7687"
  user: "neo4j"
  password: "password"
```

可以通过环境变量覆盖:

```bash
export NEO4J_URI="bolt://neo4j-server:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="strong-password"
```

## 4. 数据迁移

使用提供的迁移脚本将数据从现有的关系型数据库迁移到Neo4j:

```bash
python -m plugins.persona.scripts.migrate_to_neo4j
```

迁移过程:
1. 导出现有关系型数据库中的节点、记忆和关联数据
2. 将数据转换为Neo4j格式并导入
3. 建立节点间关系和节点-记忆关系

注意事项:
- 迁移前请确保Neo4j服务可用
- 迁移前建议备份原数据库
- 迁移可能需要较长时间，取决于数据量

## 5. 架构变化

### 5.1 存储层分离

- `message_repository.py`: 处理消息队列存储（关系型数据库）
- `memory_repository.py`: 处理记忆网络存储（Neo4j图数据库）

### 5.2 数据模型调整

- `message_models.py`: 保留MessageQueue的Tortoise ORM模型
- `memory_models.py`: 使用neomodel定义Neo4j图模型

### 5.3 组件适配

- `PersonaSystem`: 统一初始化和协调两个数据库连接
- `ShortTermMemory`: 使用MessageRepository管理短期记忆
- `LongTermMemory`: 使用MemoryRepository管理长期记忆
- `LongTermRetriever`: 优化为使用Neo4j的图查询功能
- `DecayManager`: 适配Neo4j环境的记忆衰减机制

## 6. 优化效果

### 6.1 查询性能改进

- 使用Neo4j的原生图查询能力，实现更高效的记忆检索
- 支持通过节点关联查找间接相关记忆
- 优化记忆模型间的关系表达

### 6.2 系统解耦

- 明确区分短期记忆（消息队列）和长期记忆（记忆网络）的存储
- 每个组件有更清晰的职责边界

## 7. 维护建议

- 定期检查Neo4j数据库状态和日志
- 监控关系型数据库和Neo4j的连接状态
- 根据使用情况调整Neo4j的内存配置

## 8. 已知问题与解决方案

- 两个数据库间的事务一致性：目前处理操作相对独立，但需要注意潜在的一致性问题
- 数据迁移时旧数据格式兼容性：迁移脚本会尽量保留原数据格式，但可能需要手动处理特殊情况 