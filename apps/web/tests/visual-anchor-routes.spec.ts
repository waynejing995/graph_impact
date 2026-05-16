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
      await page.goto(pageCase.route);

      await expect(page.getByTestId("asip-workbench")).toHaveAttribute("data-page-id", pageCase.pageId);
      await expect(page.getByRole("navigation", { name: "ASIP sections" })).toContainText(pageCase.nav);
      await expect(page.locator(".nav-item[aria-current='page']")).toHaveText(pageCase.nav);
      await expect(page.getByRole("table", { name: "Evidence results" })).toBeVisible();
      await expect(page.getByTestId("relationship-panel")).toBeVisible();
      await expect(page.locator("[data-testid='marketing-hero']")).toHaveCount(0);
      await expect(page.locator("[data-testid='graph-canvas']")).toHaveCount(0);
      await expect(page.locator(".workbench-grid")).toHaveCSS("display", "grid");
      if (pageCase.pageId === "graph-explorer") {
        await expect(page.getByTestId("global-network-graph")).toBeVisible();
        await expect(page.getByLabel("Global weighted network graph")).toBeVisible();
        await expect(page.getByText("weighted connections")).toBeVisible();
        await expect(page.locator(".graph-edge-line").first()).toHaveAttribute("data-weight");
        await expect(page.locator(".graph-edge-label").first()).toContainText(/\/ 0\.\d{2}/);
      }
    });
  }
});

test("graph route renders API-backed weighted relation graph", async ({ page }) => {
  let graphApiRequested = false;
  await page.route(/\/api\/workbench\/graph(?:\?|$)/, async (route) => {
    graphApiRequested = true;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        queryId: "GCVM_L2_CNTL",
        source: "sqlite",
        nodes: [
          { id: "API_GRAPH_REGISTER", kind: "register", weight: 3 },
          { id: "API_GRAPH_FIELD", kind: "field", weight: 2 },
          { id: "API_GRAPH_PDF", kind: "pdf", weight: 1 }
        ],
        edges: [
          { src: "API_GRAPH_REGISTER", dst: "API_GRAPH_FIELD", relation: "api_sets_field", confidence: 0.91, weight: 0.91 },
          { src: "API_GRAPH_REGISTER", dst: "API_GRAPH_PDF", relation: "api_relates", confidence: 0.28, weight: 0.28 }
        ]
      })
    });
  });

  await page.goto("/graph");

  const strongEdgeWidth = await page.locator(".graph-edge-line--w5").evaluate((node) => {
    return Number.parseFloat(node.getAttribute("stroke-width") ?? "0");
  });
  const weakEdgeWidth = await page.locator(".graph-edge-line--w1").first().evaluate((node) => {
    return Number.parseFloat(node.getAttribute("stroke-width") ?? "0");
  });
  const strongEdgeWeight = await page.locator(".graph-edge-line--w5").getAttribute("data-weight");
  const weakEdgeWeight = await page.locator(".graph-edge-line--w1").first().getAttribute("data-weight");
  const centralNodeRadius = await page
    .locator(".graph-bubble--register circle")
    .first()
    .evaluate((node) => Number.parseFloat(node.getAttribute("r") ?? "0"));
  const peripheralNodeRadius = await page
    .locator(".graph-bubble--neutral circle")
    .evaluate((node) => Number.parseFloat(node.getAttribute("r") ?? "0"));

  expect(graphApiRequested).toBe(true);
  await expect(page.getByLabel("Global weighted network graph")).toContainText("API_GRAPH_REGISTER");
  await expect(page.getByLabel("Global weighted network graph")).toContainText("api_sets_field / 0.91");
  await expect(page.getByLabel("Global weighted network graph")).toContainText("api_relates / 0.28");
  await expect(page.getByLabel("Global weighted network graph")).not.toContainText("maps_base / 0.68");
  await expect(page.locator(".graph-edge-line")).toHaveCount(2);
  expect(Number(strongEdgeWeight)).toBeGreaterThan(Number(weakEdgeWeight));
  expect(strongEdgeWidth).toBeGreaterThan(weakEdgeWidth);
  expect(centralNodeRadius).toBeGreaterThan(peripheralNodeRadius);
});

test("graph route requests global graph without a default seed and renders API_GLOBAL nodes", async ({ page }) => {
  await page.route(/\/api\/workbench\/graph(?:\?|$)/, async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        queryId: "global",
        source: "networkx",
        graph_runtime: "networkx",
        nodes: [
          { id: "API_GLOBAL_REGISTER", kind: "register", weight: 3 },
          { id: "API_GLOBAL_FIELD", kind: "field", weight: 2 },
          { id: "API_GLOBAL_DOC", kind: "pdf", weight: 1 }
        ],
        edges: [
          {
            src: "API_GLOBAL_REGISTER",
            dst: "API_GLOBAL_FIELD",
            relation: "api_global_sets_field",
            confidence: 0.94,
            weight: 0.94
          },
          {
            src: "API_GLOBAL_REGISTER",
            dst: "API_GLOBAL_DOC",
            relation: "api_global_documented_by",
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
  await expect(page.getByLabel("Global weighted network graph")).toContainText("API_GLOBAL_REGISTER");
  await expect(page.getByLabel("Global weighted network graph")).toContainText("API_GLOBAL_FIELD");
  await expect(page.getByLabel("Global weighted network graph")).toContainText("API_GLOBAL_DOC");
  await expect(page.locator(".graph-edge-line")).toHaveCount(2);
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
    await page.goto(pageCase.route);

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
  await page.goto("/graph");

  const graph = page.getByTestId("global-network-graph");
  const graphSvg = page.getByLabel("Global weighted network graph");

  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(graph).toBeVisible();
  await expect(graphSvg).toBeVisible();

  await page.getByRole("button", { name: "Switch to light theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect(graph).toBeVisible();
  await expect(graphSvg).toBeVisible();
  await expect(page.locator(".graph-edge-line").first()).toHaveAttribute("data-weight");
});
