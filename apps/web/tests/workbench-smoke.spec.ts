import { expect, test, type Page } from "@playwright/test";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { tmpdir } from "node:os";
import { spawnSync } from "node:child_process";
import path from "node:path";

async function chooseSelectOption(page: Page, name: string, option: string, exact = false) {
  await page.getByRole("combobox", { name, exact }).click();
  await page.getByRole("option", { name: option, exact: true }).click();
}

async function expectSelectText(page: Page, name: string, text: string, exact = false) {
  await expect(page.getByRole("combobox", { name, exact })).toContainText(text);
}

test("first screen is the ASIP evidence workbench", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByTestId("asip-workbench")).toBeVisible();
  await expect(page.getByRole("banner")).toContainText("ASIP Evidence Workbench");
  await expect(page.getByRole("navigation", { name: "ASIP sections" })).toContainText("Evidence Search");
  await expect(page.getByRole("textbox", { name: "Evidence query" })).toHaveValue("");
  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText(
    "Enter a query to search live evidence."
  );
  await expect(page.locator("body")).not.toContainText("GCVM_L2_CNTL");
});

test("first screen does not run a static default query or render static evidence rows", async ({ page }) => {
  let requestedUrl = "";
  await page.route("**/api/workbench/query?**", async (route) => {
    requestedUrl = route.request().url();
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        queryId: "api_initial_query",
        rows: [
          {
            source: "api",
            tone: "register",
            symbol: "API_INITIAL_REGISTER",
            relation: "live_default_query",
            score: "0.98",
            path: "api/default/source.c:1"
          }
        ],
        graph: {
          nodes: [{ id: "API_INITIAL_REGISTER", kind: "register", weight: 3 }],
          edges: []
        },
        source: "sqlite"
      })
    });
  });

  await page.goto("/");

  expect(requestedUrl).toBe("");
  const resultsTable = page.getByRole("table", { name: "Evidence results" });
  await expect(resultsTable).not.toContainText("API_INITIAL_REGISTER");
  await expect(resultsTable).not.toContainText("gmc_v11_0_init_golden_registers");
  await expect(page.getByTestId("query-network-graph")).not.toContainText("API_INITIAL_REGISTER");
});

test("settings page persists configurable provider model api and headers", async ({ page }) => {
  await page.goto("/settings");

  await chooseSelectOption(page, "Provider", "OpenAI compatible", true);
  await page.getByRole("textbox", { name: "Edge API base URL" }).fill("https://edge.example.test");
  await page.getByRole("textbox", { name: "Edge API path" }).fill("/v1/chat/completions");
  await page.getByRole("textbox", { name: "Edge model" }).fill("qwen3.6");
  await page.getByRole("textbox", { name: "Fallback model" }).fill("");
  await chooseSelectOption(page, "Embedding provider", "OpenAI compatible");
  await page.getByRole("textbox", { name: "Embedding API base URL" }).fill("https://embed.example.test");
  await page.getByRole("textbox", { name: "Embedding API path" }).fill("/v1/embeddings");
  await page.getByRole("textbox", { name: "Embedding model" }).fill("text-embedding-3-small");
  await page.getByRole("textbox", { name: "Timeout seconds" }).fill("123");
  await page.getByRole("textbox", { name: "Context tokens" }).fill("4096");
  await page.getByRole("textbox", { name: "Prediction tokens" }).fill("777");
  await page.getByRole("textbox", { name: "Temperature" }).fill("0.25");
  await page.getByRole("checkbox", { name: "Enable model thinking" }).check();
  await page
    .getByRole("textbox", { name: "Edge extra headers JSON" })
    .fill('{"Authorization":"Bearer local-test","X-ASIP-Workspace":"amd-mvp1"}');
  await page
    .getByRole("textbox", { name: "Embedding extra headers JSON" })
    .fill('{"Authorization":"Bearer embed-test","X-ASIP-Embed":"yes"}');
  await page.getByRole("button", { name: "Save provider settings" }).click();

  await expect(page.getByText("Provider settings saved")).toBeVisible();
  await expect(page.getByLabel("Workbench status")).toContainText("Provider: unverified");
  await expect(page.getByLabel("Workbench status")).toContainText("Edge: OpenAI-compatible / qwen3.6");
  await expect(page.getByTestId("runtime-config-preview")).toContainText('"provider": "openai-compatible"');
  await expect(page.getByTestId("runtime-config-preview")).toContainText('"api_path": "/v1/chat/completions"');
  await expect(page.getByTestId("runtime-config-preview")).toContainText('"embedding_api_base_url": "https://embed.example.test"');
  await expect(page.getByTestId("runtime-config-preview")).toContainText('"embedding_api_path": "/v1/embeddings"');
  await expect(page.getByTestId("runtime-config-preview")).toContainText('"X-ASIP-Embed": "yes"');
  await expect(page.getByTestId("runtime-config-preview")).toContainText('"num_ctx": 4096');
  await expect(page.getByLabel("Page metrics")).toContainText("edge model: qwen3.6");
  const resultsTable = page.getByRole("table", { name: "Evidence results" });
  await expect(resultsTable).toContainText("qwen3.6");
  await expect(resultsTable).toContainText("semantic_edges");
  await expect(resultsTable).toContainText("openai-compatible");
  await expect(resultsTable).toContainText("https://edge.example.test/v1/chat/completions");
  await expect(resultsTable).toContainText("https://embed.example.test");
  await expect(resultsTable).not.toContainText("qwen3.5:4b");
  await expect(resultsTable).not.toContainText("http://localhost:11434");

  const saved = await page.evaluate(() => window.localStorage.getItem("asip-provider-settings"));
  expect(saved).not.toBeNull();
  expect(JSON.parse(saved ?? "{}")).toMatchObject({
    provider: "openai-compatible",
    apiBaseUrl: "https://edge.example.test",
    apiPath: "/v1/chat/completions",
    edgeModel: "qwen3.6",
    fallbackModel: "",
    embeddingProvider: "openai-compatible",
    embeddingApiBaseUrl: "https://embed.example.test",
    embeddingApiPath: "/v1/embeddings",
    embeddingModel: "text-embedding-3-small",
    timeoutSeconds: "123",
    numCtx: "4096",
    numPredict: "777",
    temperature: "0.25",
    think: true,
    extraHeaders: {
      Authorization: "Bearer local-test",
      "X-ASIP-Workspace": "amd-mvp1"
    },
    embeddingExtraHeaders: {
      Authorization: "Bearer embed-test",
      "X-ASIP-Embed": "yes"
    }
  });

  await page.reload();
  await expectSelectText(page, "Provider", "OpenAI compatible", true);
  await expect(page.getByRole("textbox", { name: "Edge model" })).toHaveValue("qwen3.6");
  await expect(page.getByRole("textbox", { name: "Fallback model" })).toHaveValue("");
  await expectSelectText(page, "Embedding provider", "OpenAI compatible");
  await expect(page.getByRole("textbox", { name: "Embedding API base URL" })).toHaveValue("https://embed.example.test");
  await expect(page.getByRole("textbox", { name: "Embedding API path" })).toHaveValue("/v1/embeddings");
  await expect(page.getByRole("textbox", { name: "Embedding extra headers JSON" })).toHaveValue(
    '{\n  "Authorization": "Bearer embed-test",\n  "X-ASIP-Embed": "yes"\n}'
  );
  await expect(page.getByRole("checkbox", { name: "Enable model thinking" })).toBeChecked();
  await expect(page.getByLabel("Workbench status")).toContainText("Provider: unverified");
  await expect(page.getByLabel("Workbench status")).toContainText("Edge: OpenAI-compatible / qwen3.6");
});

