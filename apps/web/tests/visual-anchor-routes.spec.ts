import { expect, test } from "@playwright/test";

const pages = [
  { route: "/", pageId: "evidence-workbench", nav: "Evidence Search", anchor: "evidence-workbench.png" },
  { route: "/graph", pageId: "graph-explorer", nav: "Graph Explorer", anchor: "graph-explorer.png" },
  { route: "/corpus", pageId: "corpus", nav: "Corpus", anchor: "corpus.png" },
  {
    route: "/resolver-profiles",
    pageId: "resolver-profiles",
    nav: "Resolver Profiles",
    anchor: "resolver-profiles.png"
  },
  { route: "/acceptance", pageId: "acceptance-tests", nav: "Acceptance Tests", anchor: "acceptance-tests.png" },
  { route: "/settings", pageId: "settings", nav: "Settings", anchor: "settings.png" }
];

test.describe("visual anchor route readiness", () => {
  for (const pageCase of pages) {
    test(`${pageCase.pageId} has a real page for anchor ${pageCase.anchor}`, async ({ page }) => {
      if (pageCase.pageId === "graph-explorer") {
        await mockGraphRoute(page);
      }
      await page.goto(pageCase.route);

      await expect(page.getByTestId("asip-workbench")).toHaveAttribute("data-page-id", pageCase.pageId);
      await expect(page.getByRole("navigation", { name: "ASIP sections" })).toContainText(pageCase.nav);
      await expect(page.locator(".nav-item[aria-current='page']")).toHaveText(pageCase.nav);
      await expect(page.getByRole("table", { name: "Evidence results" })).toBeVisible();
      await expect(page.getByTestId("relationship-panel")).toBeVisible();
      await expect(page.locator("[data-testid='marketing-hero']")).toHaveCount(0);
      await expect(page.locator(".workbench-grid")).toHaveCSS("display", "grid");
      if (pageCase.pageId === "graph-explorer") {
        await expect(page.getByTestId("global-network-graph")).toBeVisible();
        await expect(page.getByTestId("force-graph")).toBeVisible();
        await expect(page.getByTestId("force-graph")).toHaveAttribute("role", "img");
        await expect(page.getByText("weighted connections")).toBeVisible();
        await expect(page.getByRole("slider", { name: "Minimum edge weight" })).toBeVisible();
        await expect(page.getByRole("slider", { name: "Visible nodes" })).toBeVisible();
        await expect(page.getByRole("slider", { name: "Visible edges" })).toBeVisible();
        await expect(page.getByTestId("force-graph")).toContainText(/edges \d+/);
        await expectForceGraphPainted(page);
      }
    });
  }
});

test("graph route renders API-backed weighted relation graph", async ({ page }) => {
  let graphApiRequested = false;
  await page.route("**/api/workbench/graph**", async (route) => {
    graphApiRequested = true;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        queryId: "GCVM_L2_CNTL",
        source: "sqlite",
        nodes: [
          { id: "API_GRAPH_FUNCTION", kind: "function", weight: 4 },
          {
            id: "API_GRAPH_REGISTER",
            kind: "register",
            weight: 3,
            attr: {
              source: [
                { corpus_id: "linux-amdgpu", path: "drivers/gpu/drm/amd/amdgpu/gfx_v11_0.c" },
                { corpus_id: "mxgpu", path: "libgv/core/hw/navi3/gfx_v11_0.c" }
              ]
            }
          },
          { id: "API_GRAPH_SECTION", kind: "doc", weight: 1, attr: { doc_kind: "markdown_section" } }
        ],
        edges: [
          { src: "API_GRAPH_FUNCTION", dst: "API_GRAPH_REGISTER", relation: "sets_field", confidence: 0.91, weight: 0.91, stage: "deterministic" },
          { src: "API_GRAPH_SECTION", dst: "API_GRAPH_REGISTER", relation: "documents", confidence: 0.28, weight: 0.28, stage: "semantic" }
        ]
      })
    });
  });

  await page.goto("/graph");

  const forceGraph = page.getByTestId("force-graph");
  await expect(forceGraph).toContainText("API_GRAPH_REGISTER");
  expect(graphApiRequested).toBe(true);
  await expect(forceGraph).toContainText("sets_field / 0.91");
  await expect(forceGraph).toContainText("documents / 0.28");
  await expect(page.getByTestId("global-network-graph")).toContainText("deterministic_ast: 1");
  await expect(page.getByTestId("global-network-graph")).toContainText("semantic_edge: 1");
  await expect(forceGraph).not.toContainText("maps_base / 0.68");
  await expect(forceGraph).toHaveAttribute("data-edge-count", "2");
  await expect(forceGraph).toHaveAttribute("data-shared-register-count", "1");
  await expect(forceGraph).toContainText("shared registers 1");
  const strongEdgeWeight = await forceGraph.getAttribute("data-strongest-weight");
  const weakEdgeWeight = await forceGraph.getAttribute("data-weakest-weight");
  expect(Number(strongEdgeWeight)).toBeGreaterThan(Number(weakEdgeWeight));
  await expectForceGraphPainted(page);
});

