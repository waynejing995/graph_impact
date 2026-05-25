import { expect, test, type Page } from "@playwright/test";
import { existsSync, mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { tmpdir } from "node:os";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import path from "node:path";

async function chooseSelectOption(page: Page, name: string, option: string, exact = false) {
  await page.getByRole("combobox", { name, exact }).click();
  await page.getByRole("option", { name: option, exact: true }).click();
}

async function expectSelectText(page: Page, name: string, text: string, exact = false) {
  await expect(page.getByRole("combobox", { name, exact })).toContainText(text);
}

async function setSliderToMinimum(page: Page, name: string) {
  const slider = page.getByRole("slider", { name, exact: true });
  await slider.focus();
  await page.keyboard.press("Home");
}

async function routeWorkbenchDbPath(page: Page, dbPath: string) {
  const addDbPathToUrl = (requestUrl: string) => {
    const url = new URL(requestUrl);
    url.searchParams.set("dbPath", dbPath);
    return url.toString();
  };
  const addDbPathToBody = (bodyText: string | null) =>
    JSON.stringify({ ...(bodyText ? JSON.parse(bodyText) : {}), dbPath });

  await page.route("**/api/workbench/corpora**", async (route) => {
    if (route.request().method() === "GET") {
      await route.continue({ url: addDbPathToUrl(route.request().url()) });
      return;
    }
    await route.continue({
      headers: { ...route.request().headers(), "content-type": "application/json" },
      postData: addDbPathToBody(route.request().postData())
    });
  });
  await page.route("**/api/workbench/index", async (route) => {
    await route.continue({
      headers: { ...route.request().headers(), "content-type": "application/json" },
      postData: addDbPathToBody(route.request().postData())
    });
  });
  await page.route("**/api/workbench/query?**", async (route) => {
    await route.continue({ url: addDbPathToUrl(route.request().url()) });
  });
  await page.route("**/api/workbench/jobs?**", async (route) => {
    await route.continue({ url: addDbPathToUrl(route.request().url()) });
  });
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

test("global symbol search runs a live query from any workbench page", async ({ page }) => {
  let requestedUrl = "";
  await page.route("**/api/workbench/query?**", async (route) => {
    requestedUrl = route.request().url();
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        queryId: "global_search_query",
        rows: [
          {
            source: "api",
            tone: "register",
            symbol: "API_GLOBAL_SEARCH_REGISTER",
            relation: "global_search",
            score: "0.93",
            path: "api/global/search.c:7",
            source_type: "code"
          }
        ],
        graph: {
          nodes: [
            { id: "API_GLOBAL_SEARCH_FUNCTION", kind: "function", weight: 1 },
            { id: "API_GLOBAL_SEARCH_REGISTER", kind: "register", weight: 1 }
          ],
          edges: [
            {
              src: "API_GLOBAL_SEARCH_FUNCTION",
              relation: "writes",
              dst: "API_GLOBAL_SEARCH_REGISTER",
              confidence: 0.93,
              weight: 0.93
            }
          ]
        },
        source: "sqlite"
      })
    });
  });
  await page.goto("/graph");

  await page.getByRole("textbox", { name: "Global symbol search" }).fill("API_GLOBAL_SEARCH_REGISTER");
  await page.getByRole("textbox", { name: "Global symbol search" }).press("Enter");

  await expect.poll(() => requestedUrl).toContain("API_GLOBAL_SEARCH_REGISTER");
  expect(new URL(requestedUrl).searchParams.get("q")).toBe("API_GLOBAL_SEARCH_REGISTER");
  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("API_GLOBAL_SEARCH_REGISTER");
  await expect(page.getByTestId("global-network-graph")).toContainText("API_GLOBAL_SEARCH_REGISTER");
});

test("graph page initial URL query runs live query and renders graph edge answers", async ({ page }) => {
  let graphRequests = 0;
  let requestedUrl = "";
  await page.route("**/api/workbench/graph**", async (route) => {
    graphRequests += 1;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        queryId: "global",
        nodes: [{ id: "GLOBAL_ONLY_REGISTER", kind: "register", weight: 1 }],
        edges: [],
        source: "networkx"
      })
    });
  });
  await page.route("**/api/workbench/query?**", async (route) => {
    requestedUrl = route.request().url();
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        query: "who will write/read CP_HQD_* regs",
        rows: [
          {
            source: "code",
            tone: "code",
            symbol: "gfx_deactivate_hqd",
            target_symbol: "CP_HQD_ACTIVE",
            relation: "reads",
            score: "0.97",
            path: "drivers/gpu/drm/amd/amdgpu/gfx_v8_0.c",
            line_start: 4369,
            source_type: "code",
            entity_type: "function"
          }
        ],
        graph: {
          nodes: [
            { id: "function:linux-amdgpu:concept:test:gfx_deactivate_hqd", kind: "function", label: "gfx_deactivate_hqd", weight: 1 },
            { id: "register:CP:CP_HQD_ACTIVE", kind: "register", label: "CP_HQD_ACTIVE", weight: 1 }
          ],
          edges: [
            {
              src: "function:linux-amdgpu:concept:test:gfx_deactivate_hqd",
              relation: "reads",
              dst: "register:CP:CP_HQD_ACTIVE",
              confidence: 0.97,
              weight: 0.97
            }
          ],
          source: "networkx"
        },
        source: "sqlite"
      })
    });
  });

  await page.goto(`/graph?q=${encodeURIComponent("who will write/read CP_HQD_* regs")}`);

  await expect.poll(() => requestedUrl).toContain("who+will+write%2Fread+CP_HQD_*+regs");
  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("gfx_deactivate_hqd -> CP_HQD_ACTIVE");
  await expect(page.getByLabel("Page metrics")).toContainText("matches: 1");
  expect(graphRequests).toBe(0);
});

test("global search preserves URL dbPath when navigating from non-query pages", async ({ page }) => {
  const dbPath = "/tmp/asip-global-search-dbpath.db";
  let requestedUrl = "";
  await page.route("**/api/workbench/query?**", async (route) => {
    requestedUrl = route.request().url();
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        queryId: "dbpath_global_search",
        rows: [],
        graph: { nodes: [], edges: [] },
        source: "sqlite"
      })
    });
  });

  await page.goto(`/corpus?dbPath=${encodeURIComponent(dbPath)}`);
  await page.getByRole("textbox", { name: "Global symbol search" }).fill("DBPATH_GLOBAL_REGISTER");
  await page.getByRole("textbox", { name: "Global symbol search" }).press("Enter");

  await page.waitForURL((url) => url.pathname === "/" && url.searchParams.get("q") === "DBPATH_GLOBAL_REGISTER");
  expect(new URL(page.url()).searchParams.get("dbPath")).toBe(dbPath);
  await expect.poll(() => requestedUrl).toContain("DBPATH_GLOBAL_REGISTER");
  expect(new URL(requestedUrl).searchParams.get("dbPath")).toBe(dbPath);
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

