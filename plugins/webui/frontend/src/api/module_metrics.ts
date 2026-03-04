import type { AxiosResponse } from "axios";

import { request } from "./index";
import {
  validateModuleMetricDetailPayload,
  validateModuleMetricModulesPayload,
  validateModuleMetricOptionsPayload,
  validateModuleMetricOverviewPayload,
} from "./contracts/module_metrics";
import type {
  ModuleMetricDetailPayload,
  ModuleMetricModulesPayload,
  ModuleMetricOptionsPayload,
  ModuleMetricOverviewPayload,
  ModuleMetricQueryParams,
} from "@/types/module_metrics";

type Validator<TPayload> = (payload: unknown) => TPayload;

const withContractValidation = async <TPayload>(
  requestPromise: Promise<AxiosResponse<unknown>>,
  endpoint: string,
  validator: Validator<TPayload>,
): Promise<AxiosResponse<TPayload>> => {
  const response = await requestPromise;
  try {
    const validatedPayload = validator(response?.data);
    return {
      ...response,
      data: validatedPayload,
    } as AxiosResponse<TPayload>;
  } catch (error: unknown) {
    const reason =
      error instanceof Error ? error.message : "schema validation failed";
    throw new Error(`[module-metrics] ${endpoint} contract mismatch: ${reason}`);
  }
};

export const fetchModuleMetricModules = (
  params: ModuleMetricQueryParams = {},
): Promise<AxiosResponse<ModuleMetricModulesPayload>> =>
  withContractValidation(
    request.get("/api/module-metrics/modules", params),
    "/api/module-metrics/modules",
    validateModuleMetricModulesPayload,
  );

export const fetchModuleMetricOverview = (
  params: ModuleMetricQueryParams = {},
): Promise<AxiosResponse<ModuleMetricOverviewPayload>> =>
  withContractValidation(
    request.get("/api/module-metrics/overview", params),
    "/api/module-metrics/overview",
    validateModuleMetricOverviewPayload,
  );

export const fetchModuleMetricDetail = (
  moduleId: string,
  params: ModuleMetricQueryParams = {},
): Promise<AxiosResponse<ModuleMetricDetailPayload>> =>
  withContractValidation(
    request.get(`/api/module-metrics/modules/${moduleId}/detail`, params),
    `/api/module-metrics/modules/${moduleId}/detail`,
    validateModuleMetricDetailPayload,
  );

export const fetchModuleMetricOptions = (
  params: ModuleMetricQueryParams = {},
): Promise<AxiosResponse<ModuleMetricOptionsPayload>> =>
  withContractValidation(
    request.get("/api/module-metrics/options", params),
    "/api/module-metrics/options",
    validateModuleMetricOptionsPayload,
  );

export const fetchModuleMetricSummary = (
  params: ModuleMetricQueryParams = {},
): Promise<AxiosResponse<unknown>> =>
  request.get("/api/module-metrics/summary", params);

export const fetchModuleMetricEvents = (
  params: ModuleMetricQueryParams = {},
): Promise<AxiosResponse<unknown>> =>
  request.get("/api/module-metrics/events", params);
