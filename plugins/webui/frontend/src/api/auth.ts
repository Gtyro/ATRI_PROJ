import axios, { type AxiosResponse } from "axios";
import { request } from "./index";

export interface AuthTokenPayload {
  access_token: string;
  refresh_token?: string;
  token_type?: string;
  [key: string]: unknown;
}

export interface AuthUser {
  username?: string;
  [key: string]: unknown;
}

export type RegisterPayload = Record<string, unknown>;

// 登录获取令牌
export function login(
  username: string,
  password: string,
): Promise<AxiosResponse<AuthTokenPayload>> {
  const params = new URLSearchParams();
  params.append("username", username);
  params.append("password", password);
  params.append("grant_type", "password");

  return axios.post<AuthTokenPayload>("/auth/token", params, {
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
  });
}

// 刷新令牌
export function refreshToken(
  refreshTokenValue: string,
): Promise<AxiosResponse<AuthTokenPayload>> {
  return axios.post<AuthTokenPayload>("/auth/refresh-token", {
    refresh_token: refreshTokenValue,
  });
}

// 退出登录
export function logout(): Promise<void> {
  return Promise.resolve();
}

// 获取当前用户信息
export function getUserInfo(): Promise<AxiosResponse<AuthUser>> {
  return request.get<AuthUser>("/auth/users/me");
}

// 注册新用户
export function register(
  userData: RegisterPayload,
): Promise<AxiosResponse<unknown>> {
  return request.post("/auth/register", userData);
}
