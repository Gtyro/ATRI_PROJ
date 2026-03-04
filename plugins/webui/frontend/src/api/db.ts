import type { AxiosResponse } from "axios";

import { request } from "./index";

export interface SqlTablesPayload {
  tables: string[];
  [key: string]: unknown;
}

export interface SqlQueryPayload {
  columns: string[];
  rows: unknown[];
  [key: string]: unknown;
}

export interface CypherQueryPayload {
  results: unknown[][];
  metadata: unknown[];
  [key: string]: unknown;
}

export interface ConversationRowsPayload {
  rows: string[];
  [key: string]: unknown;
}

export function getTables(): Promise<AxiosResponse<SqlTablesPayload>> {
  return request.get<SqlTablesPayload>("/db/tables");
}

export function getTableStructure(
  tableName: string,
): Promise<AxiosResponse<Record<string, unknown>>> {
  return request.get<Record<string, unknown>>(`/db/table/${tableName}`);
}

export function executeQuery(
  query: string,
): Promise<AxiosResponse<SqlQueryPayload>> {
  return request.post<SqlQueryPayload>("/db/query", { query });
}

export function addRecord(
  tableName: string,
  data: Record<string, unknown>,
): Promise<AxiosResponse<unknown>> {
  return request.post("/db/table/" + tableName, data);
}

export function updateRecord(
  tableName: string,
  id: string | number,
  data: Record<string, unknown>,
): Promise<AxiosResponse<unknown>> {
  return request.put(
    `/db/table/${tableName}/update?id=${encodeURIComponent(String(id))}`,
    data,
  );
}

export function deleteRecord(
  tableName: string,
  id: string | number,
): Promise<AxiosResponse<unknown>> {
  return request.delete(
    `/db/table/${tableName}/delete?id=${encodeURIComponent(String(id))}`,
  );
}

export function executeCypherQuery(
  query: string,
): Promise<AxiosResponse<CypherQueryPayload>> {
  return request.post<CypherQueryPayload>("/db/neo4j/query", { query });
}

export function getNodeLabels(): Promise<AxiosResponse<CypherQueryPayload>> {
  const query = "MATCH (n) RETURN DISTINCT labels(n) as labels";
  return executeCypherQuery(query);
}

export function getCognitiveNodes(
  convId = "",
  limit = 50,
): Promise<AxiosResponse<Record<string, unknown>>> {
  const params: Record<string, string | number> = {};

  if (convId) {
    params.conv_id = convId;
  }

  if (limit) {
    params.limit = limit;
  }

  return request.get<Record<string, unknown>>("/db/memory/nodes", params);
}

export function getCognitiveNode(
  nodeId: string,
): Promise<AxiosResponse<Record<string, unknown>>> {
  return request.get<Record<string, unknown>>(`/db/memory/node/${nodeId}`);
}

export function createCognitiveNode(
  data: Record<string, unknown>,
): Promise<AxiosResponse<unknown>> {
  return request.post("/db/memory/node", data);
}

export function updateCognitiveNode(
  nodeId: string,
  data: Record<string, unknown>,
): Promise<AxiosResponse<unknown>> {
  return request.put(`/db/memory/node/${nodeId}`, data);
}

export function deleteCognitiveNode(nodeId: string): Promise<AxiosResponse<unknown>> {
  return request.delete(`/db/memory/node/${nodeId}`);
}

export function getAssociations(
  convId = "",
  nodeIds: string | string[] | null = null,
  limit = 200,
): Promise<AxiosResponse<Record<string, unknown>>> {
  const data: {
    conv_id: string;
    limit: number;
    node_ids?: string[];
  } = {
    conv_id: convId,
    limit,
  };

  if (nodeIds) {
    data.node_ids =
      typeof nodeIds === "string" ? nodeIds.split(",") : nodeIds;
  }

  return request.post<Record<string, unknown>>("/db/memory/associations", data);
}

export function createAssociation(
  sourceId: string,
  targetId: string,
  strength = 1,
): Promise<AxiosResponse<unknown>> {
  return request.post("/db/memory/association", {
    source_id: sourceId,
    target_id: targetId,
    strength,
  });
}

export function updateAssociation(
  sourceId: string,
  targetId: string,
  strength: number,
): Promise<AxiosResponse<unknown>> {
  return request.put("/db/memory/association", {
    source_id: sourceId,
    target_id: targetId,
    strength,
  });
}

export function deleteAssociation(
  sourceId: string,
  targetId: string,
): Promise<AxiosResponse<unknown>> {
  return request.delete(
    `/db/memory/association?source_id=${sourceId}&target_id=${targetId}`,
  );
}

export function getConversations(): Promise<AxiosResponse<ConversationRowsPayload>> {
  return request.get<ConversationRowsPayload>("/db/memory/conversations");
}
