import { request } from "./index";

export const fetchPolicyMatrix = () => request.get("/api/plugin-policy/matrix");

export const updatePolicy = (data) =>
  request.post("/api/plugin-policy/policy", data);

export const batchUpdatePolicy = (data) =>
  request.post("/api/plugin-policy/batch", data);
