import { expect, test, type APIRequestContext } from "@playwright/test";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { tmpdir } from "node:os";
import { spawnSync } from "node:child_process";
import path from "node:path";

test("corpora API reads configured raw corpus state", async ({ request }) => {
  const response = await request.get("/api/workbench/corpora");

  expect(response.ok()).toBe(true);
  const body = (await response.json()) as {
    corpora: Array<{ id: string; repo: string; source_root: string; file_count: number; status: string; include: string[] }>;
  };

  expect(body.corpora).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        id: "mxgpu",
        repo: "https://github.com/amd/MxGPU-Virtualization",
        source_root: "/tmp/asip-mxgpu",
        status: expect.stringMatching(/not_indexed|indexed|indexing|failed/),
        include: expect.arrayContaining(["**/*.c"])
      }),
      expect.objectContaining({
        id: "linux-amdgpu",
        source_root: "/tmp/asip-linux-amdgpu",
        status: expect.stringMatching(/not_indexed|indexed|indexing|failed/)
      })
    ])
  );
});

test("corpora API persists user-added corpus state", async ({ request }) => {
  const root = mkdtempSync(path.join(tmpdir(), "asip-api-corpus-state-"));
  const dbPath = path.join(root, "corpus-state.db");
  const create = await request.post("/api/workbench/corpora", {
    data: {
      dbPath,
      id: "local-amd-docs",
      repo: "local",
      sourceRoot: "/docs/amd",
      include: ["**/*.md", "**/*.pdf"],
      type: "doc"
    }
  });
  expect(create.ok()).toBe(true);
  const created = (await create.json()) as { id: string; status: string; include: string[] };
  expect(created).toMatchObject({ id: "local-amd-docs", status: "not_indexed" });
  expect(created.include).toEqual(["**/*.md", "**/*.pdf"]);

  const list = await request.get(`/api/workbench/corpora?dbPath=${encodeURIComponent(dbPath)}`);
  const body = (await list.json()) as { corpora: Array<{ id: string; source_root: string; status: string }> };
  expect(body.corpora).toEqual(
    expect.arrayContaining([
      expect.objectContaining({ id: "local-amd-docs", source_root: "/docs/amd", status: "not_indexed" })
    ])
  );
});

test("corpora API persists user-added corpus subfolder filters", async ({ request }) => {
  const root = mkdtempSync(path.join(tmpdir(), "asip-api-subfolder-corpus-"));
  const dbPath = path.join(root, "subfolder-filters.db");

  const create = await request.post("/api/workbench/corpora", {
    data: {
      dbPath,
      id: "local-amd-sliced",
      repo: "local",
      sourceRoot: "/src/amd",
      include: ["**/*.c", "**/*.h"],
      type: "code",
      subfolders: [
        { relativeRoot: "drivers/gpu/drm/amd/amdgpu", include: ["**/*.c", "**/*.h"] },
        { path: "drivers/gpu/drm/amd/include/asic_reg", include: "**/*.h" }
      ]
    }
  });
  expect(create.ok()).toBe(true);
  const created = (await create.json()) as {
    id: string;
    metadata?: { subfolders?: Array<{ relative_root: string; include: string[] }> };
  };
  expect(created).toMatchObject({
    id: "local-amd-sliced",
    metadata: {
      subfolders: [
        { relative_root: "drivers/gpu/drm/amd/amdgpu", include: ["**/*.c", "**/*.h"] },
        { relative_root: "drivers/gpu/drm/amd/include/asic_reg", include: ["**/*.h"] }
      ]
    }
  });

  const list = await request.get(`/api/workbench/corpora?dbPath=${encodeURIComponent(dbPath)}`);
  expect(list.ok()).toBe(true);
  const body = (await list.json()) as {
    corpora: Array<{ id: string; metadata?: { subfolders?: Array<{ relative_root: string; include: string[] }> } }>;
  };
  expect(body.corpora).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        id: "local-amd-sliced",
        metadata: expect.objectContaining({
          subfolders: [
            { relative_root: "drivers/gpu/drm/amd/amdgpu", include: ["**/*.c", "**/*.h"] },
            { relative_root: "drivers/gpu/drm/amd/include/asic_reg", include: ["**/*.h"] }
          ]
        })
      })
    ])
  );
});

test("corpora API rejects unsafe subfolder filters outside the corpus root", async ({ request }) => {
  const root = mkdtempSync(path.join(tmpdir(), "asip-api-unsafe-subfolder-"));
  const dbPath = path.join(root, "unsafe-subfolder.db");

  const response = await request.post("/api/workbench/corpora", {
    data: {
      dbPath,
      id: "unsafe-subfolder-corpus",
      repo: "local",
      sourceRoot: "/src/amd",
      include: ["**/*.c"],
      type: "code",
      subfolders: ["../outside:**/*.c"]
    }
  });

  expect(response.status()).toBe(400);
  const body = (await response.json()) as { error?: string };
  expect(body.error).toContain("repo-relative");
});

test("index API honors user-added corpus subfolder filters", async ({ request }) => {
  const root = mkdtempSync(path.join(tmpdir(), "asip-api-subfolder-index-"));
  const dbPath = path.join(root, "subfolder-index.db");
  const sourceRoot = path.join(root, "linux");
  const amdgpuRoot = path.join(sourceRoot, "drivers/gpu/drm/amd/amdgpu");
  const asicRegRoot = path.join(sourceRoot, "drivers/gpu/drm/amd/include/asic_reg");
  const displayRoot = path.join(sourceRoot, "drivers/gpu/drm/amd/display");
  mkdirSync(amdgpuRoot, { recursive: true });
  mkdirSync(asicRegRoot, { recursive: true });
  mkdirSync(displayRoot, { recursive: true });
  writeFileSync(path.join(amdgpuRoot, "gfx.c"), "void program(void) { WREG32(regAPI_SUBFOLDER_CNTL, 1); }\n", "utf8");
  writeFileSync(path.join(asicRegRoot, "api_11_0_0_offset.h"), "#define regAPI_HEADER_ONLY_REGISTER 0x1234\n", "utf8");
  writeFileSync(path.join(displayRoot, "display.c"), "void display(void) { WREG32(regAPI_DISPLAY_ONLY_REGISTER, 1); }\n", "utf8");

  const create = await request.post("/api/workbench/corpora", {
    data: {
      dbPath,
      id: "linux-amdgpu-subfolders",
      repo: "local",
      sourceRoot,
      include: ["**/*.c"],
      type: "code",
      subfolders: [
        { relativeRoot: "drivers/gpu/drm/amd/amdgpu", include: ["**/*.c"] },
        { relativeRoot: "drivers/gpu/drm/amd/include/asic_reg", include: ["**/*.h"] }
      ]
    }
  });
  expect(create.ok()).toBe(true);

  const index = await request.post("/api/workbench/index", {
    data: { dbPath, corpusIds: ["linux-amdgpu-subfolders"] }
  });
  expect(index.ok()).toBe(true);
  const indexed = (await index.json()) as { files: number; jobStatus: string };
  expect(indexed.jobStatus).toBe("succeeded");
  expect(indexed.files).toBe(2);

  const headerQuery = await request.get(
    `/api/workbench/query?q=${encodeURIComponent("API_HEADER_ONLY_REGISTER")}&dbPath=${encodeURIComponent(dbPath)}`
  );
  expect(headerQuery.ok()).toBe(true);
  const headerBody = (await headerQuery.json()) as { rows: Array<{ symbol: string; path: string; source_type: string }> };
  expect(headerBody.rows).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        symbol: "regAPI_HEADER_ONLY_REGISTER",
        path: "drivers/gpu/drm/amd/include/asic_reg/api_11_0_0_offset.h",
        source_type: "register"
      })
    ])
  );

  const displayQuery = await request.get(
    `/api/workbench/query?q=${encodeURIComponent("API_DISPLAY_ONLY_REGISTER")}&dbPath=${encodeURIComponent(dbPath)}`
  );
  expect(displayQuery.ok()).toBe(true);
  const displayBody = (await displayQuery.json()) as { rows: Array<{ symbol: string }> };
  expect(displayBody.rows).toHaveLength(0);
});

