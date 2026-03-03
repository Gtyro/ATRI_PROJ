import { fetchEventSource } from "@microsoft/fetch-event-source";

import { request } from "./index";

const dashboardStreamState = {
  controller: null,
  listeners: new Set(),
  errorListeners: new Set(),
  intervalSeconds: 5,
};

function stopSharedDashboardStreamIfIdle() {
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

function emitDashboardUpdate(payload) {
  dashboardStreamState.listeners.forEach((listener) => {
    try {
      listener(payload);
    } catch (err) {
      console.error("dashboard SSE 回调执行失败:", err);
    }
  });
}

function emitDashboardError(err) {
  dashboardStreamState.errorListeners.forEach((listener) => {
    try {
      listener(err);
    } catch (callbackErr) {
      console.error("dashboard SSE 错误回调执行失败:", callbackErr);
    }
  });
}

function ensureSharedDashboardStream(intervalSeconds = 5) {
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
      async fetch(input, init) {
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
          emitDashboardUpdate(JSON.parse(event.data));
        } catch (err) {
          console.error("解析 dashboard SSE 消息失败:", err);
        }
      },
      onerror(err) {
        emitDashboardError(err);
      },
    },
  )
    .catch((err) => {
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

export function fetchDashboardBotInfo() {
  return request.get("/api/dashboard/bot-info");
}

export function fetchDashboardConnectionLogs(limit = 20) {
  return request.get("/api/dashboard/bot-connections", { limit });
}

export function fetchChatThroughputHourly(hours = 24) {
  return request.get("/api/dashboard/chat-throughput/hourly", { hours });
}

export function fetchChatThroughputDaily(days = 120) {
  return request.get("/api/dashboard/chat-throughput/daily", { days });
}

export function subscribeDashboardStream({
  intervalSeconds = 5,
  signal,
  onUpdate,
  onError,
} = {}) {
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

  const release = () => {
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