test("settings page hydrates backend provider settings without local storage", async ({ page, request }) => {
  const save = await request.post("/api/workbench/providers/settings", {
    data: {
      edge: {
        provider: "openai-compatible",
        base_url: "https://backend-edge.example.test",
        api_path: "/v1/chat/completions",
        model: "backend-edge-model",
        fallback_model: "",
        extra_headers: { "X-ASIP-Test": "backend" },
        think: true,
        timeout_seconds: 321,
        num_ctx: 8192,
        num_predict: 456,
        temperature: 0.1
      },
      embedding: {
        provider: "ollama",
        base_url: "http://backend-embed.example.test",
        model: "backend-embed-model"
      }
    }
  });
  expect(save.ok()).toBe(true);
  await page.addInitScript(() => window.localStorage.removeItem("asip-provider-settings"));

  await page.goto("/settings");

  await expectSelectText(page, "Provider", "OpenAI compatible", true);
  await expect(page.getByRole("textbox", { name: "Edge API base URL" })).toHaveValue("https://backend-edge.example.test");
  await expect(page.getByRole("textbox", { name: "Edge model" })).toHaveValue("backend-edge-model");
  await expectSelectText(page, "Embedding provider", "Ollama");
  await expect(page.getByRole("textbox", { name: "Embedding API base URL" })).toHaveValue("http://backend-embed.example.test");
  await expect(page.getByRole("textbox", { name: "Embedding model" })).toHaveValue("backend-embed-model");
  await expect(page.getByRole("textbox", { name: "Context tokens" })).toHaveValue("8192");
  await expect(page.getByRole("checkbox", { name: "Enable model thinking" })).toBeChecked();
  await expect(page.getByLabel("Workbench status")).toContainText("Provider: unverified");
  await expect(page.getByLabel("Workbench status")).toContainText("Edge: OpenAI-compatible / backend-edge-model");
  await expect(page.getByTestId("runtime-config-preview")).toContainText('"embedding_model": "backend-embed-model"');
});

test("settings page runs provider smoke through the workbench API", async ({ page }) => {
  await page.route("**/api/workbench/providers/smoke", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ ok: true, message: "Provider smoke passed: api-model" })
    });
  });
  await page.goto("/settings");

  await page.getByRole("button", { name: "Run provider smoke" }).click();

  await expect(page.getByTestId("action-feedback")).toContainText("Provider smoke passed: api-model");
  await expect(page.getByLabel("Workbench status")).toContainText("Provider: verified");
});

test("settings page runs AQ09 provider acceptance through the workbench API", async ({ page }) => {
  let requestBody: { queryIds?: string[]; surfaces?: string[] } = {};
  await page.route("**/api/workbench/acceptance/run", async (route) => {
    requestBody = route.request().postDataJSON() as typeof requestBody;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        summary: { total: 1, passed: 1, partial: 0, failed: 0 },
        queries: [
          {
            id: "AQ09",
            status: "pass",
            row_count: 3,
            provider_checks: {
              embedding: {
                status: "pass",
                provider: "openai-compatible",
                model: "local-openai-embed",
                embedding_count: 3,
                fallback_count: 0
              },
              semantic_edge: {
                status: "pass",
                provider: "ollama",
                model: "gemma4:e4b",
                edge_count: 1
              }
            }
          }
        ]
      })
    });
  });

  await page.goto("/settings");
  await page.getByRole("button", { name: "Run AQ09 acceptance" }).click();

  await expect(page.getByTestId("action-feedback")).toContainText(
    "AQ09 provider acceptance pass: embedding openai-compatible/local-openai-embed, semantic edge ollama/gemma4:e4b"
  );
  await expect(page.getByLabel("Workbench status")).toContainText("Provider: verified");
  expect(requestBody).toMatchObject({
    queryIds: ["AQ09"],
    surfaces: ["CLI", "API", "Web"]
  });
});

test("settings page can run AQ09 against a user supplied DB through the real workbench API", async ({ page }) => {
  test.setTimeout(60_000);
  const edgeServer = await startFakeOllamaEdgeServer();
  const root = mkdtempSync(path.join(tmpdir(), "asip-aq09-ui-"));
  const dbPath = path.join(root, "aq09.db");
  const corpusRoot = path.join(root, "docs");
  mkdirSync(corpusRoot, { recursive: true });
  writeFileSync(
    path.join(corpusRoot, "aq09.md"),
    [
      "Run embedding and optional semantic edge extraction through a configured Ollama provider.",
      "Then switch to an OpenAI compatible provider without changing retrieval or resolver code.",
      "AQ09_UI_SYMBOL keeps this provider acceptance document queryable."
    ].join("\n"),
    "utf8"
  );
  seedProviderAcceptanceDb(dbPath, corpusRoot, edgeServer.baseUrl);

  try {
    await page.goto("/settings");
    await page.getByRole("textbox", { name: "AQ09 acceptance DB path" }).fill(dbPath);
    await page.getByRole("button", { name: "Run AQ09 acceptance" }).click();

    await expect(page.getByTestId("action-feedback")).toContainText(
      "AQ09 provider acceptance pass: embedding openai-compatible/local-openai-embed, semantic edge ollama/gemma4:e4b",
      { timeout: 30_000 }
    );
    await expect(page.getByLabel("Workbench status")).toContainText("Provider: verified");
  } finally {
    await new Promise<void>((resolve, reject) => {
      edgeServer.server.close((error) => (error ? reject(error) : resolve()));
    });
  }
});