test("corpus API indexes a clean named DB and returns query graph provenance for the new corpus", async ({ request }) => {
  const root = mkdtempSync(path.join(tmpdir(), "asip-api-clean-corpus-"));
  const corpusRoot = path.join(root, "corpus");
  mkdirSync(corpusRoot, { recursive: true });
  const dbPath = path.join(root, "clean-g04.db");
  writeFileSync(
    path.join(corpusRoot, "note.md"),
    "G04_CLEAN_FLOW_REGISTER sets G04_CLEAN_FLOW_FIELD and links clean corpus graph inspector proof.",
    "utf8"
  );

  const create = await request.post("/api/workbench/corpora", {
    data: {
      dbPath,
      id: "g04-clean-docs",
      repo: "local",
      sourceRoot: corpusRoot,
      include: ["**/*.md"],
      type: "doc"
    }
  });
  expect(create.ok()).toBe(true);

  const indexed = await request.post("/api/workbench/index", {
    data: { dbPath, corpusIds: ["g04-clean-docs"] }
  });
  expect(indexed.ok()).toBe(true);
  const indexBody = (await indexed.json()) as { status: string; corpusIds: string[]; jobStatus: string };
  expect(indexBody).toMatchObject({
    status: "indexed",
    jobStatus: "succeeded",
    corpusIds: ["g04-clean-docs"]
  });

  const queried = await request.get(
    `/api/workbench/query?q=${encodeURIComponent("G04_CLEAN_FLOW_REGISTER")}&dbPath=${encodeURIComponent(dbPath)}`
  );
  expect(queried.ok()).toBe(true);
  const payload = (await queried.json()) as {
    rows: Array<{ symbol: string; corpus_id: string; source_type: string; path: string }>;
    graph: {
      nodes: Array<{ id: string; kind?: string; label?: string; attr?: { source?: Array<{ corpus_id?: string; path?: string }> } }>;
      edges: Array<{ src: string; relation?: string; dst: string; source?: string }>;
    };
  };

  expect(payload.rows).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        symbol: "G04_CLEAN_FLOW_REGISTER",
        corpus_id: "g04-clean-docs",
        source_type: "doc",
        path: "note.md"
      })
    ])
  );
  expect(payload.graph.nodes).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        id: "note.md#lines-1",
        kind: "doc",
        attr: expect.objectContaining({
          doc_kind: "markdown_section",
          source: expect.arrayContaining([expect.objectContaining({ corpus_id: "g04-clean-docs", path: "note.md" })])
        })
      }),
      expect.objectContaining({
        label: "G04_CLEAN_FLOW_REGISTER",
        kind: "register",
        attr: expect.objectContaining({
          source: expect.arrayContaining([expect.objectContaining({ corpus_id: "g04-clean-docs", path: "note.md" })])
        })
      })
    ])
  );
  expect(payload.graph.edges).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        src: "note.md#lines-1",
        relation: "documents",
        dst: expect.stringContaining("G04_CLEAN_FLOW_REGISTER"),
        source: "query_matched_section"
      })
    ])
  );
});

test("index API passes selected resolver profiles into the indexing job", async ({ request }) => {
  const root = mkdtempSync(path.join(tmpdir(), "asip-index-resolver-profile-"));
  const corpusRoot = path.join(root, "corpus");
  mkdirSync(corpusRoot, { recursive: true });
  writeFileSync(
    path.join(corpusRoot, "soc15.c"),
    [
      "void program_soc15_profile(void) {",
      "  WREG32_SOC15(GC, 0, regSOC15_ONLY_CNTL, 1);",
      "}",
      "void program_direct_profile(void) {",
      "  WREG32(mmDIRECT_ONLY_CNTL, 1);",
      "}"
    ].join("\n"),
    "utf8"
  );
  const configPath = path.join(root, "config.json");
  writeFileSync(
    configPath,
    JSON.stringify(
      {
        name: "resolver-profile-selection",
        model: {
          provider: "ollama",
          preferred: "gemma4:e4b"
        },
        corpora: [
          {
            id: "resolver-profile-selection",
            repo: "local",
            default_source_root: corpusRoot,
            include: ["**/*.c"]
          }
        ],
        queries: []
      },
      null,
      2
    ),
    "utf8"
  );
  const dbPath = path.join(root, "resolver.db");

  const response = await request.post("/api/workbench/index", {
    data: {
      configPath,
      dbPath,
      resolverProfileIds: ["amd-soc15"]
    }
  });

  expect(response.ok()).toBe(true);
  const body = (await response.json()) as { resolverProfileIds?: string[]; edges?: number };
  expect(body.resolverProfileIds).toEqual(["amd-soc15"]);
  expect(body.edges ?? 0).toBeGreaterThan(0);

  const soc15Graph = await request.get(
    `/api/workbench/graph?seed=${encodeURIComponent("SOC15_ONLY_CNTL")}&dbPath=${encodeURIComponent(dbPath)}&hops=1`
  );
  expect(soc15Graph.ok()).toBe(true);
  const soc15Body = (await soc15Graph.json()) as { edges: Array<{ dst: string; src: string; relation: string }> };
  expect(soc15Body.edges).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        relation: "writes",
        dst: expect.stringContaining("SOC15_ONLY_CNTL")
      })
    ])
  );

  const directGraph = await request.get(
    `/api/workbench/graph?seed=${encodeURIComponent("DIRECT_ONLY_CNTL")}&dbPath=${encodeURIComponent(dbPath)}&hops=1`
  );
  expect(directGraph.ok()).toBe(true);
  const directBody = (await directGraph.json()) as { edges: Array<{ dst: string; src: string }> };
  expect(directBody.edges).toHaveLength(0);
});

test("query API ranks live SQLite evidence and graph edges for a free-form query", async ({ request }) => {
  const { dbPath } = await createIndexedRawFixture(request);
  const response = await request.get(
    `/api/workbench/query?q=${encodeURIComponent("LOCAL_TEST_CNTL field")}&dbPath=${encodeURIComponent(dbPath)}`
  );

  expect(response.ok()).toBe(true);
  const body = (await response.json()) as {
    queryId: string;
    source: string;
    rows: Array<{ symbol: string; relation: string; path: string; source_type: string; resolved_chain: string }>;
    graph: {
      nodes: Array<{ id: string; kind?: string; attr?: Record<string, unknown> }>;
      edges: Array<{ src: string; relation?: string; dst: string; confidence: number; weight: number }>;
    };
  };

  expect(body.source).toBe("sqlite");
  expect(body.rows).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        symbol: "LOCAL_TEST_CNTL",
        source_type: "code",
        path: "src/gfx.c"
      })
    ])
  );
  expect(body.queryId).toBeTruthy();
  expect(body.graph.nodes).toEqual(
    expect.arrayContaining([
      expect.objectContaining({ id: expect.stringContaining("LOCAL_TEST_CNTL"), kind: "register" }),
      expect.objectContaining({ id: expect.stringContaining("program_local_register"), kind: "function" })
    ])
  );
  expect(body.graph.edges).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        src: expect.stringContaining("program_local_register"),
        relation: "sets_field",
        dst: expect.stringContaining("LOCAL_TEST_CNTL")
      })
    ])
  );
  expect(body.graph.nodes.map((node) => node.id)).not.toContain("ENABLE_LOCAL_FIELD");
});

test("query API treats natural language register wildcards as graphable symbol prefixes", async ({ request }) => {
  const dbPath = createNlWildcardQueryDb();
  const response = await request.get(
    `/api/workbench/query?q=${encodeURIComponent("who will write/read CP_HQD_* regs")}&dbPath=${encodeURIComponent(dbPath)}`
  );

  expect(response.ok()).toBe(true);
  const body = (await response.json()) as {
    empty: boolean;
    rows: Array<{ symbol: string; target_symbol?: string; relation?: string; source_type?: string }>;
    graph: {
      nodes: Array<{ id: string; kind?: string }>;
      edges: Array<{ src: string; relation: string; dst: string }>;
    };
  };

  expect(body.empty).toBe(false);
  expect(body.rows.length).toBeGreaterThan(0);
  expect(["reads", "writes"]).toContain(body.rows[0].relation);
  expect(body.rows[0].source_type).toBe("code");
  expect(["gfx_hqd_readback", "gfx_mqd_program"]).toContain(body.rows[0].symbol);
  expect(body.rows.every((row) => row.symbol.startsWith("CP_HQD_") || row.target_symbol?.startsWith("CP_HQD_"))).toBe(true);
  expect(body.rows.map((row) => row.symbol)).not.toContain("CPM_CONTROL__REFCLK_REGS_GATE_ENABLE_MASK");
  expect(body.graph.nodes).toEqual(
    expect.arrayContaining([
      expect.objectContaining({ id: expect.stringContaining("CP_HQD_PQ_CONTROL"), kind: "register" }),
      expect.objectContaining({ id: expect.stringContaining("gfx_mqd_program"), kind: "function" }),
      expect.objectContaining({ id: expect.stringContaining("gfx_hqd_readback"), kind: "function" })
    ])
  );
  expect(body.graph.edges).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        src: expect.stringContaining("gfx_mqd_program"),
        relation: "writes",
        dst: expect.stringContaining("CP_HQD_PQ_CONTROL")
      }),
      expect.objectContaining({
        src: expect.stringContaining("gfx_hqd_readback"),
        relation: "reads",
        dst: expect.stringContaining("CP_HQD_PQ_CONTROL")
      })
    ])
  );
});

test("query API exposes matching PDF section node with page provenance", async ({ request }) => {
  const dbPath = createPdfSectionQueryDb();
  const response = await request.get(
    `/api/workbench/query?q=${encodeURIComponent("GCVM_L2_CNTL PDF page")}&dbPath=${encodeURIComponent(dbPath)}`
  );

  expect(response.ok()).toBe(true);
  const body = (await response.json()) as {
    graph: {
      nodes: Array<{ id: string; kind?: string; attr?: { source?: Array<{ page?: number; path?: string }> } }>;
      edges: Array<{ src: string; relation?: string; dst: string }>;
    };
  };

  expect(body.graph.nodes).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        id: "docs/manual.pdf#page-3",
        kind: "doc",
        attr: expect.objectContaining({
          doc_kind: "pdf_section",
          source: expect.arrayContaining([expect.objectContaining({ path: "docs/manual.pdf", page: 3 })])
        })
      })
    ])
  );
  expect(body.graph.edges).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        src: "docs/manual.pdf#page-3",
        relation: "documents",
        dst: expect.stringContaining("GCVM_L2_CNTL")
      })
    ])
  );
});

