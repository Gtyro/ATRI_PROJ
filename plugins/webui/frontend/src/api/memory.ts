import type { AxiosResponse } from "axios";

import { request } from "./index";

export interface MemoryTimelineItem {
  created_at: number;
  [key: string]: unknown;
}

export interface MemoryTimelinePayload {
  memories: MemoryTimelineItem[];
  [key: string]: unknown;
}

export interface MemoryStatsPayload {
  [key: string]: unknown;
}

export function getMemoryTimeline(
  convId = "",
  startTime: number | null = null,
  endTime: number | null = null,
  limit = 100,
): Promise<AxiosResponse<MemoryTimelinePayload>> {
  const params: Record<string, string | number> = {};

  if (convId) {
    params.conv_id = convId;
  }

  if (startTime != null) {
    params.start_time = startTime;
  }

  if (endTime != null) {
    params.end_time = endTime;
  }

  params.limit = limit;

  return request.get<MemoryTimelinePayload>("/api/memory/timeline", params);
}

export function getMemoryDetail(
  memoryId: string,
): Promise<AxiosResponse<Record<string, unknown>>> {
  return request.get<Record<string, unknown>>(`/api/memory/detail/${memoryId}`);
}

export function getMemoryStats(
  convId = "",
): Promise<AxiosResponse<MemoryStatsPayload>> {
  const params = convId ? { conv_id: convId } : {};
  return request.get<MemoryStatsPayload>("/api/memory/stats", params);
}

export { getConversations } from "./db";
