import { fetchEventSource } from "@microsoft/fetch-event-source";

import { request } from "./index";

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

export async function subscribeDashboardStream({
  intervalSeconds = 5,
  signal,
  onUpdate,
  onError,
} = {}) {
  const token = localStorage.getItem("token");

  await fetchEventSource(
    `/api/dashboard/stream?interval_seconds=${intervalSeconds}`,
    {
      method: "GET",
      signal,
      openWhenHidden: true,
      headers: {
        Accept: "text/event-stream",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      onmessage(event) {
        if (event.event && event.event !== "dashboard_update") {
          return;
        }
        if (!event.data) {
          return;
        }
        try {
          const payload = JSON.parse(event.data);
          if (typeof onUpdate === "function") {
            onUpdate(payload);
          }
        } catch (err) {
          console.error("解析 dashboard SSE 消息失败:", err);
        }
      },
      onerror(err) {
        if (typeof onError === "function") {
          onError(err);
        }
      },
    },
  );
}