test("Web BFF and MCP agree for the same SQLite query, evidence row, and entity", async ({ request }) => {
  const { dbPath } = await createIndexedRawFixture(request);
  const queryText = "LOCAL_TEST_CNTL field";
  const symbol = "LOCAL_TEST_CNTL";
  const query = await request.get(
    `/api/workbench/query?q=${encodeURIComponent(queryText)}&dbPath=${encodeURIComponent(dbPath)}`
  );
  expect(query.ok()).toBe(true);
  const queryBody = (await query.json()) as {
    source: string;
    queryId: string;
    rows: Array<{ id: number; symbol: string; path: string; resolved_chain: string }>;
  };
  const evidenceId = queryBody.rows[0].id;
  const mcp = runMcpAgreementProbe(queryText, evidenceId, symbol, dbPath);

  expect(pickQueryAgreement(queryBody)).toEqual(pickQueryAgreement(mcp.query));

  const webDetail = await request.get(
    `/api/workbench/evidence/${evidenceId}?dbPath=${encodeURIComponent(dbPath)}`
  );
  expect(webDetail.ok()).toBe(true);
  const webBody = (await webDetail.json()) as {
    id: number;
    symbol: string;
    path: string;
    resolved_chain: string;
    resolved_chain_explanation: { steps: Array<{ label: string }> };
  };
  expect(pickEvidenceAgreement(webBody)).toEqual(pickEvidenceAgreement(mcp.detail));
  expect(webBody.resolved_chain_explanation.steps.map((step) => step.label)).toEqual(
    mcp.detail.resolved_chain_explanation.steps.map((step) => step.label)
  );

  const webEntity = await request.get(
    `/api/workbench/entities/${encodeURIComponent(symbol)}?dbPath=${encodeURIComponent(dbPath)}`
  );
  expect(webEntity.ok()).toBe(true);
  const webEntityBody = (await webEntity.json()) as {
    symbol: string;
    evidence: Array<{ id: number; symbol: string; path: string; resolved_chain: string }>;
    resolved_chains: string[];
    resolved_chain_explanations: Array<{ evidence_id: number; steps: Array<{ label: string }> }>;
    graph: { nodes: unknown[]; edges: unknown[] };
  };
  expect(webEntityBody.symbol).toBe(mcp.entity.symbol);
  expect(webEntityBody.evidence.map(pickEvidenceAgreement)).toEqual(mcp.entity.evidence.map(pickEvidenceAgreement));
  expect(webEntityBody.resolved_chains).toEqual(mcp.entity.resolved_chains);
  expect(webEntityBody.resolved_chain_explanations.map((item) => item.evidence_id)).toEqual(
    mcp.entity.resolved_chain_explanations.map((item) => item.evidence_id)
  );
  expect({
    nodes: webEntityBody.graph.nodes.length,
    edges: webEntityBody.graph.edges.length
  }).toEqual({
    nodes: mcp.entity.graph.nodes.length,
    edges: mcp.entity.graph.edges.length
  });

  const webGraph = await request.get(
    `/api/workbench/graph?seed=${encodeURIComponent(symbol)}&dbPath=${encodeURIComponent(dbPath)}`
  );
  expect(webGraph.ok()).toBe(true);
  const webGraphBody = (await webGraph.json()) as { nodes: unknown[]; edges: unknown[]; queryId: string };
  expect({
    queryId: webGraphBody.queryId,
    nodes: webGraphBody.nodes.length,
    edges: webGraphBody.edges.length
  }).toEqual({
    queryId: mcp.graph.queryId,
    nodes: mcp.graph.nodes.length,
    edges: mcp.graph.edges.length
  });
});

test("query API applies ASIC and IP metadata filters", async ({ request }) => {
  const response = await request.get("/api/workbench/query?q=CP_INT_CNTL_RING0&ipBlock=NO_SUCH_IP");

  expect(response.ok()).toBe(true);
  const body = (await response.json()) as {
    empty: boolean;
    rows: unknown[];
    filters: { ip_block: string };
  };

  expect(body.empty).toBe(true);
  expect(body.rows).toEqual([]);
  expect(body.filters.ip_block).toBe("NO_SUCH_IP");
});

test("query API does not implicitly index or fall back when reading an explicit empty DB", async ({ request }) => {
  const root = mkdtempSync(path.join(tmpdir(), "asip-read-query-"));
  const dbPath = path.join(root, "empty.db");
  createEmptySqliteDb(dbPath);

  const response = await request.get(
    `/api/workbench/query?q=${encodeURIComponent("GCVM_L2_CNTL")}&dbPath=${encodeURIComponent(dbPath)}`
  );
  const body = (await response.json()) as { rows: unknown[]; empty: boolean; source: string };

  expect(response.ok()).toBe(true);
  expect(body.rows).toEqual([]);
  expect(body.empty).toBe(true);
  expect(body.source).toBe("sqlite");
});

test("query API handles more than five real ASIP verification queries", async ({ request }) => {
  const { dbPath } = await createIndexedRawFixture(request);
  const queries = [
    "Who writes regLOCAL_TEST_CNTL?",
    "LOCAL_TEST_CNTL enable field",
    "ENABLE_LOCAL_FIELD set field",
    "WREG32_SOC15 local register write",
    "REG_SET_FIELD LOCAL_TEST_CNTL",
    "regLOCAL_TEST_CNTL ENABLE_LOCAL_FIELD",
  ];

  for (const query of queries) {
    const response = await request.get(`/api/workbench/query?q=${encodeURIComponent(query)}&dbPath=${encodeURIComponent(dbPath)}`);
    expect(response.ok(), query).toBe(true);
    const body = (await response.json()) as { queryId: string; rows: unknown[]; graph: { edges: unknown[] }; source: string };

    expect(body.source, query).toBe("sqlite");
    expect(body.rows.length, query).toBeGreaterThan(0);
    expect(body.graph.edges.length, query).toBeGreaterThan(0);
  }
});

test("acceptance API lists real qwen and gemma QA runs", async ({ request }) => {
  const response = await request.get("/api/workbench/acceptance");

  expect(response.ok()).toBe(true);
  const body = (await response.json()) as {
    runs: Array<{
      id: string;
      model: string;
      passed: number;
      failed: number;
      partial?: number;
      queryCount: number;
      artifactPath: string;
      details?: Array<{
        id: string;
        providerChecks?: {
          embedding?: { status?: string; provider?: string; model?: string };
          semanticEdge?: { status?: string; provider?: string; model?: string };
        };
      }>;
    }>;
  };

  expect(body.runs).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        id: "qwen35-strict-batch1",
        model: "qwen3.5:4b",
        passed: 6,
        failed: 3,
        queryCount: 9,
        artifactPath: "docs/qa/2026-05-16-full-corpus-edge-generation-qwen35-strict-batch1.json"
      }),
      expect.objectContaining({
        id: "gemma4-e4b-strict-batch1",
        model: "gemma4:e4b",
        passed: 7,
        failed: 2,
        queryCount: 9
      }),
      expect.objectContaining({
        id: "acceptance-clean-qwen35",
        model: "asip.acceptance",
        passed: 0,
        partial: 8,
        failed: 1,
        queryCount: 9,
        artifactPath: "docs/qa/2026-05-17-acceptance-clean-qwen35.json"
      }),
      expect.objectContaining({
        id: "acceptance-multisource-fixture",
        model: "asip.acceptance",
        passed: 2,
        partial: 0,
        failed: 0,
        queryCount: 2,
        artifactPath: "docs/qa/2026-05-17-acceptance-multisource-fixture.json"
      }),
      expect.objectContaining({
        id: "acceptance-clean-amd-gemma4-final-current",
        model: "asip.acceptance",
        passed: 9,
        partial: 0,
        failed: 0,
        queryCount: 9,
        artifactPath: "docs/qa/2026-05-18-acceptance-clean-amd-gemma4-final-current.json"
      }),
      expect.objectContaining({
        id: "acceptance-clean-amd-current",
        model: "asip.acceptance",
        passed: 9,
        partial: 0,
        failed: 0,
        queryCount: 9,
        artifactPath: "docs/qa/2026-05-19-acceptance-clean-amd-current.json"
      })
    ])
  );
  const providerRun = body.runs.find((run) => run.id === "acceptance-clean-amd-current");
  const aq09 = providerRun?.details?.find((detail) => detail.id === "AQ09");
  expect(aq09?.providerChecks?.embedding).toMatchObject({
    status: "pass",
    provider: "ollama",
    model: "nomic-embed-text:latest"
  });
  expect(aq09?.providerChecks?.semanticEdge).toMatchObject({
    status: "pass",
    provider: "ollama",
    model: "gemma4:e4b"
  });
});

test("acceptance run API executes selected acceptance queries", async ({ request }) => {
  test.setTimeout(90_000);
  const response = await request.post("/api/workbench/acceptance/run", {
    data: {
      queryIds: ["AQ01"],
      surfaces: ["CLI", "Web"]
    }
  });

  expect(response.ok()).toBe(true);
  const body = (await response.json()) as {
    source: string;
    summary: { total: number };
    surfaces_checked: string[];
    queries: Array<{ id: string; surfaces_checked: string[] }>;
  };

  expect(body.source).toBe("asip.acceptance");
  expect(body.summary.total).toBe(1);
  expect(body.surfaces_checked).toEqual(["CLI", "Web"]);
  expect(body.queries).toEqual([
    expect.objectContaining({
      id: "AQ01",
      surfaces_checked: ["CLI", "Web"]
    })
  ]);
});

