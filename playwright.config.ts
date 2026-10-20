import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 90000,
  expect: { timeout: 15000 },
  workers: 1,
  use: {
    baseURL: process.env.PULSEPILOT_TEST_URL ?? "http://127.0.0.1:3000",
    viewport: { width: 1440, height: 1080 },
    trace: "retain-on-failure",
  },
});