test("settings page uses URL dbPath when saving provider settings", async ({ page }) => {
  const root = mkdtempSync(path.join(tmpdir(), "asip-settings-url-dbpath-"));
  const dbPath = path.join(root, "settings.db");

  await page.goto(`/settings?dbPath=${encodeURIComponent(dbPath)}`);
  await chooseSelectOption(page, "Provider", "OpenAI compatible", true);
  await page.getByRole("textbox", { name: "Edge API base URL" }).fill("https://edge-dbpath.example.test");
  await page.getByRole("textbox", { name: "Edge model" }).fill("dbpath-edge-model");
  await page.getByRole("textbox", { name: "Embedding model" }).fill("dbpath-embed-model");
  await page.getByRole("button", { name: "Save provider settings" }).click();

  await expect(page.getByText("Provider settings saved")).toBeVisible();
  expect(readSqliteScalar(dbPath, "select json_extract(settings_json, '$.edge.model') from provider_settings order by id desc limit 1")).toBe(
    "dbpath-edge-model"
  );
  expect(
    readSqliteScalar(dbPath, "select json_extract(settings_json, '$.embedding.model') from provider_settings order by id desc limit 1")
  ).toBe("dbpath-embed-model");
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
    surfaces: ["CLI", "API", "MCP"]
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
  test.setTimeout(75_000);
  await page.goto("/");

  await page.getByRole("textbox", { name: "Evidence query" }).fill("doorbell interrupt disable");
  await page.getByRole("button", { name: "Run query" }).click();

  await expect(page.getByTestId("action-feedback")).toContainText("Query ran: doorbell interrupt disable", {
    timeout: 60_000
  });
  const resultsTable = page.getByRole("table", { name: "Evidence results" });
  await expect(resultsTable).not.toContainText("Loading live evidence");
  await expect(resultsTable).toContainText("DOORBELL");
  await expect(page.getByTestId("query-network-graph").getByTestId("force-graph")).toHaveAttribute(
    "data-node-count",
    /[1-9]\d*/
  );
  await expect(page.getByTestId("query-network-graph")).not.toContainText("No graph data returned");
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

test("query graph reports omitted graph payload instead of synthesizing static rows", async ({ page }) => {
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

  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("API_ONLY_REGISTER");
  await expect(page.getByLabel("Page metrics")).toContainText("graph edges: not returned");
  await expect(page.getByTestId("query-network-graph")).toContainText("No graph data returned.");
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

test("source filter controls constrain the free query request", async ({ page }) => {
  let requestedUrl = "";
  await page.route("**/api/workbench/query?**", async (route) => {
    requestedUrl = route.request().url();
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        queryId: "source_filtered_query",
        rows: [
          {
            source: "api",
            tone: "code",
            symbol: "CODE_ONLY_REGISTER",
            relation: "write",
            score: "0.91",
            path: "driver.c:8",
            source_type: "code"
          }
        ],
        graph: { nodes: [{ id: "CODE_ONLY_REGISTER", kind: "register" }], edges: [] },
        filters: { source_types: ["code"] }
      })
    });
  });
  await page.goto("/");

  await page.getByRole("button", { name: "Source filter Register" }).click();
  await page.getByRole("button", { name: "Source filter Doc" }).click();
  await page.getByRole("button", { name: "Source filter PDF" }).click();
  await expect(page.getByRole("button", { name: "Source filter Code" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("button", { name: "Source filter Register" })).toHaveAttribute("aria-pressed", "false");

  await page.getByRole("textbox", { name: "Evidence query" }).fill("source filtered register");
  await page.getByRole("button", { name: "Run query" }).click();

  const url = new URL(requestedUrl);
  expect(url.searchParams.get("sourceTypes")).toBe("code");
  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("CODE_ONLY_REGISTER");
});

test("graph page sends user configured semantic generation limits", async ({ page }) => {
  let requestBody: Record<string, unknown> = {};
  await page.route("**/api/workbench/semantic-edges", async (route) => {
    requestBody = route.request().postDataJSON();
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        candidate_count: 7,
        edge_count: 2,
        graph: {
          nodes: [{ id: "LIMITED_SEMANTIC_NODE", kind: "register", weight: 1 }],
          edges: []
        }
      })
    });
  });
  await page.goto("/graph");

  await page.getByRole("spinbutton", { name: "Semantic candidate limit" }).fill("7");
  await page.getByRole("spinbutton", { name: "Semantic batch size" }).fill("2");
  await page.getByRole("button", { name: "Generate batch semantic edges" }).click();

  expect(requestBody).toMatchObject({ mode: "batch", limit: 7, batchSize: 2 });
  await expect(page.getByTestId("action-feedback")).toContainText("Batch semantic edges generated: 2 from 7 candidates");
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
  await page.route("**/api/workbench/corpora**", async (route) => {
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
  await page.route("**/api/workbench/corpora**", async (route) => {
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

test("corpus page submits multiline subfolder filters as structured corpus metadata", async ({ page }) => {
  let createRequestBody: {
    id?: string;
    sourceRoot?: string;
    include?: string[];
    subfolders?: Array<{ relativeRoot?: string; include?: string[] }>;
  } = {};
  await page.route("**/api/workbench/corpora**", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({ corpora: [] })
      });
      return;
    }

    createRequestBody = route.request().postDataJSON() as typeof createRequestBody;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: createRequestBody.id,
        repo: "local",
        source_root: createRequestBody.sourceRoot,
        include: createRequestBody.include,
        file_count: 0,
        status: "not_indexed",
        metadata: {
          type: "code",
          subfolders: createRequestBody.subfolders?.map((subfolder) => ({
            relative_root: subfolder.relativeRoot,
            include: subfolder.include
          }))
        }
      })
    });
  });

  await page.goto("/corpus");
  await page.getByRole("textbox", { name: "Corpus id" }).fill("api-subfolder-corpus");
  await page.getByRole("textbox", { name: "Source root" }).fill("/src/amd");
  await page.getByRole("textbox", { name: "Include globs" }).fill("**/*.c, **/*.h");
  await page
    .getByRole("textbox", { name: "Subfolder filters" })
    .fill("drivers/gpu/drm/amd/amdgpu: **/*.c, **/*.h\ndrivers/gpu/drm/amd/include/asic_reg: **/*.h");
  await page.getByRole("button", { name: "Add corpus" }).click();

  await expect.poll(() => createRequestBody).toMatchObject({
    id: "api-subfolder-corpus",
    sourceRoot: "/src/amd",
    include: ["**/*.c", "**/*.h"],
    subfolders: [
      { relativeRoot: "drivers/gpu/drm/amd/amdgpu", include: ["**/*.c", "**/*.h"] },
      { relativeRoot: "drivers/gpu/drm/amd/include/asic_reg", include: ["**/*.h"] }
    ]
  });
  await expect(page.getByText("Corpus api-subfolder-corpus added")).toBeVisible();
  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("api-subfolder-corpus");
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
  const dbPath = "/tmp/asip-corpus-index-action.db";
  let indexRequestBody: unknown = null;
  await page.route("**/api/workbench/corpora**", async (route) => {
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
        dbPath,
        documents: 1,
        chunks: 2,
        edges: 3
      })
    });
  });

  await page.goto(`/corpus?dbPath=${encodeURIComponent(dbPath)}`);

  await page.getByRole("checkbox", { name: "Index api-corpus-a" }).uncheck();
  await expect(page.getByRole("checkbox", { name: "Index api-corpus-b" })).toBeChecked();
  await page.getByRole("button", { name: "Run index" }).click();

  await expect.poll(() => indexRequestBody).toEqual({
    corpusIds: ["api-corpus-b"],
    resolverProfileIds: [],
    dbPath
  });
  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("api-corpus-b");
  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("indexed");
  await expect(page.getByTestId("action-feedback")).toContainText("api-corpus-b");
});

test("corpus page sends the selected resolver profiles with the index job", async ({ page }) => {
  let indexRequestBody: unknown = null;
  await page.route("**/api/workbench/corpora**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        corpora: [
          {
            id: "api-corpus-resolver",
            repo: "https://example.test/api-corpus-resolver",
            sourceRoot: "/api/corpus/resolver",
            include: ["**/*.c"],
            fileCount: 3,
            status: "not_indexed"
          }
        ]
      })
    });
  });
  await page.route("**/api/workbench/resolver-profiles", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        profiles: [
          {
            id: "amd-soc15",
            language: "cpp",
            wrappers: ["WREG32_SOC15"],
            path: "configs/resolvers/amd-soc15.yaml",
            enabled: true
          },
          {
            id: "amd-direct-mmio",
            language: "cpp",
            wrappers: ["WREG32"],
            path: "configs/resolvers/amd-direct-mmio.yaml",
            enabled: true
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
        corpusIds: ["api-corpus-resolver"],
        resolverProfileIds: ["amd-soc15"],
        dbPath: "data/asip.db",
        documents: 1,
        chunks: 2,
        edges: 3
      })
    });
  });

  await page.goto("/corpus");

  await expect(page.getByRole("checkbox", { name: "Use resolver profile amd-soc15" })).toBeChecked();
  await page.getByRole("checkbox", { name: "Use resolver profile amd-direct-mmio" }).uncheck();
  await page.getByRole("button", { name: "Run index" }).click();

  await expect.poll(() => indexRequestBody).toEqual({
    corpusIds: ["api-corpus-resolver"],
    resolverProfileIds: ["amd-soc15"]
  });
  await expect(page.getByTestId("action-feedback")).toContainText("amd-soc15");
});

test("corpus page shows durable index job lifecycle events", async ({ page }) => {
  await page.route("**/api/workbench/corpora**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        corpora: [
          {
            id: "api-job-corpus",
            repo: "local",
            sourceRoot: "/api/job/corpus",
            include: ["**/*.md"],
            fileCount: 1,
            status: "not_indexed"
          }
        ]
      })
    });
  });
  await page.route("**/api/workbench/jobs**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        jobs: [
          {
            id: 42,
            kind: "index",
            status: "succeeded",
            message: "Indexed 1 documents",
            metadata: { result_status: "indexed", corpus_ids: ["api-job-corpus"] },
            events: [
              { status: "queued", message: "Indexing api-job-corpus" },
              { status: "indexing", message: "Indexing api-job-corpus" },
              { status: "succeeded", message: "Indexed 1 documents" }
            ]
          }
        ]
      })
    });
  });
  await page.route("**/api/workbench/index", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        status: "indexed",
        jobId: 42,
        jobStatus: "succeeded",
        corpusIds: ["api-job-corpus"],
        dbPath: "data/asip.db",
        documents: 1,
        chunks: 1,
        edges: 1
      })
    });
  });

  await page.goto("/corpus");
  await page.getByRole("button", { name: "Run index" }).click();

  await expect(page.getByTestId("action-feedback")).toContainText("job 42 succeeded");
  await expect(page.getByTestId("job-runs-panel")).toContainText("job 42");
  await expect(page.getByTestId("job-runs-panel")).toContainText("queued -> indexing -> succeeded");
});

test("corpus page fetches index jobs from the URL dbPath", async ({ page }) => {
  const dbPath = "/tmp/asip-job-runs-dbpath.db";
  let jobsRequestUrl = "";
  await page.route("**/api/workbench/corpora**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ corpora: [] })
    });
  });
  await page.route("**/api/workbench/jobs**", async (route) => {
    jobsRequestUrl = route.request().url();
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ jobs: [] })
    });
  });

  await page.goto(`/corpus?dbPath=${encodeURIComponent(dbPath)}`);

  await expect.poll(() => jobsRequestUrl).toContain("/api/workbench/jobs");
  expect(new URL(jobsRequestUrl).searchParams.get("dbPath")).toBe(dbPath);
});

test("corpus page marks selected corpus failed when indexing fails", async ({ page }) => {
  await page.route("**/api/workbench/corpora**", async (route) => {
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

test("acceptance page runs configurable acceptance queries through the workbench API", async ({ page }) => {
  let requestBody: {
    dbPath?: string;
    outputJson?: string;
    outputMd?: string;
    queryIds?: string[];
    surfaces?: string[];
  } = {};
  await page.route("**/api/workbench/acceptance", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ runs: [] }) });
  });
  await page.route("**/api/workbench/acceptance/run", async (route) => {
    requestBody = route.request().postDataJSON() as typeof requestBody;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        source: "asip.acceptance",
        summary: { total: 2, passed: 2, partial: 0, failed: 0 },
        surfaces_checked: ["CLI", "API", "Web", "MCP"],
        queries: [
          { id: "AQ01", status: "pass", surfaces_checked: ["CLI", "API", "Web", "MCP"] },
          { id: "AQ09", status: "pass", surfaces_checked: ["CLI", "API", "Web", "MCP"] }
        ]
      })
    });
  });

  await page.goto("/acceptance");
  await page.getByRole("textbox", { name: "Acceptance query IDs" }).fill("AQ01, AQ09");
  await page.getByRole("textbox", { name: "Acceptance DB path" }).fill("/tmp/asip-ui-acceptance.db");
  await page.getByRole("textbox", { name: "Acceptance output JSON" }).fill("docs/qa/ui-acceptance.json");
  await page.getByRole("textbox", { name: "Acceptance output Markdown" }).fill("docs/qa/ui-acceptance.md");
  await page.getByRole("checkbox", { name: "Web surface" }).click();
  await page.getByRole("button", { name: "Run acceptance" }).click();

  await expect(page.getByTestId("action-feedback")).toContainText("Acceptance run passed: 2/2");
  expect(requestBody).toMatchObject({
    dbPath: "/tmp/asip-ui-acceptance.db",
    outputJson: "docs/qa/ui-acceptance.json",
    outputMd: "docs/qa/ui-acceptance.md",
    queryIds: ["AQ01", "AQ09"],
    surfaces: ["CLI", "API", "Web", "MCP"]
  });
});