test("workbench DB-backed APIs reject explicitly blank dbPath without falling back", async ({ request }) => {
  const blankQuery = `dbPath=${encodeURIComponent("  ")}`;
  const checks: Array<{
    label: string;
    request: () => Promise<{ status(): number; json(): Promise<unknown> }>;
  }> = [
    { label: "query", request: () => request.get(`/api/workbench/query?q=GCVM_L2_CNTL&${blankQuery}`) },
    { label: "graph", request: () => request.get(`/api/workbench/graph?seed=GCVM_L2_CNTL&${blankQuery}`) },
    { label: "corpora", request: () => request.get(`/api/workbench/corpora?${blankQuery}`) },
    { label: "resolver profiles", request: () => request.get(`/api/workbench/resolver-profiles?${blankQuery}`) },
    { label: "jobs", request: () => request.get(`/api/workbench/jobs?${blankQuery}`) },
    { label: "job detail", request: () => request.get(`/api/workbench/jobs/1?${blankQuery}`) },
    { label: "evidence detail", request: () => request.get(`/api/workbench/evidence/1?${blankQuery}`) },
    { label: "entity detail", request: () => request.get(`/api/workbench/entities/GCVM_L2_CNTL?${blankQuery}`) },
    { label: "provider settings", request: () => request.get(`/api/workbench/providers/settings?${blankQuery}`) },
    {
      label: "index",
      request: () => request.post("/api/workbench/index", { data: { dbPath: "  " } })
    },
    {
      label: "acceptance run",
      request: () => request.post("/api/workbench/acceptance/run", { data: { dbPath: "  ", queryIds: ["AQ01"] } })
    },
    {
      label: "semantic edges",
      request: () => request.post("/api/workbench/semantic-edges", { data: { dbPath: "  ", q: "GCVM_L2_CNTL" } })
    },
    {
      label: "corpus add",
      request: () =>
        request.post("/api/workbench/corpora", {
          data: { dbPath: "  ", id: "blank-dbpath-corpus", sourceRoot: "/tmp/asip-blank-dbpath" }
        })
    },
    {
      label: "provider save",
      request: () => request.post("/api/workbench/providers/settings", { data: { dbPath: "  ", edge: {} } })
    }
  ];

  for (const check of checks) {
    const response = await check.request();
    expect(response.status(), check.label).toBe(400);
    const body = (await response.json()) as { error?: string };
    expect(body.error, check.label).toContain("dbPath cannot be blank");
  }
});

test("acceptance run API exposes AQ09 provider provenance from configured edge and embedding settings", async ({ request }) => {
  const root = mkdtempSync(path.join(tmpdir(), "asip-aq09-api-"));
  const dbPath = path.join(root, "aq09.db");
  const corpusRoot = path.join(root, "docs");
  mkdirSync(corpusRoot, { recursive: true });
  writeFileSync(
    path.join(corpusRoot, "aq09.md"),
    [
      "Run embedding and optional semantic edge extraction through a configured Ollama provider.",
      "Then switch to an OpenAI compatible provider without changing retrieval or resolver code.",
      "AQ09_PROVIDER_SYMBOL keeps this provider acceptance document queryable."
    ].join("\n"),
    "utf8"
  );
  seedProviderAcceptanceDb(dbPath, corpusRoot);

  const response = await request.post("/api/workbench/acceptance/run", {
    data: {
      dbPath,
      queryIds: ["AQ09"],
      surfaces: ["CLI", "API", "MCP"]
    }
  });

  expect(response.ok()).toBe(true);
  const body = (await response.json()) as {
    provider_settings: {
      edge: { provider: string; base_url: string; model: string };
      embedding: { provider: string; base_url: string; model: string };
    };
    queries: Array<{
      id: string;
      row_count: number;
      provider_checks: {
        embedding: { status: string; provider: string; model: string; embedding_count: number; fallback_count: number };
        semantic_edge: { status: string; provider: string; model: string; message?: string };
      };
      failure_reasons: string[];
    }>;
  };

  expect(body.provider_settings.edge).toMatchObject({
    provider: "ollama",
    base_url: "http://127.0.0.1:9",
    model: "gemma4:e4b"
  });
  expect(body.provider_settings.embedding).toMatchObject({
    provider: "openai-compatible",
    base_url: "https://embedding.example.test",
    model: "local-openai-embed"
  });
  expect(body.queries).toHaveLength(1);
  const aq09 = body.queries[0];
  expect(aq09.id).toBe("AQ09");
  expect(aq09.row_count).toBeGreaterThan(0);
  expect(aq09.provider_checks.embedding).toMatchObject({
    status: "pass",
    provider: "openai-compatible",
    model: "local-openai-embed",
    embedding_count: 1,
    fallback_count: 0
  });
  expect(aq09.provider_checks.semantic_edge).toMatchObject({
    status: "fail",
    provider: "ollama",
    model: "gemma4:e4b"
  });
  expect(aq09.failure_reasons).toEqual(
    expect.arrayContaining([expect.stringContaining("semantic_edge provider check failed")])
  );
});

test("graph API returns data-driven weighted edges for a selected seed", async ({ request }) => {
  const { dbPath } = await createIndexedRawFixture(request);
  const response = await request.get(
    `/api/workbench/graph?seed=GCVM_L2_CNTL&hops=2&dbPath=${encodeURIComponent(dbPath)}`
  );

  expect(response.ok()).toBe(true);
  const body = (await response.json()) as {
    queryId: string;
    nodes: Array<{ id: string; kind: string; weight: number }>;
    edges: Array<{ src: string; relation: string; dst: string; confidence: number; weight: number }>;
  };

  expect(body.queryId).toBe("GCVM_L2_CNTL");
  expect(body.nodes).toEqual(
    expect.arrayContaining([
      expect.objectContaining({ id: expect.stringContaining("GCVM_L2_CNTL"), kind: "register" }),
      expect.objectContaining({ id: expect.stringContaining("program_gcvml2_register"), kind: "function" })
    ])
  );
  expect(body.nodes.map((node) => node.id)).not.toContain("ENABLE_L2_CACHE");
  expect(body.edges).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        src: expect.stringContaining("program_gcvml2_register"),
        relation: "sets_field",
        dst: expect.stringContaining("GCVM_L2_CNTL"),
        confidence: 0.97,
        weight: 0.97
      }),
      expect.objectContaining({
        src: expect.stringContaining("program_gcvml2_register"),
        relation: "reads",
        dst: expect.stringContaining("GCVM_L2_CNTL")
      })
    ])
  );
});

test("graph API can switch between concept and implementation function views", async ({ request }) => {
  const dbPath = createVersionedFunctionGraphDb();
  const conceptResponse = await request.get(
    `/api/workbench/graph?seed=GCVM_L2_CNTL&hops=1&functionView=concept&dbPath=${encodeURIComponent(dbPath)}`
  );
  const implementationResponse = await request.get(
    `/api/workbench/graph?seed=GCVM_L2_CNTL&hops=1&functionView=implementation&dbPath=${encodeURIComponent(dbPath)}`
  );

  expect(conceptResponse.ok()).toBe(true);
  expect(implementationResponse.ok()).toBe(true);
  const concept = (await conceptResponse.json()) as {
    nodes: Array<{ id: string; kind: string; attr?: { raw_function_names?: string[] } }>;
    edges: Array<{ src: string; dst: string; relation: string }>;
  };
  const implementation = (await implementationResponse.json()) as {
    nodes: Array<{ id: string; kind: string }>;
  };

  const conceptFunction = concept.nodes.find((node) => node.kind === "function");
  expect(conceptFunction?.id).toBe(
    "function:linux-amdgpu:concept:linux-amdgpu:amd-ip-versioned-functions:gfxhub_gart_enable",
  );
  expect(conceptFunction?.attr?.raw_function_names).toEqual(
    expect.arrayContaining(["gfxhub_v11_5_0_gart_enable", "gfxhub_v12_0_gart_enable"])
  );
  expect(concept.edges).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        src: "function:linux-amdgpu:concept:linux-amdgpu:amd-ip-versioned-functions:gfxhub_gart_enable",
        relation: "writes",
        dst: "register:GC:GCVM_L2_CNTL"
      })
    ])
  );

  const implementationIds = implementation.nodes.filter((node) => node.kind === "function").map((node) => node.id);
  expect(implementationIds).toEqual(
    expect.arrayContaining([
      "function:linux-amdgpu:drivers/gpu/drm/amd/amdgpu/gfxhub_v11_5_0.c:gfxhub_v11_5_0_gart_enable",
      "function:linux-amdgpu:drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c:gfxhub_v12_0_gart_enable"
    ])
  );
  expect(implementationIds.some((id) => id.includes(":concept:"))).toBe(false);
});