test("graph route requests global graph without a default seed and renders API_GLOBAL nodes", async ({ page }) => {
  await page.route("**/api/workbench/graph**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        queryId: "global",
        source: "networkx",
        graph_runtime: "networkx",
        nodes: [
          { id: "API_GLOBAL_FUNCTION", kind: "function", weight: 4 },
          { id: "API_GLOBAL_REGISTER", kind: "register", weight: 3 },
          { id: "API_GLOBAL_SECTION", kind: "doc", weight: 1, attr: { doc_kind: "markdown_section" } }
        ],
        edges: [
          {
            src: "API_GLOBAL_FUNCTION",
            dst: "API_GLOBAL_REGISTER",
            relation: "sets_field",
            confidence: 0.94,
            weight: 0.94
          },
          {
            src: "API_GLOBAL_SECTION",
            dst: "API_GLOBAL_REGISTER",
            relation: "documents",
            confidence: 0.82,
            weight: 0.82
          }
        ]
      })
    });
  });

  const graphRequestPromise = page.waitForRequest((request) => {
    return new URL(request.url()).pathname === "/api/workbench/graph";
  });
  await page.goto("/graph");
  const graphRequest = await graphRequestPromise;

  const requested = new URL(graphRequest.url());
  expect(requested.searchParams.has("seed")).toBe(false);
  expect(requested.searchParams.has("queryId")).toBe(false);
  expect(requested.toString()).not.toContain("DOORBELL_INTERRUPT_DISABLE");
  const forceGraph = page.getByTestId("force-graph");
  await expect(forceGraph).toContainText("API_GLOBAL_REGISTER");
  await expect(forceGraph).toContainText("API_GLOBAL_SECTION");
  await expect(forceGraph).toHaveAttribute("data-edge-count", "2");
  await expectForceGraphPainted(page);
});

test("graph route keeps a global node set instead of collapsing to a tiny seed preview", async ({ page }) => {
  const kinds = ["register", "function", "doc"] as const;
  const nodes = Array.from({ length: 18 }, (_, index) => ({
    id: `API_GLOBAL_NODE_${index + 1}`,
    kind: kinds[index % kinds.length],
    weight: 18 - index
  }));
  const edges = nodes.slice(1).map((node, index) => ({
    src: nodes[index].id,
    dst: node.id,
    relation: "relates_to",
    confidence: 0.95 - index * 0.03,
    weight: 0.95 - index * 0.03
  }));
  await page.route("**/api/workbench/graph**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        queryId: "global",
        source: "networkx",
        graph_runtime: "networkx",
        nodes,
        edges
      })
    });
  });

  await page.goto("/graph");

  await expect(page.getByTestId("force-graph")).toContainText("API_GLOBAL_NODE_18");
  await expect(page.getByTestId("force-graph")).toHaveAttribute("data-node-count", "18");
  await expectForceGraphPainted(page);
});

test("graph route does not truncate large API graph payloads in the canvas layer", async ({ page }) => {
  const kinds = ["register", "function", "doc"] as const;
  const nodes = Array.from({ length: 180 }, (_, index) => ({
    id: `API_LARGE_GRAPH_NODE_${index + 1}`,
    kind: kinds[index % kinds.length],
    weight: 180 - index
  }));
  const edges = Array.from({ length: 320 }, (_, index) => ({
    src: nodes[index % nodes.length].id,
    dst: nodes[(index * 7 + 13) % nodes.length].id,
    relation: "relates_to",
    confidence: 0.7,
    weight: 0.7
  })).filter((edge) => edge.src !== edge.dst);
  await page.route("**/api/workbench/graph**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        queryId: "global",
        source: "networkx",
        graph_runtime: "networkx",
        nodes,
        edges
      })
    });
  });

  await page.goto("/graph");

  const forceGraph = page.getByTestId("force-graph");
  await expect(forceGraph).toHaveAttribute("data-layout-profile", "dense");
  await expect(forceGraph).toHaveAttribute("data-node-count", String(nodes.length));
  await expect(forceGraph).toHaveAttribute("data-edge-count", String(edges.length));
  await expect(forceGraph).toContainText("API_LARGE_GRAPH_NODE_180");
  await expectForceGraphPainted(page);
});

test("desktop and mobile screenshots keep the workbench styled", async ({ page }) => {
  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 390, height: 844 }
  ]) {
    await page.setViewportSize(viewport);
    await page.goto("/");

    await expect(page.getByTestId("asip-workbench")).toBeVisible();
    await expect(page.locator(".workbench-grid")).toHaveCSS("display", "grid");
    await expect(page.getByRole("button", { name: "Run query" })).toBeVisible();
    await expect(page.getByTestId("relationship-panel")).toBeVisible();
  }
});

