import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://127.0.0.1:3100",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    ...devices["Desktop Chrome"],
  },
  webServer: [
    {
      command: "PLAYWRIGHT=1 corepack pnpm exec next dev -H 127.0.0.1 -p 3100",
      url: "http://127.0.0.1:3100",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command:
        "P3_UI_MODE=demo P3_UI_ROLE='Data Steward' ../.venv/bin/streamlit run ../frontend/streamlit_app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true",
      url: "http://127.0.0.1:8501",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