test("graph API returns compact metadata for global UI graphs", async ({ request }) => {
  const dbPath = createVersionedFunctionGraphDb();
  const response = await request.get(
    `/api/workbench/graph?limit=20&functionView=concept&dbPath=${encodeURIComponent(dbPath)}`
  );

  expect(response.ok()).toBe(true);
  const body = (await response.json()) as {
    metadata_mode?: string;
    nodes: Array<{
      id: string;
      kind: string;
      attr?: {
        is_concept?: boolean;
        concept_implementations?: Array<{ function_name?: string; path?: string }>;
        concept_implementation_count?: number;
        raw_function_names?: string[];
        raw_implementation_count?: number;
      };
    }>;
    edges: Array<{ src: string; dst: string; relation: string }>;
  };

  expect(body.metadata_mode).toBe("compact");
  expect(body.nodes.length).toBeGreaterThan(0);
  expect(body.edges.length).toBeGreaterThan(0);
  const conceptFunction = body.nodes.find(
    (node) =>
      node.id === "function:linux-amdgpu:concept:linux-amdgpu:amd-ip-versioned-functions:gfxhub_gart_enable"
  );
  expect(conceptFunction?.attr?.is_concept).toBe(true);
  expect(conceptFunction?.attr?.raw_implementation_count).toBeGreaterThanOrEqual(2);
  expect(conceptFunction?.attr?.concept_implementation_count).toBe(
    conceptFunction?.attr?.concept_implementations?.length
  );
  expect(conceptFunction?.attr?.raw_implementation_count ?? 0).toBeGreaterThanOrEqual(
    conceptFunction?.attr?.concept_implementation_count ?? 0
  );
  expect(conceptFunction?.attr?.raw_function_names).toEqual(
    expect.arrayContaining(["gfxhub_v11_5_0_gart_enable", "gfxhub_v12_0_gart_enable"])
  );
  expect(conceptFunction?.attr?.concept_implementations).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        function_name: "gfxhub_v11_5_0_gart_enable",
        path: expect.stringContaining("gfxhub_v11_5_0.c")
      }),
      expect.objectContaining({
        function_name: "gfxhub_v12_0_gart_enable",
        path: expect.stringContaining("gfxhub_v12_0.c")
      })
    ])
  );
  expect(JSON.stringify(body)).not.toContain("raw_implementations");
});

test("graph API rejects resolver operators as selected seed nodes", async ({ request }) => {
  const { dbPath } = await createIndexedRawFixture(request);
  const response = await request.get(
    `/api/workbench/graph?seed=REG_SET_FIELD&hops=2&dbPath=${encodeURIComponent(dbPath)}`
  );

  expect(response.ok()).toBe(true);
  const body = (await response.json()) as { queryId: string; nodes: unknown[]; edges: unknown[]; empty_state?: string };

  expect(body.queryId).toBe("REG_SET_FIELD");
  expect(body.nodes).toEqual([]);
  expect(body.edges).toEqual([]);
  expect(body.empty_state).toContain("resolver operator");
});

test("workbench limits API exposes graph budgets from repo config", async ({ request }) => {
  const response = await request.get("/api/workbench/limits");

  expect(response.ok()).toBe(true);
  const body = (await response.json()) as {
    graph?: { edgeBudget?: number; visibleNodeBudget?: number; visibleEdgeBudget?: number };
    semantic?: { queryLimit?: number; batchCandidateLimit?: number; batchSize?: number };
  };

  expect(body.graph?.edgeBudget).toBeGreaterThan(0);
  expect(body.graph?.visibleNodeBudget).toBeGreaterThan(0);
  expect(body.graph?.visibleEdgeBudget).toBeGreaterThan(0);
  expect(body.semantic?.queryLimit).toBeGreaterThan(0);
  expect(body.semantic?.batchCandidateLimit).toBeGreaterThan(0);
  expect(body.semantic?.batchSize).toBeGreaterThan(0);
});

test("graph API global view can derive explicit evidence overlay from indexed evidence", async ({ request }) => {
  const { dbPath } = await createIndexedRawFixture(request);
  const response = await request.get(
    `/api/workbench/graph?dbPath=${encodeURIComponent(dbPath)}&limit=120&includeEvidenceDerived=1`
  );

  expect(response.ok()).toBe(true);
  const body = (await response.json()) as {
    queryId: string;
    nodes: Array<{ id: string; kind: string; weight: number }>;
    edges: Array<{ src: string; relation: string; dst: string; confidence: number; weight: number }>;
  };

  expect(body.queryId).toBe("global");
  expect(body.nodes).toEqual(
    expect.arrayContaining([
      expect.objectContaining({ id: expect.stringContaining("LOCAL_TEST_CNTL"), kind: "register" }),
      expect.objectContaining({ id: expect.stringContaining("program_local_register"), kind: "function" })
    ])
  );
  expect(body.nodes.map((node) => node.kind)).not.toContain("field");
  expect(body.nodes.map((node) => node.id)).not.toContain("src/gfx.c");
  expect(body.edges).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        src: expect.stringContaining("program_local_register"),
        relation: "sets_field",
        dst: expect.stringContaining("LOCAL_TEST_CNTL")
      })
    ])
  );
  expect(body.edges.every((edge) => edge.weight > 0)).toBe(true);
});

test("graph API does not implicitly index or fall back when reading an explicit empty DB", async ({ request }) => {
  const root = mkdtempSync(path.join(tmpdir(), "asip-read-graph-"));
  const dbPath = path.join(root, "empty.db");
  createEmptySqliteDb(dbPath);

  const response = await request.get(`/api/workbench/graph?seed=GCVM_L2_CNTL&dbPath=${encodeURIComponent(dbPath)}`);
  const body = (await response.json()) as { nodes: Array<{ id: string }>; edges: unknown[]; graph_runtime?: string };

  expect(response.ok()).toBe(true);
  expect(body.nodes).toEqual([expect.objectContaining({ id: "GCVM_L2_CNTL" })]);
  expect(body.edges).toEqual([]);
  expect(body.graph_runtime).toBe("networkx");
});

test("semantic edges API generates graph edges from a supplied DB", async ({ request }) => {
  const edgeServer = await startFakeOllamaEdgeServer();
  const root = mkdtempSync(path.join(tmpdir(), "asip-edge-api-"));
  const dbPath = path.join(root, "edges.db");
  const corpusRoot = path.join(root, "docs");
  mkdirSync(corpusRoot, { recursive: true });
  writeFileSync(
    path.join(corpusRoot, "edge.md"),
    "GCVM_L2_CNTL has field ENABLE_L2_CACHE in this semantic edge API fixture.",
    "utf8"
  );
  seedProviderAcceptanceDb(dbPath, corpusRoot, edgeServer.baseUrl);

  try {
    const response = await request.post("/api/workbench/semantic-edges", {
      data: {
        dbPath,
        q: "GCVM_L2_CNTL ENABLE_L2_CACHE"
      }
    });

    expect(response.ok()).toBe(true);
    const body = (await response.json()) as {
      source: string;
      edge_count: number;
      provider: string;
      model: string;
      graph: {
        nodes: Array<{ id: string; kind?: string; attr?: Record<string, unknown> }>;
        edges: Array<{ src: string; relation: string; dst: string; weight: number }>;
      };
    };
    expect(body).toMatchObject({
      source: "semantic_edge_job",
      edge_count: 1,
      provider: "ollama",
      model: "gemma4:e4b"
    });
    expect(body.graph.nodes).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: expect.stringContaining("GCVM_L2_CNTL"),
          kind: "register",
          attr: expect.objectContaining({ fields: expect.arrayContaining(["ENABLE_L2_CACHE"]) })
        })
      ])
    );
    expect(body.graph.edges).toEqual([]);
  } finally {
    await new Promise<void>((resolve, reject) => {
      edgeServer.server.close((error) => (error ? reject(error) : resolve()));
    });
  }
});

test("semantic edges API supports batch generation from indexed candidates", async ({ request }) => {
  const edgeServer = await startFakeOllamaEdgeServer();
  const root = mkdtempSync(path.join(tmpdir(), "asip-edge-batch-api-"));
  const dbPath = path.join(root, "edges.db");
  const corpusRoot = path.join(root, "docs");
  mkdirSync(corpusRoot, { recursive: true });
  writeFileSync(
    path.join(corpusRoot, "edge.md"),
    "# Programming local registers\nGCVM_L2_CNTL has field ENABLE_L2_CACHE in this batch semantic edge fixture.",
    "utf8"
  );
  seedProviderAcceptanceDb(dbPath, corpusRoot, edgeServer.baseUrl);

  try {
    const response = await request.post("/api/workbench/semantic-edges", {
      data: {
        dbPath,
        mode: "batch",
        limit: 4,
        batchSize: 2,
        includeEvidenceDerived: true
      }
    });

    expect(response.ok()).toBe(true);
    const body = (await response.json()) as {
      source: string;
      edge_count: number;
      candidate_count: number;
      provider: string;
      model: string;
      graph: { nodes: Array<{ id: string; kind: string }>; edges: Array<{ src: string; relation: string; dst: string }> };
    };
    expect(body).toMatchObject({
      source: "semantic_edge_batch_job",
      edge_count: 1,
      provider: "ollama",
      model: "gemma4:e4b"
    });
    expect(body.candidate_count).toBeGreaterThan(0);
    expect(body.graph.nodes).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "edge.md#programming-local-registers",
          kind: "doc",
          attr: expect.objectContaining({ doc_kind: "markdown_section" })
        })
      ])
    );
    expect(body.graph.edges).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          src: "edge.md#programming-local-registers",
          relation: "documents",
          dst: expect.stringContaining("GCVM_L2_CNTL")
        })
      ])
    );
  } finally {
    await new Promise<void>((resolve, reject) => {
      edgeServer.server.close((error) => (error ? reject(error) : resolve()));
    });
  }
});