test("ollama detection fills edge and embedding models", async ({ page }) => {
  await page.route("**/api/workbench/providers/ollama-tags**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        models: [
          { name: "nomic-embed-text:latest" },
          { name: "gemma4:e4b" },
          { name: "qwen3.5:4b" }
        ]
      })
    });
  });
  await page.goto("/settings");

  await page.getByRole("button", { name: "Detect Ollama models" }).click();

  await expect(page.getByRole("textbox", { name: "Edge API base URL" })).toHaveValue("http://localhost:11434");
  await expect(page.getByRole("textbox", { name: "Embedding API base URL" })).toHaveValue("http://localhost:11434");
  await expect(page.getByRole("textbox", { name: "Edge model" })).toHaveValue("gemma4:e4b");
  await expect(page.getByRole("textbox", { name: "Embedding model" })).toHaveValue("nomic-embed-text:latest");
  await expect(page.getByText("Detected 3 Ollama models")).toBeVisible();
});

test("free evidence query updates result rows and graph", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("textbox", { name: "Evidence query" }).fill("doorbell interrupt disable");
  await page.getByRole("button", { name: "Run query" }).click();

  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("DOORBELL_INTERRUPT_DISABLE");
  await expect(page.getByTestId("query-network-graph")).toContainText("DOORBELL_INTERRUPT_DISABLE");
  await expect(page.getByTestId("action-feedback")).toContainText("Query ran: doorbell interrupt disable");
});

test("evidence query consumes the workbench query API", async ({ page }) => {
  await page.route("**/api/workbench/query?**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        queryId: "api_custom_edge",
        rows: [
          {
            source: "api",
            tone: "register",
            symbol: "API_CUSTOM_REGISTER",
            relation: "api_edge",
            score: "0.99",
            path: "api/generated/source.c:10-12"
          }
        ],
        graph: {
          nodes: [{ id: "API_CUSTOM_REGISTER", kind: "register", weight: 2 }],
          edges: []
        }
      })
    });
  });
  await page.goto("/");

  await page.getByRole("textbox", { name: "Evidence query" }).fill("api custom edge");
  await page.getByRole("button", { name: "Run query" }).click();

  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("API_CUSTOM_REGISTER");
  await expect(page.getByTestId("query-network-graph")).toContainText("API_CUSTOM_REGISTER");
});

test("evidence query inspector renders the selected live evidence chain", async ({ page }) => {
  await page.route("**/api/workbench/query?**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        queryId: "api_live_inspector",
        rows: [
          {
            source: "api",
            tone: "register",
            symbol: "API_INSPECT_REGISTER",
            relation: "write",
            score: "0.97",
            path: "api/inspector/source.c:42",
            snippet: "WREG32(API_INSPECT_REGISTER, data);",
            resolved_chain: "live resolver -> API_INSPECT_REGISTER -> API_INSPECT_FIELD",
            source_type: "code",
            entity_type: "register"
          }
        ],
        graph: {
          nodes: [{ id: "API_INSPECT_REGISTER", kind: "register", weight: 3 }],
          edges: [
            {
              src: "API_INSPECT_REGISTER",
              dst: "API_INSPECT_FIELD",
              relation: "sets_field",
              confidence: 0.97,
              weight: 0.97
            }
          ]
        },
        source: "sqlite"
      })
    });
  });
  await page.goto("/");

  await page.getByRole("textbox", { name: "Evidence query" }).fill("api live inspector");
  await page.getByRole("button", { name: "Run query" }).click();

  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("API_INSPECT_REGISTER");
  await expect(page.getByTestId("query-network-graph")).toContainText("API_INSPECT_REGISTER");
  await expect(page.getByTestId("relationship-panel")).toContainText("API_INSPECT_REGISTER");
  await expect(page.getByTestId("relationship-panel")).toContainText("API_INSPECT_FIELD");
  await expect(page.getByText("WREG32(API_INSPECT_REGISTER, data);")).toBeVisible();
});

test("evidence results expose source types and PDF page citations in table and inspector", async ({ page }) => {
  await page.route("**/api/workbench/query?**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        queryId: "api_multisource_evidence",
        rows: [
          {
            source: "api",
            tone: "pdf",
            symbol: "MI300_PAGE",
            relation: "mention",
            score: "0.88",
            path: "docs/mi300-manual.asset",
            snippet: "AMD Instinct MI300 page citation.",
            resolved_chain: "pdf citation -> MI300_PAGE",
            source_type: "pdf",
            entity_type: "pdf_page",
            page: 7
          },
          {
            source: "api",
            tone: "register",
            symbol: "GCVM_L2_CNTL_BASE_IDX",
            relation: "mention",
            score: "0.91",
            path: "include/asic_reg/gc_11_0_0_offset.h",
            snippet: "#define GCVM_L2_CNTL_BASE_IDX 0",
            source_type: "register",
            entity_type: "register"
          },
          {
            source: "api",
            tone: "doc",
            symbol: "AMDGPU_OVERVIEW",
            relation: "mention",
            score: "0.80",
            path: "docs/amdgpu-overview.asset",
            snippet: "Driver overview documentation.",
            source_type: "doc",
            entity_type: "doc_section"
          }
        ],
        graph: { nodes: [], edges: [] },
        source: "sqlite"
      })
    });
  });
  await page.goto("/");

  await page.getByRole("textbox", { name: "Evidence query" }).fill("multi source evidence");
  await page.getByRole("button", { name: "Run query" }).click();

  const table = page.getByRole("table", { name: "Evidence results" });
  await expect(table).toContainText("pdf");
  await expect(table).toContainText("page 7");
  await expect(table).toContainText("register");
  await expect(table).toContainText("doc");
  await table.getByText("MI300_PAGE").click();
  await expect(page.getByText("pdf pdf_page docs/mi300-manual.asset page 7")).toBeVisible();
});

