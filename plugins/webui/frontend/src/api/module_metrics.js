import { request } from "./index";

export const fetchModuleMetricModules = (params = {}) =>
  request.get("/api/module-metrics/modules", params);

export const fetchModuleMetricOverview = (params = {}) =>
  request.get("/api/module-metrics/overview", params);

export const fetchModuleMetricDetail = (moduleId, params = {}) =>
  request.get(`/api/module-metrics/modules/${moduleId}/detail`, params);

export const fetchModuleMetricOptions = (params = {}) =>
  request.get("/api/module-metrics/options", params);

export const fetchModuleMetricSummary = (params = {}) =>
  request.get("/api/module-metrics/summary", params);

export const fetchModuleMetricEvents = (params = {}) =>
  request.get("/api/module-metrics/events", params);