test("acceptance page runs no-mock AQ01 through the real workbench API", async ({ page }) => {
  test.setTimeout(90_000);
  const root = mkdtempSync(path.join(tmpdir(), "asip-acceptance-no-mock-"));
  const dbPath = path.join(root, "acceptance.db");
  seedGraphNoMockDb(dbPath);
  const runRequests: Array<Record<string, unknown>> = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/workbench/acceptance/run")) {
      runRequests.push((request.postDataJSON() ?? {}) as Record<string, unknown>);
    }
  });

  await page.goto("/acceptance");
  await page.getByRole("textbox", { name: "Acceptance query IDs" }).fill("AQ01");
  await page.getByRole("textbox", { name: "Acceptance DB path" }).fill(dbPath);
  const responsePromise = page.waitForResponse(
    (response) => response.url().includes("/api/workbench/acceptance/run") && response.status() === 200,
    { timeout: 30_000 }
  );
  await page.getByRole("button", { name: "Run acceptance" }).click();
  const response = await responsePromise;
  const payload = (await response.json()) as {
    source?: string;
    db_path?: string;
    queries?: Array<{
      id?: string;
      row_count?: number;
      status?: string;
      missing_surfaces?: string[];
      surface_results?: Array<{ surface?: string; transport?: string; status?: string }>;
    }>;
  };

  expect(runRequests).toEqual([expect.objectContaining({ dbPath, queryIds: ["AQ01"], surfaces: ["CLI", "API", "MCP"] })]);
  expect(payload.source).toBe("asip.acceptance");
  expect(payload.db_path).toBe(dbPath);
  expect(payload.queries?.[0]).toMatchObject({
    id: "AQ01",
    status: "partial",
    missing_surfaces: ["Web"]
  });
  expect(payload.queries?.[0]?.row_count ?? 0).toBeGreaterThan(0);
  expect(payload.queries?.[0]?.surface_results ?? []).toEqual(
    expect.arrayContaining([
      expect.objectContaining({ surface: "CLI", transport: "core.query_evidence", status: "pass" }),
      expect.objectContaining({ surface: "API", transport: "fastapi.testclient.query", status: "pass" }),
      expect.objectContaining({ surface: "MCP", transport: "mcp.tool-direct.search_evidence", status: "pass" })
    ])
  );
  await expect(page.getByTestId("action-feedback")).toContainText("Acceptance run partial: 0/1");
  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("acceptance-live");
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
                surface_results: [
                  {
                    surface: "CLI",
                    transport: "core.query_evidence",
                    status: "pass",
                    row_count: 24,
                    graph_node_count: 8,
                    graph_edge_count: 2,
                    message: "ok"
                  },
                  {
                    surface: "Web",
                    transport: "next-bff.query",
                    status: "not_configured",
                    row_count: 0,
                    graph_node_count: 0,
                    graph_edge_count: 0,
                    message: "ASIP_WEB_BASE_URL is not configured"
                  }
                ],
                sourcePaths: ["drivers/gpu/drm/amd/amdgpu/gfxhub_v11_5_0.c"],
                sourceTypes: ["code"],
                rowCount: 24,
                graphEdgeCount: 2,
                provider_checks: {
                  embedding: {
                    status: "pass",
                    provider: "openai-compatible",
                    model: "local-openai-embed",
                    message: "1 provider embedding, 0 fallback"
                  },
                  semantic_edge: {
                    status: "fail",
                    provider: "ollama",
                    model: "gemma4:e4b",
                    message: "semantic edge provider check failed: connection refused"
                  }
                },
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
  await expect(page.getByText("CLI core.query_evidence pass: rows 24, graph 8 nodes / 2 edges")).toBeVisible();
  await expect(page.getByText("Web next-bff.query not_configured: ASIP_WEB_BASE_URL is not configured")).toBeVisible();
  await expect(page.getByText("embedding pass: openai-compatible / local-openai-embed")).toBeVisible();
  await expect(page.getByText("semantic edge fail: ollama / gemma4:e4b")).toBeVisible();
  await expect(page.getByText("semantic edge provider check failed: connection refused")).toBeVisible();
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
  const root = mkdtempSync(path.join(tmpdir(), "asip-ui-corpus-state-"));
  const dbPath = path.join(root, "corpus-state.db");
  await page.goto(`/corpus?dbPath=${encodeURIComponent(dbPath)}`);

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
  const dbPath = path.join(root, "ui-clean-flow.db");
  const docsRoot = path.join(root, "docs");
  mkdirSync(docsRoot, { recursive: true });
  const uniqueId = `ui-full-loop-${Date.now()}`;
  const uniqueSymbol = `UI_FULL_LOOP_REGISTER_${Date.now()}`;
  writeFileSync(
    path.join(docsRoot, "note.md"),
    `${uniqueSymbol} sets UI_FULL_LOOP_FIELD before browser validation.`,
    "utf8"
  );
  await routeWorkbenchDbPath(page, dbPath);

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
  await expect(page.getByTestId("action-feedback")).toContainText(`Query ran: ${uniqueSymbol}`, { timeout: 30_000 });
  await expect(resultsTable).not.toContainText("Loading live evidence");
  await expect(resultsTable).toContainText(uniqueSymbol);
  await expect(resultsTable).toContainText("note.md", { timeout: 30_000 });
  await expect(page.getByLabel("Page metrics")).toContainText("graph edges: 1");
  const graph = page.getByTestId("force-graph");
  await expect(graph).toHaveAttribute("data-node-count", "2");
  await expect(graph).toHaveAttribute("data-edge-count", "1");
  await expect(graph).toContainText("doc 1");
  await expect(graph).toContainText("register 1");
  await expect(graph).toContainText(uniqueSymbol);
  await expect(page.getByRole("heading", { name: `Resolved Evidence: ${uniqueSymbol}` })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Source Location" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Source Preview" })).toBeVisible();
  await expect(page.getByText("doc function docs/note.md line 1")).toBeVisible();
});

test("resolver page adds configurable profiles", async ({ page }) => {
  await page.goto("/resolver-profiles");

  await expect(page.getByRole("textbox", { name: "Profile id" })).toHaveValue("initial");
  await expect(page.getByRole("textbox", { name: "Wrapper symbol" })).toHaveValue("RREG32");
  await expect(page.getByRole("textbox", { name: "Config path" })).toHaveValue("configs/resolvers/initial.yaml");
  await page.getByRole("button", { name: "Save resolver profile" }).click();

  const resultsTable = page.getByRole("table", { name: "Evidence results" });
  await expect(resultsTable).toContainText("initial");
  await expect(resultsTable).toContainText("operators");
  await expect(resultsTable.locator("tbody tr").first().locator("td").nth(1)).not.toContainText("RREG32");
  await expect(page.getByText("Resolver profile initial saved")).toBeVisible();
});

test("resolver page validates configurable profiles from user source", async ({ page }) => {
  const symbol = `UI_DYNAMIC_REGISTER_${Date.now()}`;
  await page.goto("/resolver-profiles");

  await page.getByRole("button", { name: "Save resolver profile" }).click();
  await expect(page.getByText("Resolver profile initial saved")).toBeVisible();

  await page.getByRole("textbox", { name: "Validation source" }).fill(`RREG32(${symbol});`);
  await page.getByRole("button", { name: "Validate resolver profile" }).click();

  await expect(page.getByText(`Resolver profile initial validated ${symbol}`)).toBeVisible();
});

test("resolver page sends configurable concept normalization rules", async ({ page }) => {
  const postBodies: unknown[] = [];
  await page.route("**/api/workbench/resolver-profiles", async (route) => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON();
      postBodies.push(body);
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          id: body.id,
          language: body.language,
          wrappers: body.wrappers,
          path: body.path,
          enabled: body.enabled,
          config: {
            graph: {
              function_normalization: body.functionNormalization
            }
          }
        })
      });
      return;
    }
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ profiles: [] }) });
  });

  await page.goto("/resolver-profiles");

  await page.getByRole("textbox", { name: "Profile id" }).fill("inline-concepts");
  await page.getByRole("textbox", { name: "Wrapper symbol" }).fill("CUSTOM_WRITE");
  await page.getByRole("checkbox", { name: "Enable concept normalization" }).check();
  await page.getByRole("textbox", { name: "Concept rule id" }).fill("inline-ip-versioned-functions");
  await page
    .getByRole("textbox", { name: "Concept match regex" })
    .fill("^(?P<ip_block>gfxhub)_rev(?P<ip_version>\\d+)_(?P<operation>.+)$");
  await page.getByRole("textbox", { name: "Concept canonical name" }).fill("inline_{operation}");
  await page.getByRole("button", { name: "Save resolver profile" }).click();

  expect(postBodies).toContainEqual(
    expect.objectContaining({
      id: "inline-concepts",
      wrappers: ["CUSTOM_WRITE"],
      functionNormalization: {
        enabled: true,
        rules: [
          expect.objectContaining({
            id: "inline-ip-versioned-functions",
            canonical: "inline_{operation}"
          })
        ]
      }
    })
  );
  await expect(page.getByText("Resolver profile inline-concepts saved")).toBeVisible();
});

test("resolver page can add disabled profiles with visible status", async ({ page }) => {
  await page.goto("/resolver-profiles");

  await page.getByRole("checkbox", { name: "Enable resolver profile" }).uncheck();
  await page.getByRole("button", { name: "Save resolver profile" }).click();

  const resultsTable = page.getByRole("table", { name: "Evidence results" });
  await expect(resultsTable).toContainText("initial");
  await expect(resultsTable).toContainText("operators");
  await expect(resultsTable.locator("tbody tr").first().locator("td").nth(1)).not.toContainText("RREG32");
  await expect(resultsTable).toContainText("disabled");
});