test("semantic edges API supports LLM document node extraction", async ({ request }) => {
  const edgeServer = await startFakeOllamaEdgeServer();
  const root = mkdtempSync(path.join(tmpdir(), "asip-doc-node-api-"));
  const dbPath = path.join(root, "edges.db");
  const corpusRoot = path.join(root, "docs");
  mkdirSync(corpusRoot, { recursive: true });
  writeFileSync(
    path.join(corpusRoot, "edge.md"),
    "# Programming local registers\nGCVM_L2_CNTL has field ENABLE_L2_CACHE in this doc node fixture.",
    "utf8"
  );
  seedProviderAcceptanceDb(dbPath, corpusRoot, edgeServer.baseUrl);

  try {
    const response = await request.post("/api/workbench/semantic-edges", {
      data: {
        dbPath,
        mode: "doc-nodes",
        limit: 2,
        batchSize: 1
      }
    });

    expect(response.ok()).toBe(true);
    const body = (await response.json()) as {
      source: string;
      box_count: number;
      edge_count: number;
      graph: { nodes: Array<{ id: string; kind: string; label?: string }>; edges: Array<{ src: string; relation: string; dst: string }> };
    };
    expect(body.source).toBe("doc_node_batch_job");
    expect(body.box_count).toBe(1);
    expect(body.edge_count).toBe(2);
    expect(body.graph.nodes).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "edge.md#box-l2-cache-control",
          kind: "doc",
          attr: expect.objectContaining({ doc_kind: "boxmatrix_box" }),
          label: "L2 cache control"
        })
      ])
    );
    expect(body.graph.edges).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          src: "edge.md#programming-local-registers",
          relation: "contains",
          dst: "edge.md#box-l2-cache-control"
        })
      ])
    );
  } finally {
    await new Promise<void>((resolve, reject) => {
      edgeServer.server.close((error) => (error ? reject(error) : resolve()));
    });
  }
});

function createEmptySqliteDb(dbPath: string) {
  const result = spawnSync(
    "python3",
    ["-c", "import sqlite3, sys; sqlite3.connect(sys.argv[1]).execute('create table marker(id integer)')", dbPath],
    { encoding: "utf8" }
  );
  expect(result.status, result.stderr || result.stdout).toBe(0);
}

function createVersionedFunctionGraphDb() {
  const root = mkdtempSync(path.join(tmpdir(), "asip-versioned-graph-"));
  const dbPath = path.join(root, "versioned.db");
  const repoRoot = path.resolve(process.cwd(), "../..");
  const script = String.raw`
import sys
from asip.storage import AsipStore

store = AsipStore.connect(sys.argv[1])
store.migrate()
for function_name, ip_version in [
    ("gfxhub_v11_5_0_gart_enable", "11_5_0"),
    ("gfxhub_v12_0_gart_enable", "12_0"),
]:
    path = f"drivers/gpu/drm/amd/amdgpu/gfxhub_v{ip_version}.c"
    store.add_edge(
        function_name,
        "GCVM_L2_CNTL",
        "writes",
        0.95,
        stage="deterministic",
        source="clang_text_spans",
        path=path,
        line_start=10,
        provenance={
            "extractor": "code_graph",
            "function": function_name,
            "corpus_id": "linux-amdgpu",
            "repo": "linux",
            "path": path,
            "ip": "GC",
            "ip_version": ip_version,
            "resolver_profile": "linux-amdgpu",
        },
    )
`;
  const result = spawnSync("python3", ["-c", script, dbPath], {
    cwd: repoRoot,
    env: {
      ...process.env,
      PYTHONDONTWRITEBYTECODE: "1",
      PYTHONPATH: [path.join(repoRoot, "packages/core/src"), repoRoot].join(":")
    },
    encoding: "utf8"
  });
  expect(result.status, result.stderr || result.stdout).toBe(0);
  return dbPath;
}

function runMcpAgreementProbe(query: string, evidenceId: number, symbol: string, dbPath: string) {
  const repoRoot = path.resolve(process.cwd(), "../..");
  const script = String.raw`
import json
import sys
from apps.mcp.tools import entity_explain, evidence_detail, graph_expand, search_evidence

print(json.dumps({
  "query": search_evidence(sys.argv[1], db_path=sys.argv[4]),
  "detail": evidence_detail(evidence_id=int(sys.argv[2]), db_path=sys.argv[4]),
  "entity": entity_explain(symbol=sys.argv[3], db_path=sys.argv[4]),
  "graph": graph_expand(seed=sys.argv[3], db_path=sys.argv[4]),
}))
`;
  const result = spawnSync("python3", ["-c", script, query, String(evidenceId), symbol, dbPath], {
    cwd: repoRoot,
    env: {
      ...process.env,
      PYTHONDONTWRITEBYTECODE: "1",
      PYTHONPATH: [path.join(repoRoot, "packages/core/src"), repoRoot].join(":")
    },
    encoding: "utf8"
  });
  expect(result.status, result.stderr || result.stdout).toBe(0);
  return JSON.parse(result.stdout) as {
    query: { source: string; queryId: string; rows: Array<{ id: number }> };
    detail: {
      id: number;
      symbol: string;
      path: string;
      resolved_chain: string;
      resolved_chain_explanation: { steps: Array<{ label: string }> };
    };
    entity: {
      symbol: string;
      evidence: Array<{ id: number; symbol: string; path: string; resolved_chain: string }>;
      resolved_chains: string[];
      resolved_chain_explanations: Array<{ evidence_id: number; steps: Array<{ label: string }> }>;
      graph: { nodes: unknown[]; edges: unknown[] };
    };
    graph: { queryId: string; nodes: unknown[]; edges: unknown[] };
  };
}

function pickQueryAgreement(query: { source: string; queryId: string; rows: Array<{ id: number }> }) {
  return {
    source: query.source,
    queryId: query.queryId,
    rowIds: query.rows.map((row) => row.id)
  };
}

function pickEvidenceAgreement(row: { id: number; symbol: string; path: string; resolved_chain: string }) {
  return {
    id: row.id,
    symbol: row.symbol,
    path: row.path,
    resolved_chain: row.resolved_chain
  };
}

async function createIndexedRawFixture(request: APIRequestContext) {
  const root = mkdtempSync(path.join(tmpdir(), "asip-api-query-fixture-"));
  const corpusRoot = path.join(root, "corpus");
  mkdirSync(path.join(corpusRoot, "src"), { recursive: true });
  writeFileSync(
    path.join(corpusRoot, "src", "gfx.c"),
    [
      "void program_local_register(void) {",
      "  uint32_t tmp = 0;",
      "  tmp = REG_SET_FIELD(tmp, LOCAL_TEST_CNTL, ENABLE_LOCAL_FIELD, 1);",
      "  WREG32_SOC15(GC, 0, regLOCAL_TEST_CNTL, tmp);",
      "}",
      "void program_gcvml2_register(void) {",
      "  uint32_t tmp = RREG32_SOC15(GC, 0, regGCVM_L2_CNTL);",
      "  tmp = REG_SET_FIELD(tmp, GCVM_L2_CNTL, ENABLE_L2_CACHE, 1);",
      "  WREG32_SOC15(GC, 0, regGCVM_L2_CNTL, tmp);",
      "}"
    ].join("\n"),
    "utf8"
  );
  const configPath = path.join(root, "config.json");
  writeFileSync(
    configPath,
    JSON.stringify(
      {
        name: "api-query-fixture",
        model: {
          provider: "ollama",
          preferred: "qwen3.5:4b"
        },
        corpora: [
          {
            id: "api-query-fixture",
            repo: "local",
            default_source_root: corpusRoot,
            include: ["**/*.c"]
          }
        ],
        queries: [
          {
            id: "api_query_local_register",
            corpus: "api-query-fixture",
            question: "Which local field is set before writing LOCAL_TEST_CNTL?",
            terms: ["regLOCAL_TEST_CNTL", "LOCAL_TEST_CNTL", "ENABLE_LOCAL_FIELD"],
            expected_terms: [
              "regLOCAL_TEST_CNTL",
              "LOCAL_TEST_CNTL",
              "ENABLE_LOCAL_FIELD",
              "regGCVM_L2_CNTL",
              "GCVM_L2_CNTL",
              "ENABLE_L2_CACHE"
            ],
            max_snippets: 1
          }
        ]
      },
      null,
      2
    ),
    "utf8"
  );
  const dbPath = path.join(root, "query.db");
  const response = await request.post("/api/workbench/index", { data: { configPath, dbPath } });
  expect(response.ok()).toBe(true);
  return { dbPath };
}

