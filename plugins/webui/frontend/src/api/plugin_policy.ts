import type { AxiosResponse } from "axios";

import { request } from "./index";

export const fetchPolicyMatrix = (): Promise<AxiosResponse<Record<string, unknown>>> =>
  request.get<Record<string, unknown>>("/api/plugin-policy/matrix");

export const updatePolicy = (
  data: Record<string, unknown>,
): Promise<AxiosResponse<Record<string, unknown>>> =>
  request.post<Record<string, unknown>>("/api/plugin-policy/policy", data);

export const batchUpdatePolicy = (
  data: Record<string, unknown>,
): Promise<AxiosResponse<Record<string, unknown>>> =>
  request.post<Record<string, unknown>>("/api/plugin-policy/batch", data);
