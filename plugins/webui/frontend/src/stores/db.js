// store/modules/db.js
import { defineStore } from 'pinia'
import { getTables, getTableStructure, executeQuery } from '@/api/db'

export const useDbStore = defineStore('db', {
  state: () => ({
    tables: [],
    currentTable: null,
    tableStructure: null,
    queryResult: { columns: [], rows: [] },
    isLoading: false
  }),

  actions: {
    async fetchTables() {
      this.isLoading = true
      try {
        const response = await getTables()
        this.tables = response.data.tables
        return this.tables
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
    }
  }
})