function createPdfSectionQueryDb() {
  const root = mkdtempSync(path.join(tmpdir(), "asip-api-pdf-section-"));
  const dbPath = path.join(root, "query.db");
  const repoRoot = path.resolve(process.cwd(), "../..");
  const script = String.raw`
import sys
from asip.storage import AsipStore

store = AsipStore.connect(sys.argv[1])
store.migrate()
store.add_edge("UNRELATED_HELPER", "UNRELATED_REG", "writes", 0.8)
document_id = store.add_document("fixture", "pdf", "docs/manual.pdf")
chunk_id = store.add_chunk(document_id, "GCVM_L2_CNTL is described on this PDF page.", 1, 1, page=3)
store.add_evidence(
    chunk_id,
    "fixture",
    "pdf",
    "local",
    "docs/manual.pdf",
    "GCVM_L2_CNTL",
    "register",
    "mention",
    0.9,
    "GCVM_L2_CNTL is described on this PDF page.",
    "pdf page -> GCVM_L2_CNTL",
    line_start=1,
    line_end=1,
    page=3,
)
`;
  const result = spawnSync("python3", ["-c", script, dbPath], {
    cwd: repoRoot,
    env: {
      ...process.env,
      PYTHONDONTWRITEBYTECODE: "1",
      PYTHONPATH: [path.join(repoRoot, "packages/core/src"), repoRoot].join(":")
    },
    encoding: "utf8"
  });
  expect(result.status, result.stderr || result.stdout).toBe(0);
  return dbPath;
}

function createNlWildcardQueryDb() {
  const root = mkdtempSync(path.join(tmpdir(), "asip-api-nl-wildcard-"));
  const dbPath = path.join(root, "query.db");
  const repoRoot = path.resolve(process.cwd(), "../..");
  const script = String.raw`
import sys
from asip.storage import AsipStore

store = AsipStore.connect(sys.argv[1])
store.migrate()
noisy_doc = store.add_document("fixture", "register", "include/noisy_regs.h")
noisy_chunk = store.add_chunk(noisy_doc, "#define CPM_CONTROL__REFCLK_REGS_GATE_ENABLE_MASK 0x1", 1, 1)
store.add_evidence(
    noisy_chunk,
    "fixture",
    "register",
    "local",
    "include/noisy_regs.h",
    "CPM_CONTROL__REFCLK_REGS_GATE_ENABLE_MASK",
    "field",
    "mention",
    0.99,
    "#define CPM_CONTROL__REFCLK_REGS_GATE_ENABLE_MASK 0x1",
    "register header -> CPM_CONTROL__REFCLK_REGS_GATE_ENABLE_MASK",
    line_start=1,
    line_end=1,
)
cp_doc = store.add_document("fixture", "register", "include/cp_hqd_regs.h")
cp_chunk = store.add_chunk(cp_doc, "#define CP_HQD_PQ_CONTROL 0x0\n#define CP_HQD_ACTIVE 0x1", 1, 2)
for symbol in ("CP_HQD_PQ_CONTROL", "CP_HQD_ACTIVE"):
    store.add_evidence(
        cp_chunk,
        "fixture",
        "register",
        "local",
        "include/cp_hqd_regs.h",
        symbol,
        "register",
        "mention",
        0.7,
        f"#define {symbol} 0x0",
        f"register header -> {symbol}",
        line_start=1,
        line_end=2,
        ip_block="CP",
    )
store.add_edge(
    "gfx_mqd_program",
    "CP_HQD_PQ_CONTROL",
    "writes",
    0.95,
    stage="deterministic",
    source="clang_text_spans",
    path="drivers/gpu/drm/amd/amdgpu/gfx_mqd.c",
    line_start=21,
    provenance={"extractor": "code_graph", "function": "gfx_mqd_program", "corpus_id": "linux-amdgpu"},
)
store.add_edge(
    "gfx_hqd_readback",
    "CP_HQD_PQ_CONTROL",
    "reads",
    0.95,
    stage="deterministic",
    source="clang_text_spans",
    path="drivers/gpu/drm/amd/amdgpu/gfx_mqd.c",
    line_start=34,
    provenance={"extractor": "code_graph", "function": "gfx_hqd_readback", "corpus_id": "linux-amdgpu"},
)
`;
  const result = spawnSync("python3", ["-c", script, dbPath], {
    cwd: repoRoot,
    env: {
      ...process.env,
      PYTHONDONTWRITEBYTECODE: "1",
      PYTHONPATH: [path.join(repoRoot, "packages/core/src"), repoRoot].join(":")
    },
    encoding: "utf8"
  });
  expect(result.status, result.stderr || result.stdout).toBe(0);
  return dbPath;
}

function seedProviderAcceptanceDb(dbPath: string, corpusRoot: string, edgeBaseUrl = "http://127.0.0.1:9") {
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
            "timeout_seconds": 1,
        },
        "embedding": {
            "provider": "openai-compatible",
            "base_url": "https://embedding.example.test",
            "api_path": "/v1/embeddings",
            "model": "local-openai-embed",
            "extra_headers": {"X-ASIP-Embed": "api-acceptance"},
            "timeout_seconds": 1,
        },
    },
)
add_corpus(db_path, "aq09-api-docs", "local", str(corpus_root), ["**/*.md"], "doc")
index_registered_corpora(
    db_path,
    corpus_ids=["aq09-api-docs"],
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

async function startFakeOllamaEdgeServer(): Promise<{ server: Server; baseUrl: string }> {
  const server = createServer((request, response) => {
    if (request.method !== "POST" || request.url !== "/api/chat") {
      response.writeHead(404, { "Content-Type": "application/json" });
      response.end(JSON.stringify({ error: "not found" }));
      return;
    }
    const chunks: Buffer[] = [];
    request.on("data", (chunk) => chunks.push(Buffer.from(chunk)));
    request.on("end", () => {
      const body = JSON.parse(Buffer.concat(chunks).toString("utf8")) as { messages?: Array<{ content?: string }> };
      const prompt = body.messages?.map((message) => message.content ?? "").join("\n") ?? "";
      const content = prompt.includes("BoxMatrix")
        ? {
            documents: [
              {
                id: "edge.md#programming-local-registers",
                boxes: [
                  {
                    id: "l2-cache-control",
                    name: "L2 cache control",
                    summary: "Documents GCVM_L2_CNTL and ENABLE_L2_CACHE.",
                    inputs: ["GCVM_L2_CNTL"],
                    outputs: ["ENABLE_L2_CACHE"],
                    constraints: [],
                    confidence: 0.92,
                    evidence: "fixture"
                  }
                ],
                relationships: [
                  {
                    src: "l2-cache-control",
                    relation: "documents",
                    dst: "GCVM_L2_CNTL",
                    confidence: 0.9,
                    evidence: "fixture"
                  }
                ]
              }
            ]
          }
        : {
            cases: [
              {
                id: "workbench-query",
                edges: [
                  {
                    src: "GCVM_L2_CNTL",
                    relation: "sets_field",
                    dst: "ENABLE_L2_CACHE",
                    confidence: 0.91,
                    evidence: "fixture"
                  }
                ]
              }
            ]
          };
      response.writeHead(200, { "Content-Type": "application/json" });
      response.end(JSON.stringify({ message: { content: JSON.stringify(content) } }));
    });
  });
  await new Promise<void>((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => resolve());
  });
  const address = server.address() as AddressInfo;
  return { server, baseUrl: `http://127.0.0.1:${address.port}` };
}

test("resolver profiles API reads committed configurable profiles", async ({ request }) => {
  const response = await request.get("/api/workbench/resolver-profiles");

  expect(response.ok()).toBe(true);
  const body = (await response.json()) as {
    profiles: Array<{ id: string; language: string; wrappers: string[]; path: string }>;
  };

  expect(body.profiles).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        id: "linux-amdgpu",
        language: "cpp",
        wrappers: expect.arrayContaining(["WREG32_SOC15", "REG_SET_FIELD"]),
        path: "configs/resolvers/linux-amdgpu.yaml"
      }),
      expect.objectContaining({
        id: "initial",
        language: "cpp",
        wrappers: expect.arrayContaining(["RREG32"]),
        path: "configs/resolvers/initial.yaml"
      }),
      expect.objectContaining({
        id: "toy-python",
        language: "python",
        wrappers: expect.arrayContaining(["gpu_register"])
      })
    ])
  );
});

test("resolver profiles API persists and validates user profiles", async ({ request }) => {
  const create = await request.post("/api/workbench/resolver-profiles", {
    data: {
      id: "initial",
      language: "cpp",
      wrappers: ["RREG32"],
      strategy: "macro",
      path: "configs/resolvers/initial.yaml",
      enabled: true
    }
  });
  expect(create.ok()).toBe(true);
  const created = (await create.json()) as { id: string; wrappers: string[] };
  expect(created.id).toBe("initial");
  expect(created.wrappers).toEqual(expect.arrayContaining(["RREG32", "WREG32_SOC15", "REG_SET_FIELD"]));

  const validate = await request.post("/api/workbench/resolver-profiles", {
    data: {
      id: "initial",
      validateSource: "RREG32(CP_INT_CNTL_RING0);"
    }
  });
  expect(validate.ok()).toBe(true);
  const validation = (await validate.json()) as { valid: boolean; symbols: Array<{ symbol: string }> };
  expect(validation.valid).toBe(true);
  expect(validation.symbols).toEqual([expect.objectContaining({ symbol: "CP_INT_CNTL_RING0" })]);
});

test("resolver profiles API rejects profiles without existing yaml config", async ({ request }) => {
  const response = await request.post("/api/workbench/resolver-profiles", {
    data: {
      id: "missing-yaml",
      language: "cpp",
      wrappers: ["MISSING_WRAPPER"],
      strategy: "macro",
      path: "configs/resolvers/missing-yaml.yaml",
      enabled: true
    }
  });

  expect(response.status()).toBe(400);
  const body = (await response.json()) as { error: string };
  expect(body.error).toContain("existing YAML config");
});

