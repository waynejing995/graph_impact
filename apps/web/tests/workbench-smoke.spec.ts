import { expect, test } from "@playwright/test";

test("first screen is the ASIP evidence workbench", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByTestId("asip-workbench")).toBeVisible();
  await expect(page.getByRole("banner")).toContainText("ASIP Evidence Workbench");
  await expect(page.getByRole("navigation", { name: "ASIP sections" })).toContainText("Evidence Search");
  await expect(page.getByRole("textbox", { name: "Evidence query" })).toHaveValue(
    "Who writes regGCVM_L2_CNTL?"
  );
  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("GCVM_L2_CNTL");
  await expect(page.getByTestId("relationship-panel")).toContainText("has_field");
});

test("settings page persists configurable provider model api and headers", async ({ page }) => {
  await page.goto("/settings");

  await page.getByRole("combobox", { name: "Provider" }).selectOption("openai-compatible");
  await page.getByRole("textbox", { name: "Chat API base URL" }).fill("https://llm.example.test");
  await page.getByRole("textbox", { name: "Chat API path" }).fill("/v1/chat/completions");
  await page.getByRole("textbox", { name: "Edge model" }).fill("qwen3.6");
  await page.getByRole("textbox", { name: "Fallback model" }).fill("");
  await page.getByRole("textbox", { name: "Embedding model" }).fill("text-embedding-3-small");
  await page.getByRole("textbox", { name: "Timeout seconds" }).fill("123");
  await page.getByRole("textbox", { name: "Context tokens" }).fill("4096");
  await page.getByRole("textbox", { name: "Prediction tokens" }).fill("777");
  await page.getByRole("textbox", { name: "Temperature" }).fill("0.25");
  await page.getByRole("checkbox", { name: "Enable model thinking" }).check();
  await page
    .getByRole("textbox", { name: "Extra headers JSON" })
    .fill('{"Authorization":"Bearer local-test","X-ASIP-Workspace":"amd-mvp1"}');
  await page.getByRole("button", { name: "Save provider settings" }).click();

  await expect(page.getByText("Provider settings saved")).toBeVisible();
  await expect(page.getByLabel("Workbench status")).toContainText("OpenAI-compatible: qwen3.6");
  await expect(page.getByTestId("runtime-config-preview")).toContainText('"provider": "openai-compatible"');
  await expect(page.getByTestId("runtime-config-preview")).toContainText('"api_path": "/v1/chat/completions"');
  await expect(page.getByTestId("runtime-config-preview")).toContainText('"num_ctx": 4096');
  await expect(page.getByLabel("Page metrics")).toContainText("edge model: qwen3.6");
  const resultsTable = page.getByRole("table", { name: "Evidence results" });
  await expect(resultsTable).toContainText("qwen3.6");
  await expect(resultsTable).toContainText("semantic_edges");
  await expect(resultsTable).toContainText("openai-compatible");
  await expect(resultsTable).toContainText("https://llm.example.test/v1/chat/completions");
  await expect(resultsTable).not.toContainText("qwen3.5:4b");
  await expect(resultsTable).not.toContainText("http://localhost:11434");

  const saved = await page.evaluate(() => window.localStorage.getItem("asip-provider-settings"));
  expect(saved).not.toBeNull();
  expect(JSON.parse(saved ?? "{}")).toMatchObject({
    provider: "openai-compatible",
    apiBaseUrl: "https://llm.example.test",
    apiPath: "/v1/chat/completions",
    edgeModel: "qwen3.6",
    fallbackModel: "",
    embeddingModel: "text-embedding-3-small",
    timeoutSeconds: "123",
    numCtx: "4096",
    numPredict: "777",
    temperature: "0.25",
    think: true,
    extraHeaders: {
      Authorization: "Bearer local-test",
      "X-ASIP-Workspace": "amd-mvp1"
    }
  });

  await page.reload();
  await expect(page.getByRole("combobox", { name: "Provider" })).toHaveValue("openai-compatible");
  await expect(page.getByRole("textbox", { name: "Edge model" })).toHaveValue("qwen3.6");
  await expect(page.getByRole("textbox", { name: "Fallback model" })).toHaveValue("");
  await expect(page.getByRole("checkbox", { name: "Enable model thinking" })).toBeChecked();
  await expect(page.getByLabel("Workbench status")).toContainText("OpenAI-compatible: qwen3.6");
});

test("page action buttons show visible queued feedback", async ({ page }) => {
  await page.goto("/graph");

  await page.getByRole("button", { name: "Inspect edge provenance" }).click();

  await expect(page.getByTestId("action-feedback")).toContainText("Inspect edge provenance queued");
});
