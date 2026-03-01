import { defineConfig, devices } from "@playwright/test";

const isCI = Boolean(process.env.CI);
const useWebServer = process.env.PLAYWRIGHT_SKIP_WEBSERVER !== "1";
const baseUrl = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:4173";
const parsedBaseUrl = new URL(baseUrl);
const serverHost = parsedBaseUrl.hostname || "127.0.0.1";
const serverPort =
  parsedBaseUrl.port || (parsedBaseUrl.protocol === "https:" ? "443" : "80");

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  timeout: 30 * 1000,
  expect: {
    timeout: 5000,
  },
  forbidOnly: isCI,
  retries: isCI ? 1 : 0,
  reporter: isCI
    ? [["list"], ["html", { open: "never" }]]
    : [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: baseUrl,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    headless: true,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: useWebServer
    ? {
        command: `npm run dev -- --host ${serverHost} --port ${serverPort}`,
        url: baseUrl,
        reuseExistingServer: false,
        timeout: 120 * 1000,
      }
    : undefined,
});