test("resolver page loads an existing profile into the editor before saving", async ({ page }) => {
  const postBodies: unknown[] = [];
  await page.route("**/api/workbench/resolver-profiles", async (route) => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON();
      postBodies.push(body);
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          id: body.id,
          language: body.language,
          wrappers: body.wrappers,
          path: body.path,
          enabled: body.enabled
        })
      });
      return;
    }
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        profiles: [
          {
            id: "initial",
            language: "cpp",
            wrappers: ["RREG32"],
            path: "configs/resolvers/initial.yaml",
            enabled: true
          },
          {
            id: "linux-amdgpu",
            language: "cpp",
            wrappers: ["WREG32_SOC15"],
            path: "configs/resolvers/linux-amdgpu.yaml",
            enabled: true
          }
        ]
      })
    });
  });

  await page.goto("/resolver-profiles");

  await page.getByRole("combobox", { name: "Existing resolver profile" }).click();
  await page.getByRole("option", { name: "linux-amdgpu" }).click();
  await page.getByRole("button", { name: "Load resolver profile" }).click();

  await expect(page.getByRole("textbox", { name: "Profile id" })).toHaveValue("linux-amdgpu");
  await expect(page.getByRole("textbox", { name: "Wrapper symbol" })).toHaveValue("WREG32_SOC15");
  await expect(page.getByRole("textbox", { name: "Config path" })).toHaveValue("configs/resolvers/linux-amdgpu.yaml");

  await page.getByRole("checkbox", { name: "Enable resolver profile" }).uncheck();
  await page.getByRole("button", { name: "Save resolver profile" }).click();

  expect(postBodies).toContainEqual(
    expect.objectContaining({
      id: "linux-amdgpu",
      wrappers: ["WREG32_SOC15"],
      path: "configs/resolvers/linux-amdgpu.yaml",
      enabled: false
    })
  );
  await expect(page.getByText("Resolver profile linux-amdgpu saved")).toBeVisible();
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

  const resultsTable = page.getByRole("table", { name: "Evidence results" });
  await expect(resultsTable).toContainText("api-resolver");
  await expect(resultsTable.locator("tbody tr").first().locator("td").nth(1).locator("code")).toHaveText("api-resolver");
  await expect(resultsTable.locator("tbody tr").first().locator("td").nth(4)).toContainText("1 operator");
  await expect(resultsTable.locator("tbody tr").first().locator("td").nth(1)).not.toContainText("API_WRAPPER");
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
          { id: "API_GLOBAL_FUNCTION", kind: "function", weight: 2 }
        ],
        edges: [
          {
            src: "API_GLOBAL_FUNCTION",
            relation: "writes",
            dst: "API_GLOBAL_REGISTER",
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
  await expect(relationshipPanel).toContainText("API_GLOBAL_FUNCTION writes API_GLOBAL_REGISTER");
  await expect(relationshipPanel).not.toContainText("GCVM_L2_CNTL connects code");
  await expect(relationshipPanel).not.toContainText("Weighted global graph emphasizes");
});

test("graph page separates visible node caps from loaded function-view totals", async ({ page }) => {
  const requestedFunctionViews: string[] = [];

  await page.route("**/api/workbench/limits", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        graph: {
          edgeBudget: 2000,
          maxEdgeBudget: 2000,
          visibleNodeBudget: 1000,
          visibleEdgeBudget: 2000,
          minimumEdgeWeight: 0,
          accessibilitySummaryLimit: 8
        }
      })
    });
  });
  await page.route(/\/api\/workbench\/graph(?:\?|$)/, async (route) => {
    const url = new URL(route.request().url());
    const functionView = url.searchParams.get("functionView") === "implementation" ? "implementation" : "concept";
    const totalNodes = functionView === "implementation" ? 1008 : 1005;
    const nodes = Array.from({ length: totalNodes }, (_, index) => ({
      id: `function:test:${functionView}:node_${index}`,
      kind: "function",
      label: `${functionView}_node_${index}`,
      weight: index === 0 ? 4 : 1
    }));
    const edges = Array.from({ length: totalNodes - 1 }, (_, index) => ({
      src: `function:test:${functionView}:node_${index}`,
      relation: "calls",
      dst: `function:test:${functionView}:node_${index + 1}`,
      confidence: 0.9,
      weight: 0.9,
      stage: "deterministic",
      source: "test"
    }));

    requestedFunctionViews.push(functionView);
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ queryId: "global", nodes, edges, source: "networkx" })
    });
  });

  await page.goto("/graph");

  const controls = page.locator('[aria-label="Graph display controls"]');
  const forceGraph = page.getByTestId("force-graph");
  await expect(forceGraph).toHaveAttribute("data-ready", "true", { timeout: 20_000 });
  await expect(controls).toContainText("1000 visible / 1005 loaded");
  await expect(forceGraph).toContainText("visible nodes 1000 / loaded 1005");

  await chooseSelectOption(page, "Function view", "Implementation", true);

  await expect.poll(async () => Number(await forceGraph.getAttribute("data-node-total"))).toBe(1008);
  await expect(controls).toContainText("1000 visible / 1008 loaded");
  await expect(forceGraph).toContainText("visible nodes 1000 / loaded 1008");
  expect(requestedFunctionViews).toContain("concept");
  expect(requestedFunctionViews).toContain("implementation");
});

test("graph page uses URL dbPath for no-mock graph and query requests", async ({ page }) => {
  test.setTimeout(90_000);
  const root = mkdtempSync(path.join(tmpdir(), "asip-graph-no-mock-"));
  const dbPath = path.join(root, "graph.db");
  seedGraphNoMockDb(dbPath);
  const expectedDbParam = `dbPath=${encodeURIComponent(dbPath)}`;
  const graphRequestUrls: string[] = [];
  const queryRequestUrls: string[] = [];
  page.on("request", (request) => {
    const url = request.url();
    if (url.includes("/api/workbench/graph")) {
      graphRequestUrls.push(url);
    }
    if (url.includes("/api/workbench/query")) {
      queryRequestUrls.push(url);
    }
  });

  const graphResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/workbench/graph") &&
      response.url().includes(expectedDbParam) &&
      response.status() === 200,
    { timeout: 10_000 }
  );
  await page.goto(`/graph?dbPath=${encodeURIComponent(dbPath)}`);
  const graphResponse = await graphResponsePromise;
  const graphPayload = (await graphResponse.json()) as {
    nodes: Array<{
      id: string;
      kind?: string;
      label?: string;
      attr?: {
        doc_kind?: string;
        is_concept?: boolean;
        concept_implementations?: Array<{ function_name?: string; path?: string }>;
        raw_function_names?: string[];
        raw_implementation_count?: number;
      };
    }>;
    edges: Array<{ src: string; relation?: string; dst: string }>;
  };
  const globalNodeIds = new Set(graphPayload.nodes.map((node) => node.id));
  expect(graphPayload.nodes.length).toBeGreaterThan(0);
  expect(graphPayload.edges.length).toBeGreaterThan(0);
  expect(new Set(graphPayload.nodes.map((node) => node.kind))).toEqual(new Set(["function", "register", "doc"]));
  expect(globalNodeIds).toContain(
    "function:linux-amdgpu:concept:linux-amdgpu:amd-ip-versioned-functions:gfxhub_gart_enable"
  );
  expect(globalNodeIds).not.toContain(
    "function:linux-amdgpu:drivers/gpu/drm/amd/amdgpu/gfxhub_v11_5_0.c:gfxhub_v11_5_0_gart_enable"
  );
  const conceptFunction = graphPayload.nodes.find((node) =>
    node.id === "function:linux-amdgpu:concept:linux-amdgpu:amd-ip-versioned-functions:gfxhub_gart_enable"
  );
  expect(conceptFunction?.attr?.is_concept).toBe(true);
  expect(conceptFunction?.attr?.raw_implementation_count).toBeGreaterThanOrEqual(2);
  expect(conceptFunction?.attr?.concept_implementations).toEqual(
    expect.arrayContaining([
      expect.objectContaining({ function_name: "gfxhub_v11_5_0_gart_enable" }),
      expect.objectContaining({ function_name: "gfxhub_v12_0_gart_enable" })
    ])
  );
  expect(graphPayload.nodes).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        id: "docs/guide.md#programming-local-registers",
        kind: "doc",
        attr: expect.objectContaining({ doc_kind: "markdown_section" })
      })
    ])
  );

  const forceGraph = page.getByTestId("force-graph");
  await expect(forceGraph).toHaveAttribute("data-ready", "true", { timeout: 20_000 });
  expect(Number(await forceGraph.getAttribute("data-node-total"))).toBeGreaterThan(0);
  expect(Number(await forceGraph.getAttribute("data-edge-total"))).toBeGreaterThan(0);
  await expect.poll(async () => Number(await forceGraph.getAttribute("data-node-total"))).toBe(graphPayload.nodes.length);
  await expect.poll(async () => Number(await forceGraph.getAttribute("data-edge-total"))).toBe(graphPayload.edges.length);
  await expect(forceGraph).toContainText("doc 1");
  await expect(forceGraph).not.toContainText("doc_section");
  await expect(forceGraph).toContainText("gfxhub_gart_enable");
  await expect(forceGraph).not.toContainText("gfxhub_v11_5_0_gart_enable");
  await forceGraph.getByRole("button", { name: "gfxhub_gart_enable" }).click();
  await expect(page.getByRole("heading", { name: "Graph Node: gfxhub_gart_enable" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Node Detail" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Concept Generated From" })).toBeVisible();
  await expect(page.locator(".details-pane")).toContainText("gfxhub_v11_5_0_gart_enable");
  await expect(page.locator(".details-pane")).toContainText("gfxhub_v12_0_gart_enable");

  const implementationResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/workbench/graph") &&
      response.url().includes("functionView=implementation") &&
      response.url().includes(expectedDbParam) &&
      response.status() === 200,
    { timeout: 10_000 }
  );
  await chooseSelectOption(page, "Function view", "Implementation", true);
  const implementationResponse = await implementationResponsePromise;
  const implementationPayload = (await implementationResponse.json()) as {
    nodes: Array<{ id: string; kind?: string }>;
    edges: Array<{ src: string; relation?: string; dst: string }>;
  };
  const implementationNodeIds = new Set(implementationPayload.nodes.map((node) => node.id));
  expect(implementationNodeIds).toContain(
    "function:linux-amdgpu:drivers/gpu/drm/amd/amdgpu/gfxhub_v11_5_0.c:gfxhub_v11_5_0_gart_enable"
  );
  expect(implementationNodeIds).toContain(
    "function:linux-amdgpu:drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c:gfxhub_v12_0_gart_enable"
  );
  expect(implementationNodeIds).not.toContain(
    "function:linux-amdgpu:concept:linux-amdgpu:amd-ip-versioned-functions:gfxhub_gart_enable"
  );
  expect(implementationPayload.nodes.map((node) => node.id).sort()).not.toEqual(
    graphPayload.nodes.map((node) => node.id).sort()
  );
  await expect(forceGraph).toHaveAttribute("data-ready", "true", { timeout: 20_000 });
  await expect.poll(async () => Number(await forceGraph.getAttribute("data-node-total"))).toBe(
    implementationPayload.nodes.length
  );
  await expect.poll(async () => Number(await forceGraph.getAttribute("data-edge-total"))).toBe(
    implementationPayload.edges.length
  );
  await expect(forceGraph).toContainText("gfxhub_v11_5_0_gart_enable");
  await expect(forceGraph).toContainText("gfxhub_v12_0_gart_enable");
  await expect(forceGraph).not.toContainText("gfxhub_gart_enable");

  const queryResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/workbench/query") &&
      response.url().includes(expectedDbParam) &&
      response.url().includes("GCVM_L2_CNTL") &&
      response.status() === 200,
    { timeout: 10_000 }
  );
  await page.getByRole("textbox", { name: "Evidence query" }).fill("GCVM_L2_CNTL");
  await page.getByRole("button", { name: "Run query" }).click();
  const queryResponse = await queryResponsePromise;
  const queryPayload = (await queryResponse.json()) as {
    rows: Array<{ symbol?: string }>;
    graph: { nodes: Array<{ id?: string; kind?: string }>; edges: Array<{ src: string; dst: string }> };
  };
  expect(queryPayload.rows.length).toBeGreaterThan(0);
  expect(new Set(queryPayload.graph.nodes.map((node) => node.kind))).toEqual(new Set(["function", "register", "doc"]));
  const queryNodeIds = new Set(queryPayload.graph.nodes.map((node) => "id" in node ? String(node.id) : ""));
  expect(queryNodeIds).toContain("register:GC:GCVM_L2_CNTL");
  expect(queryNodeIds).not.toContain("register:GC:GCVM_L2_STATUS");
  expect(queryPayload.graph.edges.map((edge) => `${edge.src}->${edge.dst}`).sort()).not.toEqual(
    graphPayload.edges.map((edge) => `${edge.src}->${edge.dst}`).sort()
  );
  await expect(forceGraph).toHaveAttribute("data-ready", "true", { timeout: 20_000 });
  await expect.poll(async () => Number(await forceGraph.getAttribute("data-node-total"))).toBe(
    queryPayload.graph.nodes.length
  );
  await expect.poll(async () => Number(await forceGraph.getAttribute("data-edge-total"))).toBe(
    queryPayload.graph.edges.length
  );
  await expect(forceGraph).toContainText("GCVM_L2_CNTL");
  await expect(forceGraph).not.toContainText("GCVM_L2_STATUS");
  expect(graphRequestUrls.length).toBeGreaterThanOrEqual(2);
  expect(graphRequestUrls.every((url) => url.includes(expectedDbParam))).toBe(true);
  expect(queryRequestUrls.length).toBeGreaterThanOrEqual(1);
  expect(queryRequestUrls.every((url) => url.includes(expectedDbParam))).toBe(true);
  await expect(page.getByTestId("action-feedback")).toContainText("Query ran: GCVM_L2_CNTL");
});

