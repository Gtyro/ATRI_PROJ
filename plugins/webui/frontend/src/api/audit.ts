import type { AxiosResponse } from "axios";

import { request } from "./index";

export interface OperationAuditItem {
  id: number;
  username: string;
  action: string;
  target_type: string;
  target_id: string | null;
  success: boolean;
  detail: unknown;
  request_method: string | null;
  request_path: string | null;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
}

export interface OperationAuditListPayload {
  total: number;
  items: OperationAuditItem[];
}

export interface OperationAuditMetaPayload {
  actions: string[];
  target_types: string[];
  default_retention_days: number;
}

export interface OperationAuditCleanupPayload {
  retention_days: number;
  deleted: number;
}

export interface OperationAuditQueryParams extends Record<string, unknown> {
  limit?: number;
  offset?: number;
  username?: string;
  action?: string;
  target_type?: string;
  success?: boolean;
}

export function fetchOperationAuditLogs(
  params: OperationAuditQueryParams = {},
): Promise<AxiosResponse<OperationAuditListPayload>> {
  return request.get<OperationAuditListPayload>("/api/audit/logs", params);
}

export function fetchOperationAuditMeta(): Promise<AxiosResponse<OperationAuditMetaPayload>> {
  return request.get<OperationAuditMetaPayload>("/api/audit/meta");
}

export function cleanupOperationAuditLogs(
  retentionDays?: number,
): Promise<AxiosResponse<OperationAuditCleanupPayload>> {
  if (retentionDays && retentionDays > 0) {
    return request.post<OperationAuditCleanupPayload>(
      `/api/audit/cleanup?retention_days=${encodeURIComponent(String(retentionDays))}`,
    );
  }
  return request.post<OperationAuditCleanupPayload>("/api/audit/cleanup");
}
