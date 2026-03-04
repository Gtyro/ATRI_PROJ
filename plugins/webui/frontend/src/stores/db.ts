import { defineStore } from "pinia";

import {
  executeCypherQuery,
  executeQuery,
  getNodeLabels,
  getTableStructure,
  getTables,
} from "@/api/db";

interface QueryResult {
  columns: string[];
  rows: unknown[];
}

interface CypherResult {
  results: unknown[][];
  metadata: unknown[];
}

type DataSourceType = "sql" | "neo4j";

interface DbState {
  sqlTables: string[];
  currentTable: string | null;
  tableStructure: Record<string, unknown> | null;
  queryResult: QueryResult;
  nodeLabels: string[];
  currentNodeLabel: string | null;
  cypherResult: CypherResult;
  dataSource: DataSourceType;
  isLoading: boolean;
}

export const useDbStore = defineStore("db", {
  state: (): DbState => ({
    sqlTables: [],
    currentTable: null,
    tableStructure: null,
    queryResult: { columns: [], rows: [] },
    nodeLabels: [],
    currentNodeLabel: null,
    cypherResult: { results: [], metadata: [] },
    dataSource: "sql",
    isLoading: false,
  }),

  actions: {
    setDataSource(source: DataSourceType): void {
      this.dataSource = source;
    },

    async fetchTables(): Promise<string[]> {
      this.isLoading = true;
      try {
        const response = await getTables();
        this.sqlTables = Array.isArray(response.data?.tables)
          ? response.data.tables
          : [];
        return this.sqlTables;
      } finally {
        this.isLoading = false;
      }
    },

    async fetchTableStructure(
      tableName: string,
    ): Promise<Record<string, unknown> | null> {
      this.isLoading = true;
      try {
        const response = await getTableStructure(tableName);
        this.currentTable = tableName;
        this.tableStructure =
          response.data && typeof response.data === "object"
            ? response.data
            : null;
        return this.tableStructure;
      } finally {
        this.isLoading = false;
      }
    },

    async executeQuery(sqlQuery: string): Promise<QueryResult> {
      this.isLoading = true;
      try {
        const response = await executeQuery(sqlQuery);
        this.queryResult = {
          columns: Array.isArray(response.data?.columns)
            ? response.data.columns
            : [],
          rows: Array.isArray(response.data?.rows) ? response.data.rows : [],
        };
        return this.queryResult;
      } finally {
        this.isLoading = false;
      }
    },

    async fetchNodeLabels(): Promise<string[]> {
      this.isLoading = true;
      try {
        const response = await getNodeLabels();
        const labels = new Set<string>();
        const rows = Array.isArray(response.data?.results)
          ? response.data.results
          : [];

        rows.forEach((row: unknown) => {
          if (!Array.isArray(row) || !Array.isArray(row[0])) {
            return;
          }
          row[0].forEach((label: unknown) => {
            if (typeof label === "string" && label) {
              labels.add(label);
            }
          });
        });

        this.nodeLabels = Array.from(labels);
        return this.nodeLabels;
      } finally {
        this.isLoading = false;
      }
    },

    async executeCypherQuery(cypherQuery: string): Promise<CypherResult> {
      this.isLoading = true;
      try {
        const response = await executeCypherQuery(cypherQuery);
        this.cypherResult = {
          results: Array.isArray(response.data?.results)
            ? response.data.results
            : [],
          metadata: Array.isArray(response.data?.metadata)
            ? response.data.metadata
            : [],
        };
        return this.cypherResult;
      } finally {
        this.isLoading = false;
      }
    },

    async getAllDataSources(): Promise<{
      sql: Array<{ name: string; type: "sql" }>;
      neo4j: Array<{ name: string; type: "neo4j" }>;
    }> {
      await this.fetchTables();
      await this.fetchNodeLabels();

      return {
        sql: this.sqlTables.map((table) => ({ name: table, type: "sql" })),
        neo4j: this.nodeLabels.map((label) => ({ name: label, type: "neo4j" })),
      };
    },
  },
});