test("graph page loads current data/asip.db through browser and API", async ({ page }) => {
  test.setTimeout(120_000);
  const repoRoot = path.resolve(process.cwd(), "../..");
  const dbPath = process.env.ASIP_BROWSER_E2E_DB_PATH || "data/asip.db";
  const dbFilePath = path.isAbsolute(dbPath) ? dbPath : path.join(repoRoot, dbPath);
  test.skip(!existsSync(dbFilePath), `current ASIP DB is missing: ${dbFilePath}`);

  const chunkCount = Number(readSqliteScalar(dbFilePath, "select count(*) from chunks"));
  const edgeCount = Number(readSqliteScalar(dbFilePath, "select count(*) from edges"));
  const latestIndexJobId = readSqliteScalar(
    dbFilePath,
    "select id from jobs where kind='index' and status in ('succeeded','indexed') order by id desc limit 1"
  );
  const latestGraphRebuildJobId = readSqliteScalar(
    dbFilePath,
    "select id from jobs where kind='graph_rebuild' and status='succeeded' order by id desc limit 1"
  );
  if (process.env.ASIP_BROWSER_E2E_LATEST_INDEX_JOB_ID) {
    expect(latestIndexJobId).toBe(process.env.ASIP_BROWSER_E2E_LATEST_INDEX_JOB_ID);
  }
  if (process.env.ASIP_BROWSER_E2E_LATEST_GRAPH_REBUILD_JOB_ID) {
    expect(latestGraphRebuildJobId).toBe(process.env.ASIP_BROWSER_E2E_LATEST_GRAPH_REBUILD_JOB_ID);
  }
  expect(chunkCount).toBeGreaterThan(100_000);
  expect(edgeCount).toBeGreaterThan(10_000);

  const expectedDbParam = `dbPath=${encodeURIComponent(dbPath)}`;
  const graphRequestUrls: string[] = [];
  page.on("request", (request) => {
    const url = request.url();
    if (url.includes("/api/workbench/graph")) {
      graphRequestUrls.push(url);
    }
  });

  const graphResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/workbench/graph") &&
      response.url().includes(expectedDbParam) &&
      response.status() === 200,
    { timeout: 30_000 }
  );
  await page.goto(`/graph?dbPath=${encodeURIComponent(dbPath)}`);
  const graphResponse = await graphResponsePromise;
  expect(new URL(graphResponse.url()).searchParams.get("functionView")).toBe("concept");
  const graphPayloadText = await graphResponse.text();
  const graphPayload = JSON.parse(graphPayloadText) as {
    source?: string;
    graph_runtime?: string;
    nodes: Array<{
      id?: string;
      kind?: string;
      label?: string;
      attr?: {
        is_concept?: boolean;
        concept_implementations?: Array<{ function_name?: string; path?: string }>;
        concept_implementation_count?: number;
        raw_function_names?: string[];
        raw_implementation_count?: number;
        source?: Array<{ corpus_id?: string; path?: string }>;
      };
    }>;
    edges: Array<{ src: string; relation?: string; dst: string; stage?: string }>;
  };
  expect(graphPayload.source).toBe("networkx");
  expect(graphPayload.graph_runtime).toBe("networkx");
  expect(graphPayload.nodes.length).toBeGreaterThanOrEqual(1000);
  expect(graphPayload.edges.length).toBeGreaterThanOrEqual(1000);
  const currentGraphKinds = new Set(graphPayload.nodes.map((node) => node.kind));
  expect(currentGraphKinds.has("function")).toBe(true);
  expect(currentGraphKinds.has("register")).toBe(true);
  expect([...currentGraphKinds].every((kind) => ["function", "register", "doc"].includes(String(kind)))).toBe(true);
  const wrapperHubIds = graphPayload.nodes.filter((node) => {
    const nid = String(node.id ?? "");
    return /^(?:WREG32|RREG32|WREG32_SOC15|RREG32_SOC15|WREG32_FIELD|AMDGV_WRITE_REG)\b/.test(nid);
  });
  expect(wrapperHubIds.length).toBe(0);
  expect(
    graphPayload.nodes.some((node) =>
      (node.attr?.source ?? []).some(
        (source) => source.corpus_id === "linux-amdgpu" && String(source.path ?? "").includes("drivers/gpu/drm/amd")
      )
    )
  ).toBe(true);
  expect(
    graphPayload.edges.some(
      (edge) => edge.stage === "semantic" || ["calls", "writes", "reads", "sets_field"].includes(edge.relation ?? "")
    )
  ).toBe(true);
  const currentDbConcept = graphPayload.nodes.find(
    (node) =>
      node.kind === "function" &&
      String(node.id ?? "").includes(":concept:") &&
      ((node.attr?.concept_implementations?.length ?? 0) > 0 || (node.attr?.raw_function_names?.length ?? 0) > 0)
  );
  expect(currentDbConcept).toBeTruthy();
  expect(currentDbConcept?.attr?.is_concept).toBe(true);
  expect(currentDbConcept?.attr?.raw_implementation_count ?? 0).toBeGreaterThan(1);
  expect(currentDbConcept?.attr?.concept_implementation_count ?? 0).toBeGreaterThan(1);
  expect(currentDbConcept?.attr?.raw_implementation_count ?? 0).toBeGreaterThanOrEqual(
    currentDbConcept?.attr?.concept_implementation_count ?? 0
  );
  expect(currentDbConcept?.attr?.concept_implementations?.length ?? 0).toBe(
    currentDbConcept?.attr?.concept_implementation_count
  );
  const currentDbConceptImplementation = currentDbConcept?.attr?.concept_implementations?.find((item) =>
    item.function_name
  );
  expect(currentDbConceptImplementation?.function_name).toBeTruthy();

  const forceGraph = page.getByTestId("force-graph");
  await expect(forceGraph).toHaveAttribute("data-ready", "true", { timeout: 30_000 });
  await expect.poll(async () => Number(await forceGraph.getAttribute("data-node-total"))).toBe(graphPayload.nodes.length);
  await expect.poll(async () => Number(await forceGraph.getAttribute("data-edge-total"))).toBe(graphPayload.edges.length);
  const currentDbConceptLabel = String(currentDbConcept?.label ?? currentDbConcept?.id ?? "");
  const readConceptHitTarget = async (): Promise<{ id?: string; label?: string; x?: number; y?: number } | null> => {
    const rawTargets = await forceGraph.getAttribute("data-canvas-hit-targets");
    const targets = rawTargets ? JSON.parse(rawTargets) : [];
    return targets.find(
      (target: { id?: string; label?: string; x?: number; y?: number }) =>
        target.id === currentDbConcept?.id || target.label === currentDbConceptLabel
    ) ?? null;
  };
  await expect
    .poll(async () => Boolean(await readConceptHitTarget()), { timeout: 30_000 })
    .toBe(true);
  const conceptHitTarget = await readConceptHitTarget();
  if (!conceptHitTarget || conceptHitTarget.x === undefined || conceptHitTarget.y === undefined) {
    throw new Error(`No canvas hit target for ${currentDbConceptLabel}`);
  }
  const conceptPoint = { x: conceptHitTarget.x, y: conceptHitTarget.y };
  const graphCanvas = forceGraph.locator("canvas");
  await graphCanvas.hover({ position: { x: conceptPoint.x, y: conceptPoint.y } });
  await expect(forceGraph).toHaveAttribute("data-hovered-canvas-node-id", String(currentDbConcept?.id));
  const hoveredCanvasNodeId = await forceGraph.getAttribute("data-hovered-canvas-node-id");
  await graphCanvas.click({ position: { x: conceptPoint.x, y: conceptPoint.y } });
  await expect(forceGraph).toHaveAttribute("data-last-node-select-source", "canvas-node-click");
  const selectionInput = await forceGraph.getAttribute("data-last-node-select-source");
  await expect(page.getByRole("heading", { name: `Graph Node: ${currentDbConceptLabel}` })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Node Detail" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Concept Generated From" })).toBeVisible();
  await expect(page.locator(".details-pane")).toContainText(String(currentDbConceptImplementation?.function_name));
  await expect(page.locator(".details-pane")).not.toContainText("more implementations");
  const graphPayloadSha256 = createHash("sha256").update(graphPayloadText).digest("hex");
  const conceptDetailProbe = {
    surface: "graph_page_concept_detail_selection",
    url: page.url(),
    db_path: dbPath,
    status: graphResponse.status(),
    node_count: graphPayload.nodes.length,
    edge_count: graphPayload.edges.length,
    response_sha256: graphPayloadSha256,
    latest_index_job_id: latestIndexJobId,
    latest_graph_rebuild_job_id: latestGraphRebuildJobId,
    selected_node_id: currentDbConcept?.id,
    selected_is_concept: currentDbConcept?.attr?.is_concept,
    selected_kind: currentDbConcept?.kind,
    selected_label: currentDbConceptLabel,
    implementation_count: currentDbConcept?.attr?.concept_implementation_count,
    listed_implementation_count: currentDbConcept?.attr?.concept_implementations?.length,
    raw_implementation_record_count: currentDbConcept?.attr?.raw_implementation_count,
    selected_implementation: currentDbConceptImplementation?.function_name,
    selection_input: selectionInput,
    hovered_canvas_node_id: hoveredCanvasNodeId,
    canvas_click_x: conceptPoint.x,
    canvas_click_y: conceptPoint.y,
    detail_heading: "Concept Generated From",
    detail_truncated: false
  };
  expect(graphRequestUrls.length).toBeGreaterThanOrEqual(1);
  expect(graphRequestUrls.every((url) => url.includes(expectedDbParam))).toBe(true);

  const directApiResponse = await page.goto(`/api/workbench/graph?dbPath=${encodeURIComponent(dbPath)}`);
  expect(directApiResponse).not.toBeNull();
  expect(directApiResponse?.status()).toBe(200);
  const directPayloadText = await page.locator("body").innerText();
  const directPayload = JSON.parse(directPayloadText) as {
    source?: string;
    graph_runtime?: string;
    nodes: Array<{ id?: string; kind?: string }>;
    edges: Array<{ src: string; dst: string }>;
  };
  expect(directPayload.source).toBe("networkx");
  expect(directPayload.graph_runtime).toBe("networkx");
  expect(directPayload.nodes.length).toBe(graphPayload.nodes.length);
  expect(directPayload.edges.length).toBe(graphPayload.edges.length);

  const currentDbProbes = [
    {
      surface: "graph_page_api_request",
      url: graphResponse.url(),
      db_path: dbPath,
      status: graphResponse.status(),
      node_count: graphPayload.nodes.length,
      edge_count: graphPayload.edges.length,
      response_sha256: graphPayloadSha256,
      latest_index_job_id: latestIndexJobId,
      latest_graph_rebuild_job_id: latestGraphRebuildJobId
    },
    {
      surface: "direct_api_graph_request",
      url: directApiResponse?.url() ?? "",
      db_path: dbPath,
      status: directApiResponse?.status() ?? 0,
      node_count: directPayload.nodes.length,
      edge_count: directPayload.edges.length,
      response_sha256: createHash("sha256").update(directPayloadText).digest("hex"),
      latest_index_job_id: latestIndexJobId,
      latest_graph_rebuild_job_id: latestGraphRebuildJobId
    },
    conceptDetailProbe
  ];
  console.log(`ASIP_BROWSER_CURRENT_DB_PROBE ${JSON.stringify(currentDbProbes)}`);
  await test.info().attach("asip-current-db-probes", {
    body: JSON.stringify(currentDbProbes, null, 2),
    contentType: "application/json"
  });
});

