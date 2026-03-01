import { request } from "./index";
import {
  validateModuleMetricDetailPayload,
  validateModuleMetricModulesPayload,
  validateModuleMetricOptionsPayload,
  validateModuleMetricOverviewPayload,
} from "./contracts/module_metrics";

const withContractValidation = async (requestPromise, endpoint, validator) => {
  const response = await requestPromise;
  try {
    validator(response?.data);
  } catch (error) {
    const reason =
      error instanceof Error ? error.message : "schema validation failed";
    throw new Error(
      `[module-metrics] ${endpoint} contract mismatch: ${reason}`,
    );
  }
  return response;
};

export const fetchModuleMetricModules = (params = {}) =>
  withContractValidation(
    request.get("/api/module-metrics/modules", params),
    "/api/module-metrics/modules",
    validateModuleMetricModulesPayload,
  );

export const fetchModuleMetricOverview = (params = {}) =>
  withContractValidation(
    request.get("/api/module-metrics/overview", params),
    "/api/module-metrics/overview",
    validateModuleMetricOverviewPayload,
  );

export const fetchModuleMetricDetail = (moduleId, params = {}) =>
  withContractValidation(
    request.get(`/api/module-metrics/modules/${moduleId}/detail`, params),
    `/api/module-metrics/modules/${moduleId}/detail`,
    validateModuleMetricDetailPayload,
  );

export const fetchModuleMetricOptions = (params = {}) =>
  withContractValidation(
    request.get("/api/module-metrics/options", params),
    "/api/module-metrics/options",
    validateModuleMetricOptionsPayload,
  );

export const fetchModuleMetricSummary = (params = {}) =>
  request.get("/api/module-metrics/summary", params);

export const fetchModuleMetricEvents = (params = {}) =>
  request.get("/api/module-metrics/events", params);