test("evidence query inspector changes when a different live row is selected", async ({ page }) => {
  await page.route("**/api/workbench/query?**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        queryId: "api_select_inspector",
        rows: [
          {
            source: "api",
            tone: "register",
            symbol: "API_FIRST_REGISTER",
            relation: "read",
            score: "0.90",
            path: "api/first.c:1",
            snippet: "RREG32(API_FIRST_REGISTER);",
            resolved_chain: "live resolver -> API_FIRST_REGISTER"
          },
          {
            source: "api",
            tone: "register",
            symbol: "API_SECOND_REGISTER",
            relation: "write",
            score: "0.95",
            path: "api/second.c:9",
            snippet: "WREG32(API_SECOND_REGISTER, data);",
            resolved_chain: "live resolver -> API_SECOND_REGISTER -> API_SECOND_FIELD"
          }
        ],
        graph: {
          nodes: [
            { id: "API_FIRST_REGISTER", kind: "register", weight: 2 },
            { id: "API_SECOND_REGISTER", kind: "register", weight: 3 }
          ],
          edges: [
            {
              src: "API_SECOND_REGISTER",
              dst: "API_SECOND_FIELD",
              relation: "sets_field",
              confidence: 0.95,
              weight: 0.95
            }
          ]
        },
        source: "sqlite"
      })
    });
  });
  await page.goto("/");

  await page.getByRole("textbox", { name: "Evidence query" }).fill("api select inspector");
  await page.getByRole("button", { name: "Run query" }).click();
  await expect(page.getByTestId("relationship-panel")).toContainText("API_FIRST_REGISTER");

  await page.getByRole("row", { name: /API_SECOND_REGISTER/ }).click();

  await expect(page.getByTestId("relationship-panel")).toContainText("API_SECOND_REGISTER");
  await expect(page.getByTestId("relationship-panel")).toContainText("API_SECOND_FIELD");
  await expect(page.getByText("WREG32(API_SECOND_REGISTER, data);")).toBeVisible();
});

test("query graph fallback derives only API rows when graph payload is omitted", async ({ page }) => {
  await page.route("**/api/workbench/query?**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        queryId: "api_rows_without_graph",
        rows: [
          {
            source: "api",
            tone: "register",
            symbol: "API_ONLY_REGISTER",
            relation: "api_row",
            score: "0.91",
            path: "api/rows-only/source.c:1"
          }
        ],
        source: "sqlite"
      })
    });
  });
  await page.goto("/");

  await page.getByRole("textbox", { name: "Evidence query" }).fill("api rows without graph");
  await page.getByRole("button", { name: "Run query" }).click();

  await expect(page.getByTestId("query-network-graph")).toContainText("API_ONLY_REGISTER");
  await expect(page.getByTestId("query-network-graph")).not.toContainText("GCVM_L2_CNTL");
});

test("free evidence query sends IP and ASIC filters to the query API", async ({ page }) => {
  let requestedUrl = "";
  await page.route("**/api/workbench/query?**", async (route) => {
    requestedUrl = route.request().url();
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        queryId: "filtered_query",
        rows: [
          {
            source: "api",
            tone: "register",
            symbol: "CP_FILTERED_REGISTER",
            relation: "field_set",
            score: "0.97",
            path: "driver.c:1"
          }
        ],
        graph: { nodes: [{ id: "CP_FILTERED_REGISTER", kind: "register" }], edges: [] },
        filters: { ip_block: "CP", asic_or_generation: "gfx1100" }
      })
    });
  });
  await page.goto("/");

  await page.getByRole("textbox", { name: "Evidence query" }).fill("filtered register");
  await page.getByRole("textbox", { name: "IP block filter" }).fill("CP");
  await page.getByRole("textbox", { name: "ASIC or generation filter" }).fill("gfx1100");
  await page.getByRole("button", { name: "Run query" }).click();

  const url = new URL(requestedUrl);
  expect(url.searchParams.get("q")).toBe("filtered register");
  expect(url.searchParams.get("ipBlock")).toBe("CP");
  expect(url.searchParams.get("asic")).toBe("gfx1100");
  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("CP_FILTERED_REGISTER");
});

test("free evidence query shows no-match empty state instead of fallback rows", async ({ page }) => {
  await page.route("**/api/workbench/query?**", async (route) => {
    const url = new URL(route.request().url());
    const query = url.searchParams.get("q");
    if (query !== "no matches") {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          query,
          rows: [
            {
              source: "api",
              tone: "register",
              symbol: "API_INITIAL_REGISTER",
              relation: "live_default_query",
              score: "0.98",
              path: "api/default/source.c:1"
            }
          ],
          graph: { nodes: [{ id: "API_INITIAL_REGISTER", kind: "register", weight: 3 }], edges: [] },
          source: "sqlite"
        })
      });
      return;
    }
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        query: "no matches",
        rows: [],
        graph: { nodes: [], edges: [] },
        empty: true,
        empty_state: "No evidence matched query: no matches",
        source: "sqlite"
      })
    });
  });
  await page.goto("/");

  await page.getByRole("textbox", { name: "Evidence query" }).fill("no matches");
  await page.getByRole("button", { name: "Run query" }).click();

  const resultsTable = page.getByRole("table", { name: "Evidence results" });
  await expect(resultsTable).toContainText("No evidence matched query: no matches");
  await expect(resultsTable).not.toContainText("GCVM_L2_CNTL");
  await expect(page.getByTestId("query-network-graph")).not.toContainText("GCVM_L2_CNTL");
});