test("corpus page uses URL dbPath for list add and index without route rewriting", async ({ page }) => {
  test.setTimeout(90_000);
  const root = mkdtempSync(path.join(tmpdir(), "asip-corpus-url-dbpath-"));
  const dbPath = path.join(root, "corpus.db");
  const sourceRoot = path.join(root, "linux");
  const amdgpuRoot = path.join(sourceRoot, "drivers/gpu/drm/amd/amdgpu");
  const registerRoot = path.join(sourceRoot, "drivers/gpu/drm/amd/include/asic_reg");
  mkdirSync(amdgpuRoot, { recursive: true });
  mkdirSync(registerRoot, { recursive: true });
  writeFileSync(path.join(amdgpuRoot, "gfx.c"), "void program_url_dbpath(void) { WREG32(regURL_DBPATH_CNTL, 1); }\n", "utf8");
  writeFileSync(path.join(registerRoot, "url_11_0_0_offset.h"), "#define regURL_DBPATH_HEADER_ONLY 0x1234\n", "utf8");

  await page.goto(`/corpus?dbPath=${encodeURIComponent(dbPath)}`);
  await page.getByRole("textbox", { name: "Corpus id" }).fill("url-dbpath-corpus");
  await page.getByRole("textbox", { name: "Repository URL" }).fill("local");
  await page.getByRole("textbox", { name: "Source root" }).fill(sourceRoot);
  await page.getByRole("textbox", { name: "Include globs" }).fill("**/*.c, **/*.h");
  await page
    .getByRole("textbox", { name: "Subfolder filters" })
    .fill("drivers/gpu/drm/amd/amdgpu: **/*.c\ndrivers/gpu/drm/amd/include/asic_reg: **/*.h");
  await page.getByRole("button", { name: "Add corpus" }).click();

  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("url-dbpath-corpus");
  expect(readSqliteScalar(dbPath, "select count(*) from corpora where id='url-dbpath-corpus'")).toBe("1");

  await page.reload();
  await expect(page.getByRole("table", { name: "Evidence results" })).toContainText("url-dbpath-corpus");
  await page.getByRole("checkbox", { name: "Index url-dbpath-corpus" }).check();
  await page.getByRole("button", { name: "Run index" }).click();
  await expect(page.getByTestId("action-feedback")).toContainText("Index built");
  expect(Number(readSqliteScalar(dbPath, "select count(*) from documents where corpus_id='url-dbpath-corpus'"))).toBeGreaterThan(0);
  expect(readSqliteScalar(dbPath, "select count(*) from evidence where symbol='regURL_DBPATH_HEADER_ONLY'")).toBe("1");
});

test("graph page filters no-mock graph layers and shows edge provenance", async ({ page }) => {
  test.setTimeout(90_000);
  const root = mkdtempSync(path.join(tmpdir(), "asip-graph-controls-"));
  const dbPath = path.join(root, "graph.db");
  seedGraphNoMockDb(dbPath);
  const expectedDbParam = `dbPath=${encodeURIComponent(dbPath)}`;
  const graphRequestUrls: string[] = [];
  page.on("request", (request) => {
    const url = request.url();
    if (url.includes("/api/workbench/graph")) {
      graphRequestUrls.push(url);
    }
  });

  await page.goto(`/graph?dbPath=${encodeURIComponent(dbPath)}`);

  const graphPanel = page.getByTestId("global-network-graph");
  const forceGraph = page.getByTestId("force-graph");
  await expect(forceGraph).toHaveAttribute("data-ready", "true", { timeout: 20_000 });
  await expect(graphPanel).toContainText("deterministic_ast: 3");
  await expect(graphPanel).toContainText("concept_merge: 1");
  await expect(graphPanel).toContainText("semantic_doc_node: 1");
  await expect(graphPanel).toContainText("ollama/gemma4:e4b");
  await expect(graphPanel).toContainText("job 1");
  await expect(graphPanel.getByRole("checkbox", { name: "Graph relation documents" })).toBeChecked();
  await expect(graphPanel.getByRole("checkbox", { name: "Graph stage semantic" })).toBeChecked();
  await expect(graphPanel.getByRole("checkbox", { name: "Graph source ollama" })).toBeChecked();
  expect(await forceGraph.getAttribute("data-edge-count")).toBe("4");

  await graphPanel.getByRole("checkbox", { name: "Graph relation documents" }).click();
  await expect(forceGraph).toHaveAttribute("data-edge-count", "3");
  await expect(graphPanel).not.toContainText("semantic_doc_node: 1");

  await graphPanel.getByRole("checkbox", { name: "Graph relation documents" }).click();
  await expect(forceGraph).toHaveAttribute("data-edge-count", "4");

  const budgetResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/workbench/graph") &&
      response.url().includes(expectedDbParam) &&
      response.url().includes("limit=1") &&
      response.status() === 200,
    { timeout: 10_000 }
  );
  await setSliderToMinimum(page, "Loaded edge budget");
  await budgetResponsePromise;
  expect(graphRequestUrls.some((url) => url.includes(expectedDbParam) && url.includes("limit=1"))).toBe(true);
});

test("evidence page initial query uses URL dbPath without default DB fallback", async ({ page }) => {
  test.setTimeout(90_000);
  const root = mkdtempSync(path.join(tmpdir(), "asip-evidence-no-mock-"));
  const dbPath = path.join(root, "evidence.db");
  seedGraphNoMockDb(dbPath);
  const expectedDbParam = `dbPath=${encodeURIComponent(dbPath)}`;
  const queryRequestUrls: string[] = [];
  page.on("request", (request) => {
    const url = request.url();
    if (url.includes("/api/workbench/query")) {
      queryRequestUrls.push(url);
    }
  });

  const queryResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/workbench/query") &&
      response.url().includes(expectedDbParam) &&
      response.url().includes("GCVM_L2_CNTL") &&
      response.status() === 200,
    { timeout: 10_000 }
  );
  await page.goto(`/?q=GCVM_L2_CNTL&dbPath=${encodeURIComponent(dbPath)}`);
  const queryResponse = await queryResponsePromise;
  const queryPayload = (await queryResponse.json()) as {
    rows: Array<{ symbol?: string }>;
    graph: { nodes: Array<{ kind?: string }>; edges: Array<{ src: string; dst: string }> };
  };

  expect(queryPayload.rows.length).toBeGreaterThan(0);
  expect(new Set(queryPayload.graph.nodes.map((node) => node.kind))).toEqual(new Set(["function", "register", "doc"]));
  expect(queryRequestUrls.length).toBeGreaterThanOrEqual(1);
  expect(queryRequestUrls.every((url) => url.includes(expectedDbParam))).toBe(true);
  await expect(page.getByTestId("action-feedback")).toContainText("Query ran: GCVM_L2_CNTL");
});

