import axios, {
  type AxiosInstance,
  type AxiosRequestConfig,
  type AxiosResponse,
} from "axios";
import { useAuthStore } from "@/stores/auth";
import router from "@/router";

interface RetryableRequestConfig extends AxiosRequestConfig {
  _retry?: boolean;
}

// 是否正在刷新 token
let isRefreshing = false;
// 请求队列
let requests: Array<() => void> = [];

// 创建 axios 实例
const service: AxiosInstance = axios.create({
  baseURL: "", // 使用相对路径，配合 vite 的 proxy
  timeout: 5000,
});

// 请求拦截器
service.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("token");
    if (token) {
      const headers = config.headers || {};
      (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
      config.headers = headers;
    }
    return config;
  },
  (error: unknown) => Promise.reject(error),
);

// 响应拦截器
service.interceptors.response.use(
  (response) => response,
  async (error: unknown) => {
    const axiosError = error as {
      config?: RetryableRequestConfig;
      response?: { status?: number };
    };
    const originalRequest = axiosError.config;

    const shouldRefresh =
      axiosError.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !String(originalRequest.url || "").includes("/auth/refresh-token");

    if (shouldRefresh) {
      if (!isRefreshing) {
        isRefreshing = true;
        const authStore = useAuthStore();

        try {
          await authStore.refreshToken();

          const headers = originalRequest.headers || {};
          (headers as Record<string, string>)["Authorization"] =
            `Bearer ${localStorage.getItem("token") || ""}`;
          originalRequest.headers = headers;
          originalRequest._retry = true;

          requests.forEach((callback) => callback());
          requests = [];

          return service(originalRequest);
        } catch (refreshError: unknown) {
          authStore.resetAuth();
          router.replace("/login");
          return Promise.reject(refreshError);
        } finally {
          isRefreshing = false;
        }
      }

      return new Promise((resolve) => {
        requests.push(() => {
          const headers = originalRequest.headers || {};
          (headers as Record<string, string>)["Authorization"] =
            `Bearer ${localStorage.getItem("token") || ""}`;
          originalRequest.headers = headers;
          resolve(service(originalRequest));
        });
      });
    }

    return Promise.reject(error);
  },
);

// 替换全局 axios 默认值
axios.defaults.baseURL = service.defaults.baseURL;
axios.defaults.timeout = service.defaults.timeout;
const axiosInterceptors = axios.interceptors as unknown as Record<
  string,
  { handlers: unknown } | undefined
>;
const serviceInterceptors = service.interceptors as unknown as Record<
  string,
  { handlers: unknown } | undefined
>;

Object.keys(serviceInterceptors).forEach((type) => {
  const target = axiosInterceptors[type];
  const source = serviceInterceptors[type];
  if (!target || !source) {
    return;
  }
  target.handlers = source.handlers;
});

export const request = {
  get: <T = unknown>(
    url: string,
    params?: Record<string, unknown>,
    config: AxiosRequestConfig = {},
  ): Promise<AxiosResponse<T>> => service.get<T>(url, { params, ...config }),

  post: <T = unknown>(
    url: string,
    data?: unknown,
    config: AxiosRequestConfig = {},
  ): Promise<AxiosResponse<T>> => service.post<T>(url, data, config),

  put: <T = unknown>(
    url: string,
    data?: unknown,
    config: AxiosRequestConfig = {},
  ): Promise<AxiosResponse<T>> => service.put<T>(url, data, config),

  delete: <T = unknown>(
    url: string,
    config: AxiosRequestConfig = {},
  ): Promise<AxiosResponse<T>> => service.delete<T>(url, config),
};

export default service;