test("evidence query API failure shows an error state without static seed rows or graph nodes", async ({ page }) => {
  await page.route("**/api/workbench/query?**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      status: 500,
      body: JSON.stringify({ error: "query backend unavailable" })
    });
  });
  await page.goto("/");

  await page.getByRole("textbox", { name: "Evidence query" }).fill("backend outage");
  await page.getByRole("button", { name: "Run query" }).click();

  const resultsTable = page.getByRole("table", { name: "Evidence results" });
  await expect(resultsTable).toContainText(/Query (API returned 500|failed)/);
  await expect(page.getByTestId("action-feedback")).toContainText(/Query failed|Query API returned 500/);
  await expect(resultsTable).not.toContainText("GCVM_L2_CNTL");
  await expect(resultsTable).not.toContainText("MI300 CDNA3 ISA");
  await expect(page.getByTestId("query-network-graph")).not.toContainText("GCVM_L2_CNTL");
  await expect(page.getByTestId("query-network-graph")).not.toContainText("MI300 CDNA3 ISA");
});

test("corpus page loads the workbench corpora API", async ({ page }) => {
  await page.route("**/api/workbench/corpora", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        corpora: [
          {
            id: "api-corpus",
            repo: "https://example.test/api-corpus",
            sourceRoot: "/api/corpus/root",
            include: ["**/*.c"],
            fileCount: 42,
            commit: "abc1234"
          }
        ]
      })
    });
  });

  await page.goto("/corpus");

  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("api-corpus");
  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("/api/corpus/root");
  await expect(page.getByLabel("Page metrics")).toContainText("files: 42");
});

test("corpus page treats empty API corpora as empty instead of default corpora", async ({ page }) => {
  await page.route("**/api/workbench/corpora", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ corpora: [] })
    });
  });

  await page.goto("/corpus");

  const resultsTable = page.getByRole("table", { name: "Evidence results" });
  await expect(resultsTable).not.toContainText("mxgpu");
  await expect(resultsTable).not.toContainText("linux-amdgpu");
  await expect(resultsTable).not.toContainText("amd-pdf-mi300");
  await expect(resultsTable).toContainText("empty");
  await expect(page.getByLabel("Page metrics")).toContainText("corpora: 0");
});

test("corpus page runs the index job through the workbench API", async ({ page }) => {
  await page.route("**/api/workbench/index", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        status: "indexed",
        dbPath: "data/asip.db",
        documents: 5,
        chunks: 9,
        edges: 16
      })
    });
  });
  await page.goto("/corpus");

  await expect(page.getByRole("checkbox", { name: /^Index / }).first()).toBeChecked();
  await page.getByRole("button", { name: "Run index" }).click();

  await expect(page.getByTestId("action-feedback")).toContainText(
    "Index built: 5 documents, 9 chunks, 16 edges -> data/asip.db"
  );
});

test("corpus page indexes only the selected corpus and shows indexed status", async ({ page }) => {
  let indexRequestBody: unknown = null;
  await page.route("**/api/workbench/corpora", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        corpora: [
          {
            id: "api-corpus-a",
            repo: "https://example.test/api-corpus-a",
            sourceRoot: "/api/corpus/a",
            include: ["**/*.c"],
            fileCount: 11,
            status: "not_indexed"
          },
          {
            id: "api-corpus-b",
            repo: "https://example.test/api-corpus-b",
            sourceRoot: "/api/corpus/b",
            include: ["**/*.h"],
            fileCount: 7,
            status: "not_indexed"
          }
        ]
      })
    });
  });
  await page.route("**/api/workbench/index", async (route) => {
    indexRequestBody = route.request().postDataJSON();
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        status: "indexed",
        corpusIds: ["api-corpus-b"],
        dbPath: "data/asip.db",
        documents: 1,
        chunks: 2,
        edges: 3
      })
    });
  });

  await page.goto("/corpus");

  await page.getByRole("checkbox", { name: "Index api-corpus-a" }).uncheck();
  await expect(page.getByRole("checkbox", { name: "Index api-corpus-b" })).toBeChecked();
  await page.getByRole("button", { name: "Run index" }).click();

  await expect.poll(() => indexRequestBody).toEqual({ corpusIds: ["api-corpus-b"] });
  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("api-corpus-b");
  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("indexed");
  await expect(page.getByTestId("action-feedback")).toContainText("api-corpus-b");
});

test("corpus page marks selected corpus failed when indexing fails", async ({ page }) => {
  await page.route("**/api/workbench/corpora", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        corpora: [
          {
            id: "missing-docs",
            repo: "local",
            sourceRoot: "/tmp/asip-missing-docs",
            include: ["**/*.md"],
            fileCount: 0,
            status: "not_indexed"
          }
        ]
      })
    });
  });
  await page.route("**/api/workbench/index", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      status: 500,
      body: JSON.stringify({
        status: "failed",
        corpusIds: ["missing-docs"],
        error: "source root not found: /tmp/asip-missing-docs"
      })
    });
  });

  await page.goto("/corpus");
  await page.getByRole("button", { name: "Run index" }).click();

  const resultsTable = page.getByRole("table", { name: "Evidence results" });
  await expect(resultsTable).toContainText("missing-docs");
  await expect(resultsTable).toContainText("failed");
  await expect(page.getByTestId("action-feedback")).toContainText("source root not found");
});

test("acceptance page loads real run summaries from the workbench API", async ({ page }) => {
  await page.route("**/api/workbench/acceptance", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        runs: [
          {
            id: "api-run",
            model: "api-model:latest",
            passed: 8,
            partial: 0,
            failed: 1,
            queryCount: 9,
            artifactPath: "docs/qa/api-run.json"
          }
        ]
      })
    });
  });

  await page.goto("/acceptance");

  await expect(page.getByLabel("Page metrics")).toContainText("passed: 8");
  await expect(page.getByLabel("Page metrics")).toContainText("partial: 0");
  await expect(page.getByLabel("Page metrics")).toContainText("failed: 1");
  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("api-run");
  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("api-model:latest");
  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("docs/qa/api-run.json");
});