test("graph page runs semantic edge generation through the workbench API", async ({ page }) => {
  const dbPath = "/tmp/asip-semantic-query-action.db";
  let requestBody: { dbPath?: string; q?: string; limit?: number } = {};
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
            { id: "UI_EDGE_FUNCTION", kind: "function", weight: 1 },
            { id: "UI_EDGE_REGISTER", kind: "register", weight: 1 },
          ],
          edges: [
            {
              src: "UI_EDGE_FUNCTION",
              relation: "sets_field",
              dst: "UI_EDGE_REGISTER",
              attr: { fields: ["ENABLE_L2_CACHE"] },
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

  await page.goto(`/graph?dbPath=${encodeURIComponent(dbPath)}`);
  await page.getByRole("textbox", { name: "Evidence query" }).fill("UI_EDGE_REGISTER UI_EDGE_FIELD");
  await page.getByRole("button", { name: "Generate semantic edges" }).click();

  expect(requestBody.dbPath).toBe(dbPath);
  expect(requestBody.q).toBe("UI_EDGE_REGISTER UI_EDGE_FIELD");
  expect(requestBody.limit).toBe(8);
  await expect(page.getByTestId("action-feedback")).toContainText("Semantic edges generated: 1");
  await expect(page.getByTestId("global-network-graph")).toContainText("UI_EDGE_REGISTER");
});

test("graph page runs batch semantic edge generation through the workbench API", async ({ page }) => {
  const dbPath = "/tmp/asip-semantic-batch-action.db";
  let requestBody: { dbPath?: string; mode?: string; batchSize?: number } = {};
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
            {
              id: "docs/guide.md#programming-local-registers",
              kind: "doc",
              weight: 1,
              attr: { doc_kind: "markdown_section" }
            },
            { id: "UI_BATCH_REGISTER", kind: "register", weight: 1 }
          ],
          edges: [
            {
              src: "docs/guide.md#programming-local-registers",
              relation: "documents",
              dst: "UI_BATCH_REGISTER",
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

  await page.goto(`/graph?dbPath=${encodeURIComponent(dbPath)}`);
  await expect(page.getByLabel("Graph display controls")).toContainText("Loaded edge budget");
  await page.getByRole("button", { name: "Generate batch semantic edges" }).click();

  expect(requestBody.dbPath).toBe(dbPath);
  expect(requestBody.mode).toBe("batch");
  if (requestBody.batchSize !== undefined) {
    expect(requestBody.batchSize).toBe(6);
  }
  await expect(page.getByTestId("action-feedback")).toContainText("Batch semantic edges generated: 1 from 2 candidates");
  await expect(page.getByTestId("global-network-graph")).toContainText("UI_BATCH_REGISTER");
});

test("graph page runs no-mock batch semantic edge generation against a supplied DB", async ({ page }) => {
  test.setTimeout(90_000);
  const edgeServer = await startFakeOllamaEdgeServer();
  const root = mkdtempSync(path.join(tmpdir(), "asip-ui-semantic-real-"));
  const dbPath = path.join(root, "semantic-real.db");
  const corpusRoot = path.join(root, "docs");
  mkdirSync(corpusRoot, { recursive: true });
  writeFileSync(
    path.join(corpusRoot, "semantic.md"),
    "# Programming local registers\nGCVM_L2_CNTL has field ENABLE_L2_CACHE in this UI semantic edge fixture.",
    "utf8"
  );
  seedProviderAcceptanceDb(dbPath, corpusRoot, edgeServer.baseUrl);

  const semanticRequests: Array<{ url: string; body: Record<string, unknown> }> = [];
  page.on("request", (request) => {
    if (!request.url().includes("/api/workbench/semantic-edges")) {
      return;
    }
    semanticRequests.push({
      url: request.url(),
      body: (request.postDataJSON() ?? {}) as Record<string, unknown>
    });
  });

  try {
    const responsePromise = page.waitForResponse(
      (response) => response.url().includes("/api/workbench/semantic-edges") && response.status() === 200,
      { timeout: 30_000 }
    );
    await page.goto(`/graph?dbPath=${encodeURIComponent(dbPath)}`);
    await page.getByRole("button", { name: "Generate batch semantic edges" }).click();
    const response = await responsePromise;
    const payload = (await response.json()) as {
      source?: string;
      edge_count?: number;
      provider?: string;
      model?: string;
      graph?: { nodes?: Array<{ kind?: string; id?: string }>; edges?: Array<{ relation?: string }> };
    };

    expect(payload).toMatchObject({
      source: "semantic_edge_batch_job",
      edge_count: 1,
      provider: "ollama",
      model: "gemma4:e4b"
    });
    expect((payload.graph?.nodes ?? []).some((node) => node.kind === "register")).toBe(true);
    const graphResponse = await page.request.get(
      `/api/workbench/graph?dbPath=${encodeURIComponent(dbPath)}&limit=all`
    );
    expect(graphResponse.ok()).toBe(true);
    const graphPayload = (await graphResponse.json()) as {
      nodes?: Array<{ kind?: string }>;
      edges?: Array<{ relation?: string; stage?: string }>;
    };
    expect(new Set((graphPayload.nodes ?? []).map((node) => node.kind))).toEqual(new Set(["doc", "register"]));
    expect(graphPayload.edges ?? []).toEqual(
      expect.arrayContaining([expect.objectContaining({ relation: "documents", stage: "semantic" })])
    );
    expect(semanticRequests).toHaveLength(1);
    expect(semanticRequests[0].body).toMatchObject({ dbPath, mode: "batch" });
    await expect(page.getByTestId("action-feedback")).toContainText("Batch semantic edges generated: 1", {
      timeout: 30_000
    });
    await expect(page.getByTestId("global-network-graph")).toContainText("GCVM_L2_CNTL");
  } finally {
    await new Promise<void>((resolve, reject) => {
      edgeServer.server.close((error) => (error ? reject(error) : resolve()));
    });
  }
});

test("graph page runs LLM document node extraction through the workbench API", async ({ page }) => {
  const dbPath = "/tmp/asip-doc-node-action.db";
  let requestBody: { dbPath?: string; mode?: string; batchSize?: number } = {};
  await page.route("**/api/workbench/semantic-edges", async (route) => {
    requestBody = route.request().postDataJSON() as typeof requestBody;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        source: "doc_node_batch_job",
        box_count: 1,
        edge_count: 2,
        candidate_count: 1,
        provider: "ollama",
        model: "gemma4:e4b",
        graph: {
          nodes: [
            {
              id: "docs/guide.md#programming-local-registers",
              kind: "doc",
              weight: 1,
              attr: { doc_kind: "markdown_section" }
            },
            {
              id: "docs/guide.md#box-l2-cache-control",
              kind: "doc",
              label: "L2 cache control",
              weight: 1,
              attr: { doc_kind: "boxmatrix_box" }
            },
            { id: "UI_DOC_REGISTER", kind: "register", weight: 1 }
          ],
          edges: [
            {
              src: "docs/guide.md#programming-local-registers",
              relation: "contains",
              dst: "docs/guide.md#box-l2-cache-control",
              confidence: 0.92,
              weight: 0.92
            },
            {
              src: "docs/guide.md#box-l2-cache-control",
              relation: "documents",
              dst: "UI_DOC_REGISTER",
              confidence: 0.9,
              weight: 0.9
            }
          ],
          source: "networkx",
          graph_runtime: "networkx"
        }
      })
    });
  });

  await page.goto(`/graph?dbPath=${encodeURIComponent(dbPath)}`);
  await expect(page.getByLabel("Graph display controls")).toContainText("Loaded edge budget");
  await page.getByRole("button", { name: "Extract document nodes" }).click();

  expect(requestBody.dbPath).toBe(dbPath);
  expect(requestBody.mode).toBe("doc-nodes");
  if (requestBody.batchSize !== undefined) {
    expect(requestBody.batchSize).toBe(6);
  }
  await expect(page.getByTestId("action-feedback")).toContainText("Document nodes extracted: 1 boxes, 2 edges from 1 candidates");
  await expect(page.getByTestId("global-network-graph")).toContainText("L2 cache control");
});

