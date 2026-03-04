import { defineStore } from "pinia";
import { ElMessage } from "element-plus";

import { getUserInfo, login, logout, refreshToken, type AuthUser } from "@/api/auth";
import router from "@/router";
import { isTokenExpired } from "@/utils/jwt";

interface AuthState {
  token: string;
  user: AuthUser | null;
}

const parseStoredUser = (): AuthUser | null => {
  const rawUser = localStorage.getItem("user");
  if (!rawUser) {
    return null;
  }

  try {
    const parsed = JSON.parse(rawUser);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch (_error) {
    return null;
  }
};

const getErrorMessage = (error: unknown): string => {
  if (error instanceof Error) {
    return error.message;
  }
  return "未知错误";
};

export const useAuthStore = defineStore("auth", {
  state: (): AuthState => ({
    token: localStorage.getItem("token") || "",
    user: parseStoredUser(),
  }),

  getters: {
    isAuthenticated: (state): boolean =>
      Boolean(state.token) && !isTokenExpired(state.token),
    username: (state): string | undefined => state.user?.username,
  },

  actions: {
    async login(username: string, password: string): Promise<boolean> {
      try {
        const response = await login(username, password);

        const token = response.data.access_token;
        const refreshTokenValue = response.data.refresh_token;
        if (!token) {
          throw new Error("响应中没有找到访问令牌");
        }

        this.token = token;
        localStorage.setItem("token", token);
        if (refreshTokenValue) {
          localStorage.setItem("refresh_token", refreshTokenValue);
        }
        await this.fetchUserInfo();
        return true;
      } catch (error: unknown) {
        this.resetAuth();
        throw error;
      }
    },

    async fetchUserInfo(): Promise<AuthUser | null> {
      if (!this.token) {
        return null;
      }

      try {
        const response = await getUserInfo();
        this.user = response.data;
        localStorage.setItem("user", JSON.stringify(response.data));
        return this.user;
      } catch (error: unknown) {
        ElMessage.error(`获取用户信息失败: ${getErrorMessage(error)}`);
        this.resetAuth();
        throw error;
      }
    },

    async logout(): Promise<void> {
      try {
        await logout();
      } finally {
        this.resetAuth();
        router.push("/login");
      }
    },

    resetAuth(): void {
      this.token = "";
      this.user = null;
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      localStorage.removeItem("refresh_token");
    },

    async refreshToken(): Promise<boolean> {
      try {
        const refreshTokenValue = localStorage.getItem("refresh_token");
        if (!refreshTokenValue) {
          throw new Error("没有刷新令牌");
        }

        const response = await refreshToken(refreshTokenValue);

        const token = response.data.access_token;
        const newRefreshToken = response.data.refresh_token;
        if (!token) {
          throw new Error("响应中没有找到访问令牌");
        }

        this.token = token;
        localStorage.setItem("token", token);
        if (newRefreshToken) {
          localStorage.setItem("refresh_token", newRefreshToken);
        } else {
          localStorage.removeItem("refresh_token");
        }

        return true;
      } catch (error: unknown) {
        this.resetAuth();
        throw error;
      }
    },
  },
});
