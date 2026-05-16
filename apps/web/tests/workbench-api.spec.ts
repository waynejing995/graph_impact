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
  const create = await request.post("/api/workbench/corpora", {
    data: {
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

  const list = await request.get("/api/workbench/corpora");
  const body = (await list.json()) as { corpora: Array<{ id: string; source_root: string; status: string }> };
  expect(body.corpora).toEqual(
    expect.arrayContaining([
      expect.objectContaining({ id: "local-amd-docs", source_root: "/docs/amd", status: "not_indexed" })
    ])
  );
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
    graph: { nodes: Array<{ id: string }>; edges: Array<{ src: string; dst: string; confidence: number; weight: number }> };
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
  expect(body.graph.nodes).toEqual(expect.arrayContaining([expect.objectContaining({ id: "LOCAL_TEST_CNTL" })]));
  expect(body.graph.edges).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        src: "LOCAL_TEST_CNTL",
        dst: "ENABLE_LOCAL_FIELD"
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
  const webBody = (await webDetail.json()) as { id: number; symbol: string; path: string; resolved_chain: string };
  expect(pickEvidenceAgreement(webBody)).toEqual(pickEvidenceAgreement(mcp.detail));

  const webEntity = await request.get(
    `/api/workbench/entities/${encodeURIComponent(symbol)}?dbPath=${encodeURIComponent(dbPath)}`
  );
  expect(webEntity.ok()).toBe(true);
  const webEntityBody = (await webEntity.json()) as {
    symbol: string;
    evidence: Array<{ id: number; symbol: string; path: string; resolved_chain: string }>;
    resolved_chains: string[];
  };
  expect(webEntityBody.symbol).toBe(mcp.entity.symbol);
  expect(webEntityBody.evidence.map(pickEvidenceAgreement)).toEqual(mcp.entity.evidence.map(pickEvidenceAgreement));
  expect(webEntityBody.resolved_chains).toEqual(mcp.entity.resolved_chains);
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
    runs: Array<{ id: string; model: string; passed: number; failed: number; partial?: number; queryCount: number; artifactPath: string }>;
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
      })
    ])
  );
  expect(body.runs[0]).toEqual(
    expect.objectContaining({
      model: "asip.acceptance",
      artifactPath: expect.stringMatching(/^docs\/qa\/2026-05-17-acceptance/)
    })
  );
});

test("acceptance run API executes selected acceptance queries", async ({ request }) => {
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
      surfaces: ["CLI", "API", "Web"]
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
  const response = await request.get("/api/workbench/graph?seed=GCVM_L2_CNTL");

  expect(response.ok()).toBe(true);
  const body = (await response.json()) as {
    queryId: string;
    nodes: Array<{ id: string; kind: string; weight: number }>;
    edges: Array<{ src: string; relation: string; dst: string; confidence: number; weight: number }>;
  };

  expect(body.queryId).toBe("GCVM_L2_CNTL");
  expect(body.nodes).toEqual(
    expect.arrayContaining([
      expect.objectContaining({ id: "GCVM_L2_CNTL", kind: "register" }),
      expect.objectContaining({ id: "ENABLE_L2_CACHE", kind: "field" })
    ])
  );
  expect(body.edges).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        src: "GCVM_L2_CNTL",
        relation: "sets_field",
        dst: "ENABLE_L2_CACHE",
        confidence: 0.9,
        weight: 0.9
      })
    ])
  );
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
      graph: { edges: Array<{ src: string; relation: string; dst: string; weight: number }> };
    };
    expect(body).toMatchObject({
      source: "semantic_edge_job",
      edge_count: 1,
      provider: "ollama",
      model: "gemma4:e4b"
    });
    expect(body.graph.edges).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          src: "GCVM_L2_CNTL",
          relation: "sets_field",
          dst: "ENABLE_L2_CACHE",
          weight: 0.91
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

function runMcpAgreementProbe(query: string, evidenceId: number, symbol: string, dbPath: string) {
  const repoRoot = path.resolve(process.cwd(), "../..");
  const script = String.raw`
import json
import sys
from apps.mcp.tools import entity_explain, evidence_detail, search_evidence

print(json.dumps({
  "query": search_evidence(sys.argv[1], db_path=sys.argv[4]),
  "detail": evidence_detail(evidence_id=int(sys.argv[2]), db_path=sys.argv[4]),
  "entity": entity_explain(symbol=sys.argv[3], db_path=sys.argv[4]),
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
    detail: { id: number; symbol: string; path: string; resolved_chain: string };
    entity: {
      symbol: string;
      evidence: Array<{ id: number; symbol: string; path: string; resolved_chain: string }>;
      resolved_chains: string[];
    };
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
  const dbPath = path.join(root, "query.db");
  const response = await request.post("/api/workbench/index", { data: { configPath, dbPath } });
  expect(response.ok()).toBe(true);
  return { dbPath };
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
    response.writeHead(200, { "Content-Type": "application/json" });
    response.end(
      JSON.stringify({
        message: {
          content: JSON.stringify({
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
      id: "api-python",
      language: "python",
      wrappers: ["gpu_register"],
      strategy: "python-call",
      path: "configs/resolvers/api-python.yaml",
      enabled: true
    }
  });
  expect(create.ok()).toBe(true);
  const created = (await create.json()) as { id: string; wrappers: string[] };
  expect(created.id).toBe("api-python");
  expect(created.wrappers).toEqual(["gpu_register"]);

  const validate = await request.post("/api/workbench/resolver-profiles", {
    data: {
      id: "api-python",
      validateSource: '@gpu_register("CP_INT_CNTL_RING0")'
    }
  });
  expect(validate.ok()).toBe(true);
  const validation = (await validate.json()) as { valid: boolean; symbols: Array<{ symbol: string }> };
  expect(validation.valid).toBe(true);
  expect(validation.symbols).toEqual([expect.objectContaining({ symbol: "CP_INT_CNTL_RING0" })]);
});

test("index API can target user-added corpora and record provider settings", async ({ request }) => {
  const root = mkdtempSync(path.join(tmpdir(), "asip-api-corpus-"));
  mkdirSync(path.join(root, "docs"));
  writeFileSync(
    path.join(root, "docs", "note.md"),
    "LOCAL_GRAPH_TEST_REGISTER sets LOCAL_GRAPH_TEST_FIELD before validation.",
    "utf8"
  );

  const provider = await request.post("/api/workbench/providers/settings", {
    data: {
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
      type: "doc"
    }
  });
  expect(create.ok()).toBe(true);

  const index = await request.post("/api/workbench/index", { data: { corpusIds: ["api-local-docs"] } });
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

  const query = await request.get("/api/workbench/query?q=LOCAL_GRAPH_TEST_REGISTER");
  const body = (await query.json()) as { rows: Array<{ corpus_id: string; symbol: string }> };
  expect(body.rows).toEqual(
    expect.arrayContaining([
      expect.objectContaining({ corpus_id: "api-local-docs", symbol: "LOCAL_GRAPH_TEST_REGISTER" })
    ])
  );
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
