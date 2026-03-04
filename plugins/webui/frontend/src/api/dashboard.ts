import type { AxiosResponse } from "axios";
import { fetchEventSource } from "@microsoft/fetch-event-source";

import { request } from "./index";

export type DashboardStreamPayload = Record<string, unknown>;

type UpdateListener = (payload: DashboardStreamPayload) => void;
type ErrorListener = (error: unknown) => void;

interface DashboardStreamState {
  controller: AbortController | null;
  listeners: Set<UpdateListener>;
  errorListeners: Set<ErrorListener>;
  intervalSeconds: number;
}

const dashboardStreamState: DashboardStreamState = {
  controller: null,
  listeners: new Set<UpdateListener>(),
  errorListeners: new Set<ErrorListener>(),
  intervalSeconds: 5,
};

function stopSharedDashboardStreamIfIdle(): void {
  if (
    dashboardStreamState.listeners.size > 0 ||
    dashboardStreamState.errorListeners.size > 0
  ) {
    return;
  }
  if (!dashboardStreamState.controller) {
    return;
  }
  dashboardStreamState.controller.abort();
  dashboardStreamState.controller = null;
}

function emitDashboardUpdate(payload: DashboardStreamPayload): void {
  dashboardStreamState.listeners.forEach((listener) => {
    try {
      listener(payload);
    } catch (err: unknown) {
      console.error("dashboard SSE 回调执行失败:", err);
    }
  });
}

function emitDashboardError(err: unknown): void {
  dashboardStreamState.errorListeners.forEach((listener) => {
    try {
      listener(err);
    } catch (callbackErr: unknown) {
      console.error("dashboard SSE 错误回调执行失败:", callbackErr);
    }
  });
}

function ensureSharedDashboardStream(intervalSeconds = 5): void {
  if (dashboardStreamState.controller) {
    return;
  }

  dashboardStreamState.intervalSeconds = intervalSeconds;
  dashboardStreamState.controller = new AbortController();
  const controller = dashboardStreamState.controller;

  void fetchEventSource(
    `/api/dashboard/stream?interval_seconds=${dashboardStreamState.intervalSeconds}`,
    {
      method: "GET",
      signal: controller.signal,
      openWhenHidden: true,
      async onopen(response) {
        if (response.ok) {
          return;
        }
        throw new Error(`dashboard SSE open failed: ${response.status}`);
      },
      async fetch(input: RequestInfo | URL, init?: RequestInit) {
        const token = localStorage.getItem("token");
        return fetch(input, {
          ...init,
          headers: {
            Accept: "text/event-stream",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
        });
      },
      onmessage(event) {
        if (event.event && event.event !== "dashboard_update") {
          return;
        }
        if (!event.data) {
          return;
        }
        try {
          emitDashboardUpdate(JSON.parse(event.data) as DashboardStreamPayload);
        } catch (err: unknown) {
          console.error("解析 dashboard SSE 消息失败:", err);
        }
      },
      onerror(err) {
        emitDashboardError(err);
      },
    },
  )
    .catch((err: unknown) => {
      if (controller.signal.aborted) {
        return;
      }
      emitDashboardError(err);
    })
    .finally(() => {
      if (dashboardStreamState.controller !== controller) {
        return;
      }
      dashboardStreamState.controller = null;
      if (
        dashboardStreamState.listeners.size > 0 ||
        dashboardStreamState.errorListeners.size > 0
      ) {
        ensureSharedDashboardStream(dashboardStreamState.intervalSeconds);
      }
    });
}

export function fetchDashboardBotInfo(): Promise<AxiosResponse<Record<string, unknown>>> {
  return request.get<Record<string, unknown>>("/api/dashboard/bot-info");
}

export function fetchDashboardConnectionLogs(
  limit = 20,
): Promise<AxiosResponse<Record<string, unknown>>> {
  return request.get<Record<string, unknown>>("/api/dashboard/bot-connections", {
    limit,
  });
}

export function fetchChatThroughputHourly(
  hours = 24,
): Promise<AxiosResponse<Record<string, unknown>>> {
  return request.get<Record<string, unknown>>("/api/dashboard/chat-throughput/hourly", {
    hours,
  });
}

export function fetchChatThroughputDaily(
  days = 120,
): Promise<AxiosResponse<Record<string, unknown>>> {
  return request.get<Record<string, unknown>>("/api/dashboard/chat-throughput/daily", {
    days,
  });
}

export interface DashboardStreamSubscriptionOptions {
  intervalSeconds?: number;
  signal?: AbortSignal;
  onUpdate?: UpdateListener;
  onError?: ErrorListener;
}

export function subscribeDashboardStream(
  options: DashboardStreamSubscriptionOptions = {},
): () => void {
  const {
    intervalSeconds = 5,
    signal,
    onUpdate,
    onError,
  } = options;
  const updateListener = typeof onUpdate === "function" ? onUpdate : null;
  const errorListener = typeof onError === "function" ? onError : null;
  let released = false;

  if (updateListener) {
    dashboardStreamState.listeners.add(updateListener);
  }
  if (errorListener) {
    dashboardStreamState.errorListeners.add(errorListener);
  }

  ensureSharedDashboardStream(intervalSeconds);

  const release = (): void => {
    if (released) {
      return;
    }
    released = true;
    if (updateListener) {
      dashboardStreamState.listeners.delete(updateListener);
    }
    if (errorListener) {
      dashboardStreamState.errorListeners.delete(errorListener);
    }
    stopSharedDashboardStreamIfIdle();
  };

  if (signal) {
    if (signal.aborted) {
      release();
      return release;
    }
    signal.addEventListener("abort", release, { once: true });
  }

  return release;
}
