// store/modules/db.js
import { defineStore } from 'pinia'
import {
  getTables, getTableStructure, executeQuery,
  executeCypherQuery, getNodeLabels
} from '@/api/db'

export const useDbStore = defineStore('db', {
  state: () => ({
    // SQL数据相关
    sqlTables: [],
    currentTable: null,
    tableStructure: null,
    queryResult: { columns: [], rows: [] },

    // Neo4j数据相关
    nodeLabels: [],
    currentNodeLabel: null,
    cypherResult: { results: [], metadata: [] },

    // 通用状态
    dataSource: 'sql', // 'sql' 或 'neo4j'
    isLoading: false
  }),

  actions: {
    // 设置当前数据源
    setDataSource(source) {
      this.dataSource = source
    },

    // === SQL数据库操作 ===

    async fetchTables() {
      this.isLoading = true
      try {
        const response = await getTables()
        this.sqlTables = response.data.tables
        return this.sqlTables
      } catch (error) {
        throw error
      } finally {
        this.isLoading = false
      }
    },

    async fetchTableStructure(tableName) {
      this.isLoading = true
      try {
        const response = await getTableStructure(tableName)
        this.currentTable = tableName
        this.tableStructure = response.data
        return this.tableStructure
      } catch (error) {
        throw error
      } finally {
        this.isLoading = false
      }
    },

    async executeQuery(sqlQuery) {
      this.isLoading = true
      try {
        const response = await executeQuery(sqlQuery)
        this.queryResult = {
          columns: response.data.columns || [],
          rows: response.data.rows || []
        }
        return this.queryResult
      } catch (error) {
        throw error
      } finally {
        this.isLoading = false
      }
    },

    // === Neo4j数据库操作 ===

    async fetchNodeLabels() {
      this.isLoading = true
      try {
        const response = await getNodeLabels()
        // 处理标签数据，从格式化的结果中提取标签名
        const labels = []
        if (response.data && response.data.results) {
          response.data.results.forEach(row => {
            if (row[0] && Array.isArray(row[0])) {
              row[0].forEach(label => {
                if (!labels.includes(label)) {
                  labels.push(label)
                }
              })
            }
          })
        }
        this.nodeLabels = labels
        return this.nodeLabels
      } catch (error) {
        throw error
      } finally {
        this.isLoading = false
      }
    },

    async executeCypherQuery(cypherQuery) {
      this.isLoading = true
      try {
        const response = await executeCypherQuery(cypherQuery)
        this.cypherResult = {
          results: response.data.results || [],
          metadata: response.data.metadata || []
        }
        return this.cypherResult
      } catch (error) {
        throw error
      } finally {
        this.isLoading = false
      }
    },

    // 获取所有可用数据源（合并SQL表和Neo4j节点标签）
    async getAllDataSources() {
      // 获取SQL表
      await this.fetchTables()

      // 获取Neo4j节点标签
      await this.fetchNodeLabels()

      // 返回合并后的数据源列表，带有类型标识
      return {
        sql: this.sqlTables.map(table => ({ name: table, type: 'sql' })),
        neo4j: this.nodeLabels.map(label => ({ name: label, type: 'neo4j' }))
      }
    }
  }
})