test("acceptance failures expand with query-level reasons and evidence sources", async ({ page }) => {
  await page.route("**/api/workbench/acceptance", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        runs: [
          {
            id: "api-failing-run",
            model: "asip.acceptance",
            passed: 0,
            partial: 0,
            failed: 1,
            queryCount: 1,
            artifactPath: "docs/qa/api-failing-run.json",
            details: [
              {
                id: "AQ01",
                status: "fail",
                query: "Who reads or writes regGCVM_L2_CNTL?",
                failureReasons: ["index job 3 failed: interrupted after embedding reindex"],
                missingSurfaces: ["Web", "MCP"],
                sourcePaths: ["drivers/gpu/drm/amd/amdgpu/gfxhub_v11_5_0.c"],
                sourceTypes: ["code"],
                rowCount: 24,
                graphEdgeCount: 2
              }
            ]
          }
        ]
      })
    });
  });

  await page.goto("/acceptance");
  await page.getByRole("button", { name: /api-failing-run/ }).click();

  await expect(page.getByText("AQ01")).toBeVisible();
  await expect(page.getByText("index job 3 failed: interrupted after embedding reindex")).toBeVisible();
  await expect(page.getByText("missing surfaces: Web, MCP")).toBeVisible();
  await expect(page.getByText("drivers/gpu/drm/amd/amdgpu/gfxhub_v11_5_0.c")).toBeVisible();
  await expect(page.getByText("rows 24 / graph edges 2")).toBeVisible();
});

test("acceptance API failure shows explicit empty state without static QA seed rows", async ({ page }) => {
  await page.route("**/api/workbench/acceptance", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      status: 500,
      body: JSON.stringify({ error: "acceptance backend unavailable" })
    });
  });

  await page.goto("/acceptance");

  const resultsTable = page.getByRole("table", { name: "Evidence results" });
  await expect(resultsTable).not.toContainText("mxgpu_gcvm_l2_cntl_fields");
  await expect(resultsTable).not.toContainText("qwen3.5");
  await expect(resultsTable).toContainText("empty");
  await expect(page.getByLabel("Page metrics")).toContainText("runs: 0");
});

test("corpus page adds user corpus rows", async ({ page }) => {
  await page.goto("/corpus");

  await page.getByRole("textbox", { name: "Corpus id" }).fill("amd-docs");
  await page.getByRole("textbox", { name: "Repository URL" }).fill("https://example.test/amd-docs");
  await page.getByRole("textbox", { name: "Source root" }).fill("/data/amd-docs");
  await page.getByRole("textbox", { name: "Include globs" }).fill("**/*.pdf, **/*.md");
  await page.getByRole("button", { name: "Add corpus" }).click();

  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("amd-docs");
  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("/data/amd-docs");
  await expect(page.getByText("Corpus amd-docs added")).toBeVisible();
});

test("corpus page adds indexes and queries a real local corpus through the UI", async ({ page }) => {
  test.setTimeout(60_000);
  const root = mkdtempSync(path.join(tmpdir(), "asip-ui-corpus-"));
  const docsRoot = path.join(root, "docs");
  mkdirSync(docsRoot, { recursive: true });
  const uniqueId = `ui-full-loop-${Date.now()}`;
  const uniqueSymbol = `UI_FULL_LOOP_REGISTER_${Date.now()}`;
  writeFileSync(
    path.join(docsRoot, "note.md"),
    `${uniqueSymbol} sets UI_FULL_LOOP_FIELD before browser validation.`,
    "utf8"
  );

  await page.goto("/corpus");
  await page.getByRole("textbox", { name: "Corpus id" }).fill(uniqueId);
  await page.getByRole("textbox", { name: "Repository URL" }).fill("local");
  await page.getByRole("textbox", { name: "Source root" }).fill(root);
  await page.getByRole("textbox", { name: "Include globs" }).fill("**/*.md");
  await page.getByRole("button", { name: "Add corpus" }).click();
  await expect(page.getByText(`Corpus ${uniqueId} added`)).toBeVisible();

  const checkboxes = page.getByRole("checkbox", { name: /^Index / });
  const count = await checkboxes.count();
  for (let index = 0; index < count; index += 1) {
    const checkbox = checkboxes.nth(index);
    const label = await checkbox.getAttribute("aria-label");
    if (label === `Index ${uniqueId}`) {
      await checkbox.check();
    } else {
      await checkbox.uncheck();
    }
  }

  await page.getByRole("button", { name: "Run index" }).click();
  await expect(page.getByTestId("action-feedback")).toContainText(`Index built for ${uniqueId}`, { timeout: 30_000 });
  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("indexed");

  await page.getByRole("link", { name: "Evidence Search" }).click();
  await expect(page).toHaveURL("/");
  await expect(page.getByRole("textbox", { name: "Evidence query" })).toHaveValue("");
  await page.getByRole("textbox", { name: "Evidence query" }).fill(uniqueSymbol);
  await page.getByRole("button", { name: "Run query" }).click();

  const resultsTable = page.getByRole("table", { name: "Evidence results" });
  await expect(resultsTable).toContainText(uniqueSymbol, { timeout: 30_000 });
  await expect(resultsTable).toContainText("note.md");
});

test("resolver page adds configurable profiles", async ({ page }) => {
  await page.goto("/resolver-profiles");

  await expect(page.getByRole("textbox", { name: "Profile id" })).toHaveValue("initial");
  await expect(page.getByRole("textbox", { name: "Wrapper symbol" })).toHaveValue("RREG32");
  await expect(page.getByRole("textbox", { name: "Config path" })).toHaveValue("configs/resolvers/initial.yaml");
  await page.getByRole("button", { name: "Add resolver profile" }).click();

  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("RREG32");
  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("initial");
  await expect(page.getByText("Resolver profile initial added")).toBeVisible();
});

test("resolver page validates configurable profiles from user source", async ({ page }) => {
  const symbol = `UI_DYNAMIC_REGISTER_${Date.now()}`;
  await page.goto("/resolver-profiles");

  await page.getByRole("button", { name: "Add resolver profile" }).click();
  await expect(page.getByText("Resolver profile initial added")).toBeVisible();

  await page.getByRole("textbox", { name: "Validation source" }).fill(`RREG32(${symbol});`);
  await page.getByRole("button", { name: "Validate resolver profile" }).click();

  await expect(page.getByText(`Resolver profile initial validated ${symbol}`)).toBeVisible();
});

test("resolver page can add disabled profiles with visible status", async ({ page }) => {
  await page.goto("/resolver-profiles");

  await page.getByRole("checkbox", { name: "Enable resolver profile" }).uncheck();
  await page.getByRole("button", { name: "Add resolver profile" }).click();

  const resultsTable = page.getByRole("table", { name: "Evidence results" });
  await expect(resultsTable).toContainText("RREG32");
  await expect(resultsTable).toContainText("disabled");
});