test("theme toggle supports light and dark modes by default", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("button", { name: "Switch to light theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect(page.locator(".workbench-grid")).toHaveCSS("display", "grid");
  await page.getByRole("button", { name: "Switch to dark theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});

test("light theme persists across route navigation", async ({ page }) => {
  await page.goto("/corpus");
  await page.getByRole("button", { name: "Switch to light theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");

  await page.getByRole("link", { name: "Resolver Profiles" }).click();

  await expect(page).toHaveURL(/\/resolver-profiles$/);
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect(page.getByRole("button", { name: "Switch to dark theme" })).toBeVisible();
  await expect.poll(async () => page.evaluate(() => window.localStorage.getItem("asip-theme"))).toBe("light");
});

test("all routes share the canonical anchor chrome baseline", async ({ page }) => {
  await page.setViewportSize({ width: 2048, height: 1280 });

  const expectedBaseline = {
    ".topbar": { x: 0, y: 0, width: 2048, height: 72 },
    ".sidebar": { x: 0, y: 72, width: 288 },
    ".center-pane": { x: 288, y: 72 },
    ".details-pane": { x: 1536, y: 72, width: 488 }
  } as const;

  const reference = new Map<string, number>();
  for (const pageCase of pages) {
    await page.goto(pageCase.route, { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("asip-workbench")).toHaveAttribute("data-page-id", pageCase.pageId);

    for (const selector of [".topbar", ".sidebar", ".center-pane", ".details-pane"]) {
      const box = await page.locator(selector).boundingBox();
      expect(box, `${pageCase.route} ${selector}`).not.toBeNull();
      if (!box) {
        continue;
      }

      const expected = expectedBaseline[selector as keyof typeof expectedBaseline] as Record<string, number>;
      for (const [key, value] of Object.entries({ x: box.x, y: box.y, width: box.width, height: box.height })) {
        const metric = `${selector}.${key}`;
        if (!reference.has(metric)) {
          reference.set(metric, value);
        }

        expect(value, `${pageCase.route} ${metric}`).toBeCloseTo(reference.get(metric) ?? value, 0);
        if (expected[key] !== undefined) {
          expect(value, `${pageCase.route} ${metric} hard baseline`).toBeCloseTo(expected[key], 0);
        }
      }
    }
  }
});

test("graph visualization stays visible in light and dark modes", async ({ page }) => {
  await mockGraphRoute(page);
  await page.goto("/graph");

  const graph = page.getByTestId("global-network-graph");
  const forceGraph = page.getByTestId("force-graph");

  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(graph).toBeVisible();
  await expect(forceGraph).toBeVisible();
  await expectForceGraphPainted(page);

  await page.getByRole("button", { name: "Switch to light theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect(graph).toBeVisible();
  await expect(forceGraph).toBeVisible();
  await expectForceGraphPainted(page);
});

async function mockGraphRoute(page: import("@playwright/test").Page) {
  await page.route("**/api/workbench/graph**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        queryId: "global",
        source: "networkx",
        graph_runtime: "networkx",
        nodes: [
          { id: "MOCK_GRAPH_FUNCTION", kind: "function", weight: 4 },
          { id: "MOCK_GRAPH_REGISTER", kind: "register", weight: 3 },
          { id: "MOCK_GRAPH_SECTION", kind: "doc", weight: 1, attr: { doc_kind: "markdown_section" } }
        ],
        edges: [
          {
            src: "MOCK_GRAPH_FUNCTION",
            dst: "MOCK_GRAPH_REGISTER",
            relation: "reads",
            confidence: 0.94,
            weight: 0.94
          },
          {
            src: "MOCK_GRAPH_SECTION",
            dst: "MOCK_GRAPH_REGISTER",
            relation: "documents",
            confidence: 0.72,
            weight: 0.72
          }
        ]
      })
    });
  });
}

async function expectForceGraphPainted(page: import("@playwright/test").Page) {
  const canvas = page.getByTestId("force-graph").locator("canvas").first();
  await expect(canvas).toBeVisible({ timeout: 15_000 });
  await expect
    .poll(
      async () =>
        canvas.evaluate((element) => {
          const graphCanvas = element as HTMLCanvasElement;
          const context = graphCanvas.getContext("2d");
          if (!context || graphCanvas.width === 0 || graphCanvas.height === 0) {
            return 0;
          }
          const pixels = context.getImageData(0, 0, graphCanvas.width, graphCanvas.height).data;
          let painted = 0;
          for (let index = 3; index < pixels.length; index += 64) {
            if (pixels[index] > 0) {
              painted += 1;
            }
          }
          return painted;
        }),
      { timeout: 10_000 }
    )
    .toBeGreaterThan(20);
}