test("resolver profiles API accepts inline concept normalization config", async ({ request }) => {
  const root = mkdtempSync(path.join(tmpdir(), "asip-api-inline-resolver-"));
  const dbPath = path.join(root, "inline-resolver.db");

  const create = await request.post("/api/workbench/resolver-profiles", {
    data: {
      id: "inline-concepts",
      language: "cpp",
      wrappers: ["CUSTOM_WRITE"],
      strategy: "macro",
      path: "inline:inline-concepts",
      enabled: true,
      dbPath,
      functionNormalization: {
        enabled: true,
        rules: [
          {
            id: "inline-ip-versioned-functions",
            enabled: true,
            match: "^(?P<ip_block>gfxhub)_rev(?P<ip_version>\\d+)_(?P<operation>.+)$",
            canonical: "inline_{operation}"
          }
        ]
      }
    }
  });

  expect(create.ok()).toBe(true);
  const body = (await create.json()) as {
    id: string;
    path: string;
    config?: {
      graph?: {
        function_normalization?: {
          enabled?: boolean;
          rules?: Array<{ id?: string; match?: string; canonical?: string }>;
        };
      };
    };
  };
  expect(body.id).toBe("inline-concepts");
  expect(body.path).toBe("inline:inline-concepts");
  expect(body.config?.graph?.function_normalization?.enabled).toBe(true);
  expect(body.config?.graph?.function_normalization?.rules?.[0]).toEqual(
    expect.objectContaining({
      id: "inline-ip-versioned-functions",
      canonical: "inline_{operation}"
    })
  );
});

test("index API can target user-added corpora and record provider settings", async ({ request }) => {
  const root = mkdtempSync(path.join(tmpdir(), "asip-api-corpus-"));
  const dbPath = path.join(root, "api-local-docs.db");
  mkdirSync(path.join(root, "docs"));
  writeFileSync(
    path.join(root, "docs", "note.md"),
    "LOCAL_GRAPH_TEST_REGISTER sets LOCAL_GRAPH_TEST_FIELD before validation.",
    "utf8"
  );

  const provider = await request.post("/api/workbench/providers/settings", {
    data: {
      dbPath,
      edge: { provider: "ollama", base_url: "http://edge.local", model: "gemma4:e4b" },
      embedding: {
        provider: "ollama",
        base_url: "http://127.0.0.1:9",
        model: "nomic-embed-text",
        timeout_seconds: 1
      }
    }
  });
  expect(provider.ok()).toBe(true);

  const create = await request.post("/api/workbench/corpora", {
    data: {
      id: "api-local-docs",
      repo: "local",
      sourceRoot: root,
      include: ["**/*.md"],
      type: "doc",
      dbPath
    }
  });
  expect(create.ok()).toBe(true);

  const index = await request.post("/api/workbench/index", { data: { corpusIds: ["api-local-docs"], dbPath } });
  expect(index.ok()).toBe(true);
  const indexed = (await index.json()) as {
    source: string;
    corpusIds: string[];
    providerSettings: { edge?: { model?: string }; embedding?: { base_url?: string } };
  };
  expect(indexed.source).toBe("registered_corpus");
  expect(indexed.corpusIds).toEqual(["api-local-docs"]);
  expect(indexed.providerSettings.edge?.model).toBe("gemma4:e4b");
  expect(indexed.providerSettings.embedding?.base_url).toBe("http://127.0.0.1:9");

  const query = await request.get(
    `/api/workbench/query?q=LOCAL_GRAPH_TEST_REGISTER&dbPath=${encodeURIComponent(dbPath)}`
  );
  const body = (await query.json()) as { rows: Array<{ corpus_id: string; symbol: string }> };
  expect(body.rows).toEqual(
    expect.arrayContaining([
      expect.objectContaining({ corpus_id: "api-local-docs", symbol: "LOCAL_GRAPH_TEST_REGISTER" })
    ])
  );
});

test("jobs API exposes durable index job lifecycle events", async ({ request }) => {
  const root = mkdtempSync(path.join(tmpdir(), "asip-api-jobs-"));
  const dbPath = path.join(root, "api-jobs.db");
  mkdirSync(path.join(root, "docs"));
  writeFileSync(path.join(root, "docs", "note.md"), "LOCAL_JOB_API_REGISTER appears in docs.", "utf8");

  const create = await request.post("/api/workbench/corpora", {
    data: {
      id: "api-job-docs",
      repo: "local",
      sourceRoot: root,
      include: ["**/*.md"],
      type: "doc",
      dbPath
    }
  });
  expect(create.ok()).toBe(true);

  const index = await request.post("/api/workbench/index", { data: { corpusIds: ["api-job-docs"], dbPath } });
  expect(index.ok()).toBe(true);
  const indexed = (await index.json()) as { jobId: number; jobStatus: string; status: string };
  expect(indexed.status).toBe("indexed");
  expect(indexed.jobStatus).toBe("succeeded");

  const list = await request.get(`/api/workbench/jobs?dbPath=${encodeURIComponent(dbPath)}`);
  expect(list.ok()).toBe(true);
  const listBody = (await list.json()) as { jobs: Array<{ id: number; status: string; events: Array<{ status: string }> }> };
  const listedJob = listBody.jobs.find((job) => job.id === indexed.jobId);
  expect(listedJob).toBeTruthy();
  expect(listedJob?.status).toBe("succeeded");
  expect(listedJob?.events.map((event) => event.status)).toEqual(["queued", "indexing", "succeeded"]);

  const detail = await request.get(
    `/api/workbench/jobs/${indexed.jobId}?dbPath=${encodeURIComponent(dbPath)}`
  );
  expect(detail.ok()).toBe(true);
  const detailBody = (await detail.json()) as { status: string; metadata: { result_status?: string }; events: Array<{ status: string }> };
  expect(detailBody.status).toBe("succeeded");
  expect(detailBody.metadata.result_status).toBe("indexed");
  expect(detailBody.events.map((event) => event.status)).toEqual(["queued", "indexing", "succeeded"]);
});

test("provider smoke API makes a real Ollama status attempt", async ({ request }) => {
  const response = await request.post("/api/workbench/providers/smoke", {
    data: {
      provider: "ollama",
      api_base_url: "http://127.0.0.1:9",
      preferred: "missing-model"
    }
  });
  const body = (await response.json()) as { ok: boolean; requestedUrl: string; error?: string };

  expect(response.status()).toBe(502);
  expect(body.ok).toBe(false);
  expect(body.requestedUrl).toBe("http://127.0.0.1:9/api/tags");
  expect(body.error).toBeTruthy();
});

test("index API builds the local SQLite evidence store from raw corpora", async ({ request }) => {
  const root = mkdtempSync(path.join(tmpdir(), "asip-api-raw-index-"));
  const corpusRoot = path.join(root, "corpus");
  mkdirSync(path.join(corpusRoot, "src"), { recursive: true });
  writeFileSync(
    path.join(corpusRoot, "src", "gfx.c"),
    [
      "void program_local_register(void) {",
      "  uint32_t tmp = 0;",
      "  tmp = REG_SET_FIELD(tmp, LOCAL_TEST_CNTL, ENABLE_LOCAL_FIELD, 1);",
      "  WREG32_SOC15(GC, 0, regLOCAL_TEST_CNTL, tmp);",
      "}"
    ].join("\n"),
    "utf8"
  );
  const configPath = path.join(root, "config.json");
  writeFileSync(
    configPath,
    JSON.stringify(
      {
        name: "api-raw-fixture",
        model: {
          provider: "ollama",
          preferred: "qwen3.5:4b"
        },
        corpora: [
          {
            id: "api-raw-fixture",
            repo: "local",
            default_source_root: corpusRoot,
            include: ["**/*.c"]
          }
        ],
        queries: [
          {
            id: "api_raw_local_register",
            corpus: "api-raw-fixture",
            question: "Which local field is set before writing LOCAL_TEST_CNTL?",
            terms: ["regLOCAL_TEST_CNTL", "LOCAL_TEST_CNTL", "ENABLE_LOCAL_FIELD"],
            expected_terms: ["regLOCAL_TEST_CNTL", "LOCAL_TEST_CNTL", "ENABLE_LOCAL_FIELD"],
            max_snippets: 1
          }
        ]
      },
      null,
      2
    ),
    "utf8"
  );
  const dbPath = path.join(root, "raw.db");
  const response = await request.post("/api/workbench/index", { data: { configPath, dbPath } });

  expect(response.ok()).toBe(true);
  const body = (await response.json()) as {
    status: string;
    dbPath: string;
    documents: number;
    chunks: number;
    evidence: number;
    edges: number;
    source: string;
    files: number;
  };

  expect(body.status).toBe("indexed");
  expect(body.source).toBe("raw_corpus");
  expect(body.dbPath).toBe(dbPath);
  expect(body.documents).toBeGreaterThan(0);
  expect(body.chunks).toBeGreaterThan(0);
  expect(body.evidence).toBeGreaterThan(0);
  expect(body.edges).toBeGreaterThan(0);
  expect(body.files).toBe(1);
});