test("resolver page loads resolver profiles from the workbench API", async ({ page }) => {
  await page.route("**/api/workbench/resolver-profiles", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        profiles: [
          {
            id: "api-resolver",
            language: "cpp",
            wrappers: ["API_WRAPPER"],
            path: "configs/resolvers/api-resolver.yaml",
            enabled: true
          }
        ]
      })
    });
  });

  await page.goto("/resolver-profiles");

  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("API_WRAPPER");
  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("api-resolver");
  await expect(page.getByLabel("Page metrics")).toContainText("profiles: 1");
});

test("resolver page treats empty API profiles as empty instead of default profiles", async ({ page }) => {
  await page.route("**/api/workbench/resolver-profiles", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ profiles: [] })
    });
  });

  await page.goto("/resolver-profiles");

  const resultsTable = page.getByRole("table", { name: "Evidence results" });
  await expect(resultsTable).not.toContainText("WREG32_SOC15");
  await expect(resultsTable).not.toContainText("adapt->reg_offset");
  await expect(resultsTable).not.toContainText("toy-python");
  await expect(resultsTable).toContainText("empty");
  await expect(page.getByLabel("Page metrics")).toContainText("profiles: 0");
});

test("graph API failure shows graph error empty state without static seed nodes", async ({ page }) => {
  await page.route(/\/api\/workbench\/graph(?:\?|$)/, async (route) => {
    await route.fulfill({
      contentType: "application/json",
      status: 500,
      body: JSON.stringify({ error: "graph backend unavailable" })
    });
  });

  await page.goto("/graph");

  const graph = page.getByTestId("global-network-graph");
  await expect(graph).toContainText(/Graph (API returned 500|failed|unavailable)|No graph data/);
  await expect(graph).not.toContainText("GCVM_L2_CNTL");
  await expect(graph).not.toContainText("MI300 CDNA3 ISA");
  await expect(graph).not.toContainText("DOORBELL_INTERRUPT_DISABLE");
  await expect(page.locator("body")).not.toContainText("GCVM_L2_CNTL");
  await expect(page.locator("body")).not.toContainText("MI300 CDNA3 ISA");
  await expect(page.locator("body")).not.toContainText("DOORBELL_INTERRUPT_DISABLE");
  await expect(page.locator("body")).not.toContainText("Shortest Path");
  await expect(page.locator("body")).not.toContainText("Neighborhood:");
});

test("graph empty state does not render static seed copy anywhere on the page", async ({ page }) => {
  await page.route(/\/api\/workbench\/graph(?:\?|$)/, async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        queryId: "global",
        source: "networkx",
        graph_runtime: "networkx",
        nodes: [],
        edges: []
      })
    });
  });

  await page.goto("/graph");

  await expect(page.getByTestId("global-network-graph")).toContainText("No graph data returned.");
  await expect(page.locator("body")).not.toContainText("GCVM_L2_CNTL");
  await expect(page.locator("body")).not.toContainText("ENABLE_L2_CACHE");
  await expect(page.locator("body")).not.toContainText("gmc_v11_0_init_golden_registers");
  await expect(page.locator("body")).not.toContainText("MI300 CDNA3 ISA");
  await expect(page.locator("body")).not.toContainText("DOORBELL_INTERRUPT_DISABLE");
});

test("graph page relationship panel is API-backed when graph API succeeds", async ({ page }) => {
  await page.route(/\/api\/workbench\/graph(?:\?|$)/, async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        queryId: "global",
        nodes: [
          { id: "API_GLOBAL_REGISTER", kind: "register", weight: 3 },
          { id: "API_GLOBAL_FIELD", kind: "field", weight: 2 }
        ],
        edges: [
          {
            src: "API_GLOBAL_REGISTER",
            relation: "api_sets_field",
            dst: "API_GLOBAL_FIELD",
            confidence: 0.92,
            weight: 0.92
          }
        ],
        source: "networkx",
        graph_runtime: "networkx"
      })
    });
  });

  await page.goto("/graph");

  const relationshipPanel = page.getByTestId("relationship-panel");
  await expect(relationshipPanel).toContainText("API_GLOBAL_REGISTER api_sets_field API_GLOBAL_FIELD");
  await expect(relationshipPanel).not.toContainText("GCVM_L2_CNTL connects code");
  await expect(relationshipPanel).not.toContainText("Weighted global graph emphasizes");
});

test("graph page runs semantic edge generation through the workbench API", async ({ page }) => {
  let requestBody: { q?: string } = {};
  await page.route("**/api/workbench/semantic-edges", async (route) => {
    requestBody = route.request().postDataJSON() as typeof requestBody;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        source: "semantic_edge_job",
        edge_count: 1,
        provider: "ollama",
        model: "gemma4:e4b",
        graph: {
          nodes: [
            { id: "UI_EDGE_REGISTER", kind: "register", weight: 1 },
            { id: "UI_EDGE_FIELD", kind: "field", weight: 1 }
          ],
          edges: [
            {
              src: "UI_EDGE_REGISTER",
              relation: "sets_field",
              dst: "UI_EDGE_FIELD",
              confidence: 0.93,
              weight: 0.93
            }
          ],
          source: "networkx",
          graph_runtime: "networkx"
        }
      })
    });
  });

  await page.goto("/graph");
  await page.getByRole("textbox", { name: "Evidence query" }).fill("UI_EDGE_REGISTER UI_EDGE_FIELD");
  await page.getByRole("button", { name: "Generate semantic edges" }).click();

  expect(requestBody.q).toBe("UI_EDGE_REGISTER UI_EDGE_FIELD");
  await expect(page.getByTestId("action-feedback")).toContainText("Semantic edges generated: 1");
  await expect(page.getByTestId("global-network-graph")).toContainText("UI_EDGE_FIELD");
});

