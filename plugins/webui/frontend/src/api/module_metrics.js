import { request } from "./index";

export const fetchModuleMetricOptions = (params = {}) =>
  request.get("/api/module-metrics/options", params);

export const fetchModuleMetricSummary = (params = {}) =>
  request.get("/api/module-metrics/summary", params);

export const fetchModuleMetricEvents = (params = {}) =>
  request.get("/api/module-metrics/events", params);