test("graph page runs blackbox profile generation and shows inspector profile", async ({ page }) => {
  const dbPath = "/tmp/asip-blackbox-action.db";
  let requestBody: { dbPath?: string; mode?: string; batchSize?: number } = {};
  await page.route("**/api/workbench/semantic-edges", async (route) => {
    requestBody = route.request().postDataJSON() as typeof requestBody;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        source: "blackbox_profile_batch_job",
        inventory_total: 4,
        candidate_count: 2,
        profile_count: 1,
        edge_count: 2,
        provider: "ollama",
        model: "gemma4:e4b",
        graph: {
          nodes: [
            {
              id: "function:test:driver.c:program_l2",
              kind: "function",
              label: "program_l2",
              weight: 1,
              attr: {
                blackbox: {
                  method: "blackbox_io",
                  inputs: ["GCVM_L2_CNTL enable request"],
                  outputs: ["writes GCVM_L2_CNTL"],
                  observed_behavior: "program_l2 writes the L2 control register",
                  explanation_layer: "explains cache setup behavior",
                  evidence: "program_l2 writes GCVM_L2_CNTL"
                },
                providers: ["ollama"],
                models: ["gemma4:e4b"],
                job_ids: ["12"],
                source: [{ corpus_id: "test", repo: "local", path: "driver.c" }]
              }
            },
            { id: "register:GC:GCVM_L2_CNTL", kind: "register", label: "GCVM_L2_CNTL", weight: 1 }
          ],
          edges: [
            {
              src: "function:test:driver.c:program_l2",
              relation: "writes",
              dst: "register:GC:GCVM_L2_CNTL",
              confidence: 0.82,
              weight: 0.82,
              stage: "semantic",
              source: "ollama",
              attr: {
                extractor: "blackbox_profiles",
                provider: "ollama",
                model: "gemma4:e4b",
                job_id: 12
              }
            }
          ],
          source: "networkx",
          graph_runtime: "networkx"
        }
      })
    });
  });

  await page.goto(`/graph?dbPath=${encodeURIComponent(dbPath)}`);
  await page.getByRole("button", { name: "Generate blackbox profiles" }).click();

  expect(requestBody.dbPath).toBe(dbPath);
  expect(requestBody.mode).toBe("blackbox-profiles");
  if (requestBody.batchSize !== undefined) {
    expect(requestBody.batchSize).toBe(1);
  }
  await expect(page.getByTestId("action-feedback")).toContainText(
    "Blackbox profiles generated: 1 profiles, 2 edges from 2/4 candidates"
  );
  await expect(page.getByTestId("global-network-graph")).toContainText("blackbox_profile: 1");
  await expect(page.getByTestId("global-network-graph")).toContainText("blackbox_relationship: 1");
  await page.getByTestId("force-graph").getByRole("button", { name: "program_l2" }).click();
  await expect(page.getByRole("heading", { name: "Opened Blackbox", exact: true })).toBeVisible();
  await expect(page.locator(".details-pane")).toContainText("Inputs: GCVM_L2_CNTL enable request");
  await expect(page.locator(".details-pane")).toContainText("Behavior: program_l2 writes the L2 control register");
  await expect(page.locator(".details-pane")).toContainText("Outputs: writes GCVM_L2_CNTL");
  await expect(page.locator(".details-pane")).toContainText("Explains: explains cache setup behavior");
  await expect(page.locator(".details-pane")).toContainText("Evidence: program_l2 writes GCVM_L2_CNTL");
  await expect(page.locator(".details-pane")).toContainText("Generated By: ollama gemma4:e4b job 12");
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
    if (request.method === "POST" && request.url === "/v1/embeddings") {
      let body = "";
      request.setEncoding("utf8");
      request.on("data", (chunk) => {
        body += chunk;
      });
      request.on("end", () => {
        let input: unknown[] = ["provider smoke"];
        try {
          const parsed = JSON.parse(body) as { input?: unknown[] | string };
          input = Array.isArray(parsed.input) ? parsed.input : [parsed.input ?? "provider smoke"];
        } catch {
          input = ["provider smoke"];
        }
        response.writeHead(200, { "Content-Type": "application/json" });
        response.end(
          JSON.stringify({
            data: input.map((_item, index) => ({
              index,
              embedding: [0.11 + index, 0.22, 0.33]
            }))
          })
        );
      });
      return;
    }
    if (request.method !== "POST" || request.url !== "/api/chat") {
      response.writeHead(404, { "Content-Type": "application/json" });
      response.end(JSON.stringify({ error: "not found" }));
      return;
    }
    let body = "";
    request.setEncoding("utf8");
    request.on("data", (chunk) => {
      body += chunk;
    });
    request.on("end", () => {
      let promptText = body;
      try {
        const parsed = JSON.parse(body) as { prompt?: string; messages?: Array<{ content?: string }> };
        promptText = [
          parsed.prompt ?? "",
          ...(parsed.messages ?? []).map((message) => message.content ?? "")
        ].join("\n");
      } catch {
        promptText = body;
      }
      const caseMatch = promptText.match(/^CASE\s+([^\n"]+)/m);
      const caseId = caseMatch?.[1]?.trim() || "provider-smoke";
      const isDocCase = caseId.includes(".md#");
      const edge = isDocCase
        ? {
            src: caseId,
            relation: "documents",
            dst: "GCVM_L2_CNTL",
            confidence: 0.9,
            evidence: "fixture"
        }
        : {
            src: "program_gcvm_l2",
            relation: "writes",
            dst: "GCVM_L2_CNTL",
            confidence: 0.9,
            evidence: "fixture"
          };
      response.writeHead(200, { "Content-Type": "application/json" });
      response.end(
        JSON.stringify({
          message: {
            content: JSON.stringify({
              cases: [
                {
                  id: caseId,
                  edges: [edge]
                }
              ]
            })
          }
        })
      );
    });
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
from asip.storage import AsipStore
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
            "base_url": edge_base_url,
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
store = AsipStore.connect(str(db_path))
semantic_job_id = store.start_job(
    "semantic_edges_batch",
    "seed AQ09 UI semantic edge provenance",
    metadata={"provider_settings": {"edge": {"provider": "ollama", "model": "gemma4:e4b"}}},
)
store.finish_job(semantic_job_id, "generated", "Generated 1 semantic edge")
doc_node_job_id = store.start_job(
    "doc_nodes_batch",
    "seed AQ09 UI doc-node provenance",
    metadata={"provider_settings": {"edge": {"provider": "ollama", "model": "gemma4:e4b"}}},
)
store.finish_job(doc_node_job_id, "generated", "Generated 1 doc-node edge")
store.add_edge(
    "AQ09_UI_SYMBOL",
    "ENABLE_PROVIDER_SWITCH",
    "relates_to",
    0.91,
    stage="semantic",
    source="ollama",
    provenance={
        "provider": "ollama",
        "model": "gemma4:e4b",
        "job_id": semantic_job_id,
        "extractor": "semantic_edges",
    },
)
store.add_edge(
    "docs/aq09.md#provider-acceptance",
    "AQ09_UI_SYMBOL",
    "documents",
    0.88,
    stage="semantic",
    source="ollama",
    provenance={
        "provider": "ollama",
        "model": "gemma4:e4b",
        "job_id": doc_node_job_id,
        "extractor": "doc_nodes",
    },
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

function seedGraphNoMockDb(dbPath: string) {
  const repoRoot = path.resolve(process.cwd(), "../..");
  const script = String.raw`
import sys
from pathlib import Path
from asip.storage import AsipStore

db_path = Path(sys.argv[1])
store = AsipStore.connect(str(db_path))
store.migrate()
store.add_edge(
    "program_gcvm_l2",
    "GCVM_L2_CNTL",
    "writes",
    0.97,
    stage="deterministic",
    source="clang_preprocess",
    path="drivers/gpu/drm/amd/amdgpu/gfx.c",
    provenance={
        "function": "program_gcvm_l2",
        "corpus_id": "ui-no-mock",
        "repo": "local",
        "path": "drivers/gpu/drm/amd/amdgpu/gfx.c",
        "ip": "GC",
        "line_start": 12,
        "line_end": 12,
    },
)
store.add_edge(
    "read_gcvm_l2_status",
    "GCVM_L2_STATUS",
    "reads",
    0.88,
    stage="deterministic",
    source="clang_ast",
    path="drivers/gpu/drm/amd/amdgpu/gfx.c",
    provenance={
        "function": "read_gcvm_l2_status",
        "corpus_id": "ui-no-mock",
        "repo": "local",
        "path": "drivers/gpu/drm/amd/amdgpu/gfx.c",
        "ip": "GC",
        "line_start": 18,
        "line_end": 18,
    },
)
code_document_id = store.add_document("ui-no-mock-code", "code", "acceptance-live.c")
code_chunk_id = store.add_chunk(
    code_document_id,
    "acceptance-live writes regGCVM_L2_CNTL and GCVM_L2_CNTL.",
    1,
    1,
)
for symbol in ["regGCVM_L2_CNTL", "GCVM_L2_CNTL"]:
    store.add_evidence(
        chunk_id=code_chunk_id,
        corpus_id="ui-no-mock-code",
        source_type="code",
        repo="local",
        path="acceptance-live.c",
        line_start=1,
        line_end=1,
        symbol=symbol,
        entity_type="register",
        access_type="writes",
        confidence=0.99,
        snippet="acceptance-live writes regGCVM_L2_CNTL.",
        resolved_chain="acceptance-live -> regGCVM_L2_CNTL",
    )
for function_name, ip_version in [
    ("gfxhub_v11_5_0_gart_enable", "11_5_0"),
    ("gfxhub_v12_0_gart_enable", "12_0"),
]:
    source_path = f"drivers/gpu/drm/amd/amdgpu/gfxhub_v{ip_version}.c"
    store.add_edge(
        function_name,
        "GCVM_L2_CNTL",
        "writes",
        0.95,
        stage="deterministic",
        source="clang_text_spans",
        path=source_path,
        provenance={
            "function": function_name,
            "corpus_id": "linux-amdgpu",
            "repo": "linux",
            "path": source_path,
            "ip": "GC",
            "ip_version": ip_version,
            "resolver_profile": "linux-amdgpu",
            "line_start": 22,
            "line_end": 22,
        },
    )
document_id = store.add_document("ui-no-mock-docs", "doc", "docs/guide.md")
chunk_id = store.add_chunk(
    document_id,
    "# Programming local registers\nGCVM_L2_CNTL is documented by this section.",
    1,
    2,
)
store.add_evidence(
    chunk_id=chunk_id,
    corpus_id="ui-no-mock-docs",
    source_type="doc",
    repo="local",
    path="docs/guide.md",
    line_start=2,
    line_end=2,
    symbol="GCVM_L2_CNTL",
    entity_type="register",
    access_type="mention",
    confidence=0.95,
    snippet="GCVM_L2_CNTL is documented by this section.",
    resolved_chain="doc section -> GCVM_L2_CNTL",
)
doc_nodes_job_id = store.start_job("doc_nodes_batch", "seed no-mock doc node edge")
store.finish_job(doc_nodes_job_id, "succeeded", "seeded no-mock doc node edge")
store.add_edge(
    "docs/guide.md#programming-local-registers",
    "GCVM_L2_CNTL",
    "documents_register",
    0.91,
    stage="semantic",
    source="ollama",
    path="docs/guide.md",
    provenance={
        "corpus_id": "ui-no-mock-docs",
        "repo": "local",
        "path": "docs/guide.md",
        "title": "Programming local registers",
        "ip": "GC",
        "provider": "ollama",
        "model": "gemma4:e4b",
        "job_id": doc_nodes_job_id,
        "extractor": "doc_nodes",
    },
)
`;
  const result = spawnSync("python3", ["-c", script, dbPath], {
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

function readSqliteScalar(dbPath: string, sql: string) {
  const result = spawnSync("sqlite3", [dbPath, sql], {
    encoding: "utf8"
  });
  expect(result.status, result.stderr || result.stdout).toBe(0);
  return result.stdout.trim();
}