test("graph page runs batch semantic edge generation through the workbench API", async ({ page }) => {
  let requestBody: { mode?: string; batchSize?: number } = {};
  await page.route("**/api/workbench/semantic-edges", async (route) => {
    requestBody = route.request().postDataJSON() as typeof requestBody;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        source: "semantic_edge_batch_job",
        edge_count: 1,
        candidate_count: 2,
        provider: "ollama",
        model: "gemma4:e4b",
        graph: {
          nodes: [
            { id: "docs/guide.md#programming-local-registers", kind: "doc_section", weight: 1 },
            { id: "UI_BATCH_REGISTER", kind: "register", weight: 1 },
            { id: "UI_BATCH_FIELD", kind: "field", weight: 1 }
          ],
          edges: [
            {
              src: "UI_BATCH_REGISTER",
              relation: "sets_field",
              dst: "UI_BATCH_FIELD",
              confidence: 0.93,
              weight: 0.93
            }
          ],
          source: "networkx",
          graph_runtime: "networkx"
        }
      })
    });
  });

  await page.goto("/graph");
  await page.getByRole("button", { name: "Generate batch semantic edges" }).click();

  expect(requestBody.mode).toBe("batch");
  expect(requestBody.batchSize).toBe(6);
  await expect(page.getByTestId("action-feedback")).toContainText("Batch semantic edges generated: 1 from 2 candidates");
  await expect(page.getByTestId("global-network-graph")).toContainText("UI_BATCH_FIELD");
});

test("shadcn Radix controls keep styled dimensions instead of bare browser defaults", async ({ page }) => {
  await page.goto("/corpus");

  const button = page.locator('[data-slot="button"]').first();
  const input = page.locator('[data-slot="input"]').first();
  const tableContainer = page.locator('[data-slot="table-container"]').first();
  const checkbox = page.locator('[data-slot="checkbox"]').first();

  await expect(button).toBeVisible();
  await expect(input).toBeVisible();
  await expect(tableContainer).toBeVisible();
  await expect(checkbox).toBeVisible();

  const styles = await page.evaluate(() => {
    const read = (selector: string) => {
      const element = document.querySelector(selector);
      if (!element) {
        return null;
      }
      const computed = window.getComputedStyle(element);
      return {
        borderRadius: computed.borderRadius,
        display: computed.display,
        height: computed.height,
        overflowX: computed.overflowX,
        width: computed.width
      };
    };
    return {
      button: read('[data-slot="button"]'),
      input: read('[data-slot="input"]'),
      table: read('[data-slot="table-container"]'),
      checkbox: read('[data-slot="checkbox"]')
    };
  });

  expect(styles.button?.display).toMatch(/^(inline-)?flex$/);
  expect(parseFloat(styles.button?.height ?? "0")).toBeGreaterThanOrEqual(30);
  expect(parseFloat(styles.input?.height ?? "0")).toBeGreaterThanOrEqual(30);
  expect(parseFloat(styles.input?.borderRadius ?? "0")).toBeGreaterThanOrEqual(4);
  expect(styles.table?.overflowX).toBe("auto");
  expect(parseFloat(styles.checkbox?.width ?? "0")).toBeGreaterThanOrEqual(14);
});

test("page action buttons show visible queued feedback", async ({ page }) => {
  await page.goto("/graph");

  await page.getByRole("button", { name: "Generate semantic edges" }).click();

  await expect(page.getByTestId("action-feedback")).toContainText("Enter a query before generating semantic edges.");
});

async function startFakeOllamaEdgeServer(): Promise<{ server: Server; baseUrl: string }> {
  const server = createServer((request, response) => {
    if (request.method !== "POST" || request.url !== "/api/chat") {
      response.writeHead(404, { "Content-Type": "application/json" });
      response.end(JSON.stringify({ error: "not found" }));
      return;
    }
    response.writeHead(200, { "Content-Type": "application/json" });
    response.end(
      JSON.stringify({
        message: {
          content: JSON.stringify({
            cases: [
              {
                id: "provider-smoke",
                edges: [
                  {
                    src: "GCVM_L2_CNTL",
                    relation: "sets_field",
                    dst: "ENABLE_L2_CACHE",
                    confidence: 0.9,
                    evidence: "fixture"
                  }
                ]
              }
            ]
          })
        }
      })
    );
  });
  await new Promise<void>((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => resolve());
  });
  const address = server.address() as AddressInfo;
  return { server, baseUrl: `http://127.0.0.1:${address.port}` };
}

function seedProviderAcceptanceDb(dbPath: string, corpusRoot: string, edgeBaseUrl: string) {
  const repoRoot = path.resolve(process.cwd(), "../..");
  const script = String.raw`
import sys
from pathlib import Path
from asip.workbench import add_corpus, index_registered_corpora, save_provider_settings

class FakeOpenAIEmbeddingTransport:
    def post_json(self, url, payload, headers, timeout):
        return {"data": [{"index": index, "embedding": [0.11 + index, 0.22, 0.33]} for index, _ in enumerate(payload["input"])]}

db_path = Path(sys.argv[1])
corpus_root = Path(sys.argv[2])
edge_base_url = sys.argv[3]
save_provider_settings(
    db_path,
    {
        "edge": {
            "provider": "ollama",
            "base_url": edge_base_url,
            "api_path": "/api/chat",
            "model": "gemma4:e4b",
            "think": False,
            "timeout_seconds": 2,
        },
        "embedding": {
            "provider": "openai-compatible",
            "base_url": "https://embedding.example.test",
            "api_path": "/v1/embeddings",
            "model": "local-openai-embed",
            "extra_headers": {"X-ASIP-Embed": "ui-acceptance"},
            "timeout_seconds": 1,
        },
    },
)
add_corpus(db_path, "aq09-ui-docs", "local", str(corpus_root), ["**/*.md"], "doc")
index_registered_corpora(
    db_path,
    corpus_ids=["aq09-ui-docs"],
    embedding_transport=FakeOpenAIEmbeddingTransport(),
)
`;
  const result = spawnSync("python3", ["-c", script, dbPath, corpusRoot, edgeBaseUrl], {
    cwd: repoRoot,
    env: {
      ...process.env,
      PYTHONDONTWRITEBYTECODE: "1",
      PYTHONPATH: [path.join(repoRoot, "packages/core/src"), path.join(repoRoot, "packages/core/tests"), repoRoot].join(":")
    },
    encoding: "utf8"
  });
  expect(result.status, result.stderr || result.stdout).toBe(0);
}
