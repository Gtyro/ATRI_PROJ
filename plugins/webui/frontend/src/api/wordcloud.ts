import type { AxiosResponse } from "axios";

import { request } from "./index";

export function getWordCloudData(
  convId: string,
  limit: number | null = null,
  refresh = false,
): Promise<AxiosResponse<Record<string, unknown>>> {
  const params: Record<string, string | number | boolean> = {
    conv_id: convId,
  };

  if (limit != null) {
    params.limit = limit;
  }

  if (refresh) {
    params.refresh = refresh;
  }

  return request.get<Record<string, unknown>>("/api/wordcloud/data", params);
}

export function getWordCloudHistory(
  convId: string,
  date: string,
  hour: number | null = null,
): Promise<AxiosResponse<Record<string, unknown>>> {
  const params: Record<string, string | number> = {
    conv_id: convId,
    date,
  };

  if (hour !== null) {
    params.hour = hour;
  }

  return request.get<Record<string, unknown>>("/api/wordcloud/history", params);
}

export function generateWordCloud(
  convId: string,
  wordLimit: number | null = null,
  hours: number | null = null,
): Promise<AxiosResponse<Record<string, unknown>>> {
  const params: Record<string, string | number> = {
    conv_id: convId,
  };

  if (wordLimit != null) {
    params.word_limit = wordLimit;
  }

  if (hours != null) {
    params.hours = hours;
  }

  return request.post<Record<string, unknown>>("/api/wordcloud/generate", null, {
    params,
  });
}

export function getConversations(): Promise<AxiosResponse<Record<string, unknown>>> {
  return request.get<Record<string, unknown>>("/api/wordcloud/conversations");
}
