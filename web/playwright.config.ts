import { defineConfig, devices } from "@playwright/test";

const internalConsoleUrl = "http://127.0.0.1:18502";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  timeout: 60_000,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://127.0.0.1:3100",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    ...devices["Desktop Chrome"],
  },
  webServer: [
    {
      command:
        `PLAYWRIGHT=1 NEXT_PUBLIC_INTERNAL_CONSOLE_URL=${internalConsoleUrl} ` +
        "corepack pnpm exec next dev -H 127.0.0.1 -p 3100",
      url: "http://127.0.0.1:3100",
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command:
        "P3_UI_MODE=demo P3_UI_ROLE='Data Steward' " +
        "python -m streamlit run ../frontend/streamlit_app.py " +
        "--server.address 127.0.0.1 --server.port 18502 --server.headless true",
      url: internalConsoleUrl,
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
