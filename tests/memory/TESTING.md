# 记忆系统测试指南

本文档提供了如何测试记忆系统和查看memory.db数据库内容的详细说明。

## 测试文件

本插件包含两个测试相关的文件：

1. `test_memory_db.py` - 创建测试数据库并运行单元测试
2. `show_memory_db.py` - 直接查看实际使用中的memory.db内容

## 运行单元测试

单元测试会创建一个临时测试数据库，填充测试数据，然后进行各种功能测试。这不会影响实际使用的数据库。

运行方法：

```bash
# 在插件目录下执行
python test_memory_db.py
```

这将运行所有测试用例，并显示测试数据库的内容，包括：
- 数据库表结构
- 记忆内容
- 用户记忆
- 上下文记忆
- 记忆关联
- 消息队列
- 记忆标签

测试完成后，临时测试数据库会被自动删除。

## 查看实际数据库内容

使用`show_memory_db.py`工具可以直接查看实际使用中的memory.db数据库内容，方便调试和监控。

基本使用：

```bash
# 查看默认数据库(data/memory.db)的所有内容
python show_memory_db.py

# 指定数据库路径
python show_memory_db.py --db /path/to/memory.db
```

### 命令行选项

该工具提供了多种命令行选项，用于查看不同类型的信息：

```
--db DB            指定数据库路径 (默认: data/memory.db)
--user USER        查看指定用户的记忆
--context CONTEXT  查看指定上下文的记忆
--limit LIMIT      显示记录的数量限制 (默认: 10)
--summary          只显示摘要信息
--all              显示所有内容
--structure        只显示数据库结构
--memories         只显示记忆内容
--queue            只显示消息队列
--tags             只显示标签信息
```

### 使用示例

1. 只查看数据库结构：
   ```bash
   python show_memory_db.py --structure
   ```

2. 查看最新的记忆内容：
   ```bash
   python show_memory_db.py --memories
   ```

3. 查看特定用户的记忆：
   ```bash
   python show_memory_db.py --user 123456789
   ```

4. 查看特定群聊的记忆：
   ```bash
   python show_memory_db.py --context group_123456789
   ```

5. 查看消息队列状态：
   ```bash
   python show_memory_db.py --queue
   ```

6. 查看热门标签：
   ```bash
   python show_memory_db.py --tags
   ```

7. 显示更多记录：
   ```bash
   python show_memory_db.py --memories --limit 20
   ```

## 注意事项

1. 确保运行测试时有适当的文件读写权限
2. 单元测试不会修改实际的数据库，但查看工具会直接读取实际数据库
3. 对于生产环境，建议先备份数据库再运行查看工具
4. 如果数据库很大，可以使用`--limit`选项限制显示的记录数量

## 故障排除

1. 如果出现"数据库文件不存在"错误，检查数据库路径是否正确
2. 如果显示的数据不完整，可能是因为某些记录被删除或数据库损坏
3. 如果测试运行缓慢，可能是因为数据库较大，尝试减小`--limit`值 