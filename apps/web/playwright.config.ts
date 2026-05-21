import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3100";
const skipWebServer = process.env.PLAYWRIGHT_SKIP_WEB_SERVER === "1";
const parsedUrl = new URL(baseURL);
const hostname = parsedUrl.hostname || "127.0.0.1";
const port = parsedUrl.port || "3100";
const webServerCommand =
  process.env.PLAYWRIGHT_WEB_SERVER_COMMAND ?? `pnpm dev --hostname ${hostname} --port ${port}`;
const reuseExistingServer = process.env.PLAYWRIGHT_REUSE_EXISTING_SERVER === "1";

export default defineConfig({
  testDir: "./tests",
  workers: 1,
  webServer: skipWebServer
    ? undefined
    : {
        command: webServerCommand,
        url: baseURL,
        reuseExistingServer,
        timeout: 120_000
      },
  use: {
    baseURL,
    trace: "on-first-retry"
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    }
  ]
});
