import {
  createRouter,
  createWebHashHistory,
  type RouteRecordRaw,
} from "vue-router";

import { useAuthStore } from "@/stores/auth";
import { isTokenExpired } from "@/utils/jwt";

const Login = () => import("@/views/LoginPage.vue");
const AdminLayout = () => import("@/views/AdminLayout.vue");
const DBAdmin = () => import("@/views/DBAdmin.vue");
const MemoryAdmin = () => import("@/views/MemoryAdmin.vue");
const DashboardOverview = () => import("@/views/dashboard/DashboardOverview.vue");
const WordCloudPage = () => import("@/views/wordcloud/WordCloudPage.vue");
const MemoryTimeline = () => import("@/views/MemoryTimeline.vue");
const PluginPolicyPage = () => import("@/views/PluginPolicyPage.vue");
const ModuleMetricsPage = () => import("@/views/ModuleMetricsPage.vue");
const OperationAuditPage = () => import("@/views/OperationAuditPage.vue");

const routes: RouteRecordRaw[] = [
  {
    path: "/",
    redirect: "/admin",
  },
  {
    path: "/login",
    component: Login,
    meta: { requiresAuth: false },
  },
  {
    path: "/admin",
    component: AdminLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: "",
        redirect: "/admin/dashboard",
      },
      {
        path: "dashboard",
        component: DashboardOverview,
        meta: { requiresAuth: true },
      },
      {
        path: "db-admin",
        component: DBAdmin,
        meta: { requiresAuth: true },
      },
      {
        path: "memory-admin",
        component: MemoryAdmin,
        meta: { requiresAuth: true },
      },
      {
        path: "memory-timeline",
        component: MemoryTimeline,
        meta: { requiresAuth: true },
      },
      {
        path: "wordcloud",
        component: WordCloudPage,
        meta: { requiresAuth: true },
      },
      {
        path: "plugin-policy",
        component: PluginPolicyPage,
        meta: { requiresAuth: true },
      },
      {
        path: "module-metrics",
        component: ModuleMetricsPage,
        meta: { requiresAuth: true },
      },
      {
        path: "operation-audit",
        component: OperationAuditPage,
        meta: { requiresAuth: true },
      },
    ],
  },
];

const router = createRouter({
  history: createWebHashHistory(),
  routes,
});

router.beforeEach((to, _from, next) => {
  const authStore = useAuthStore();
  const token = authStore.token;

  if (token && isTokenExpired(token)) {
    authStore.resetAuth();
  }

  const requiresAuth = to.matched.some(
    (record) => record.meta.requiresAuth === true,
  );
  const isAuthenticated = authStore.isAuthenticated;

  if (requiresAuth && !isAuthenticated) {
    next("/login");
    return;
  }

  if (to.path === "/login" && isAuthenticated) {
    next("/admin");
    return;
  }

  next();
});

export default router;
