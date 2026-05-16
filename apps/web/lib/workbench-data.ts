import { existsSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";

type FullCorpusConfig = {
  name: string;
  model: Record<string, unknown>;
  corpora: Array<{
    id: string;
    repo: string;
    default_source_root: string;
    relative_root?: string;
    include: string[];
  }>;
  queries: ArtifactQuery[];
};

type ArtifactQuery = {
  id: string;
  corpus: string;
  repo?: string;
  question: string;
  terms: string[];
  expected_terms: string[];
  max_snippets?: number;
  snippets?: SourceSnippet[];
  resolved?: boolean;
};

type SourceSnippet = {
  path: string;
  line_start: number;
  line_end: number;
  text: string;
};

type GeneratedCase = {
  id: string;
  edges?: GraphEdge[];
};

type GraphEdge = {
  src: string;
  relation: string;
  dst: string;
  confidence: number;
  evidence: string;
};

type QueryResult = {
  id: string;
  case: string;
  corpus: string;
  passed: boolean;
  missing: string[];
  missing_in_sources: string[];
  ungrounded_edges: string[];
  edge_count: number;
  source_hit_count: number;
  sources: string[];
};

type FullCorpusRun = {
  config: string;
  model: string;
  duration_seconds: number;
  corpora: Record<
    string,
    {
      repo: string;
      source_root: string;
      scan_root: string;
      relative_root: string;
      file_count: number;
      commit: string;
    }
  >;
  scan: {
    queries: ArtifactQuery[];
    summary: Record<string, unknown>;
  };
  generated: {
    cases: GeneratedCase[];
    errors?: unknown[];
  };
  query_results: QueryResult[];
  summary: {
    query_count: number;
    passed: number;
    failed: number;
    min_pass: number;
    batch_size: number;
    resolved_query_count: number;
    total_files_scanned: number;
  };
};

type AcceptanceQueryRun = {
  source: "asip.acceptance";
  db_path: string;
  summary: {
    total: number;
    passed: number;
    partial: number;
    failed: number;
  };
};

export type WorkbenchEvidenceRow = {
  source: string;
  tone: "neutral" | "code" | "register" | "doc" | "pdf" | "success";
  symbol: string;
  relation: string;
  score: string;
  path: string;
  snippet?: string;
};

const repoRoot = path.resolve(process.cwd(), "../..");
const fullCorpusConfigPath = path.join(repoRoot, "configs/edge_cases/full-corpus-qwen35.json");
const defaultRunPath = path.join(
  repoRoot,
  "docs/qa/2026-05-16-full-corpus-edge-generation-qwen35-strict-batch1.json"
);

export function getCorpora() {
  const config = readFullCorpusConfig();
  const run = readDefaultRun();

  return config.corpora.map((corpus) => {
    const scanned = run.corpora[corpus.id];
    return {
      id: corpus.id,
      repo: scanned?.repo ?? corpus.repo,
      sourceRoot: scanned?.source_root ?? corpus.default_source_root,
      scanRoot: scanned?.scan_root ?? corpus.default_source_root,
      relativeRoot: scanned?.relative_root ?? corpus.relative_root ?? "",
      include: corpus.include,
      fileCount: scanned?.file_count ?? 0,
      commit: scanned?.commit ?? "unknown"
    };
  });
}

export function searchWorkbench(query: string) {
  const run = readDefaultRun();
  const selected = selectQuery(run.scan.queries, query);
  const graph = buildGraphForQuery(selected.id);
  const rows = buildEvidenceRows(selected, run.query_results.find((result) => result.case === selected.id), graph.edges);

  return {
    query: query.trim(),
    queryId: selected.id,
    question: selected.question,
    rows,
    graph
  };
}

export function listAcceptanceRuns() {
  const qaDir = path.join(repoRoot, "docs/qa");
  const files = readdirSync(qaDir)
    .filter(
      (file) =>
        /^2026-05-16-full-corpus-edge-generation-.*\.json$/.test(file) ||
        /^\d{4}-\d{2}-\d{2}-acceptance-.*\.json$/.test(file)
    )
    .sort()
    .reverse();

  return files.map((file) => {
    const artifactPath = `docs/qa/${file}`;
    const run = readJson<FullCorpusRun | AcceptanceQueryRun>(path.join(qaDir, file));
    if (isAcceptanceQueryRun(run)) {
      return {
        id: runIdFromArtifact(file),
        artifactPath,
        config: "acceptance",
        model: run.source,
        durationSeconds: 0,
        passed: run.summary.passed,
        partial: run.summary.partial,
        failed: run.summary.failed,
        queryCount: run.summary.total,
        resolvedQueryCount: run.summary.total - run.summary.failed,
        totalFilesScanned: 0,
        batchSize: 0,
        errorCount: run.summary.failed
      };
    }
    return {
      id: runIdFromArtifact(file),
      artifactPath,
      config: run.config,
      model: run.model,
      durationSeconds: run.duration_seconds,
      passed: run.summary.passed,
      failed: run.summary.failed,
      queryCount: run.summary.query_count,
      resolvedQueryCount: run.summary.resolved_query_count,
      totalFilesScanned: run.summary.total_files_scanned,
      batchSize: run.summary.batch_size,
      errorCount: run.generated.errors?.length ?? 0
    };
  });
}

export function listResolverProfiles() {
  const resolverDir = path.join(repoRoot, "configs/resolvers");
  return readdirSync(resolverDir)
    .filter((file) => file.endsWith(".yaml"))
    .sort()
    .map((file) => {
      const text = readFileSync(path.join(resolverDir, file), "utf8");
      const wrappers = Array.from(text.matchAll(/^  ([A-Za-z_][A-Za-z0-9_]*):$/gm)).map((match) => match[1]);
      const pythonExtractors = parseInlineList(text.match(/^python_extractors:\s*(\[.*\])$/m)?.[1] ?? "");
      return {
        id: text.match(/^id:\s*(.+)$/m)?.[1].trim() ?? file.replace(/\.yaml$/, ""),
        language: text.match(/^language:\s*(.+)$/m)?.[1].trim() ?? "cpp",
        wrappers: wrappers.length ? wrappers : pythonExtractors,
        path: `configs/resolvers/${file}`,
        enabled: true
      };
    });
}

export function buildGraphForQuery(queryId: string) {
  const run = readDefaultRun();
  const generated = run.generated.cases.find((item) => item.id === queryId);
  const query = run.scan.queries.find((item) => item.id === queryId);
  const edges = generated?.edges ?? [];
  const nodeWeights = new Map<string, { id: string; kind: string; weight: number }>();

  for (const edge of edges) {
    addNode(nodeWeights, edge.src);
    addNode(nodeWeights, edge.dst);
  }
  for (const term of query?.expected_terms ?? []) {
    addNode(nodeWeights, term);
  }

  return {
    queryId,
    nodes: Array.from(nodeWeights.values()).sort((left, right) => right.weight - left.weight),
    edges,
    snippets: query?.snippets ?? []
  };
}

function isAcceptanceQueryRun(run: FullCorpusRun | AcceptanceQueryRun): run is AcceptanceQueryRun {
  return (run as AcceptanceQueryRun).source === "asip.acceptance";
}

function readFullCorpusConfig() {
  return readJson<FullCorpusConfig>(fullCorpusConfigPath);
}

function readDefaultRun() {
  return readJson<FullCorpusRun>(defaultRunPath);
}

function readJson<T>(filePath: string): T {
  if (!existsSync(filePath)) {
    throw new Error(`Missing workbench artifact: ${path.relative(repoRoot, filePath)}`);
  }
  return JSON.parse(readFileSync(filePath, "utf8")) as T;
}

function selectQuery(queries: ArtifactQuery[], rawQuery: string) {
  const tokens = tokenize(rawQuery);
  const scored = queries.map((query) => {
    const haystack = [
      query.id,
      query.question,
      ...query.terms,
      ...query.expected_terms,
      ...(query.snippets ?? []).map((snippet) => snippet.text)
    ]
      .join(" ")
      .toLowerCase();
    return {
      query,
      score: tokens.reduce((sum, token) => sum + (haystack.includes(token) ? 1 : 0), 0)
    };
  });

  return scored.sort((left, right) => right.score - left.score)[0]?.query ?? queries[0];
}

function buildEvidenceRows(query: ArtifactQuery, result: QueryResult | undefined, edges: GraphEdge[]) {
  const sourceRows = (query.snippets ?? []).flatMap((snippet) =>
    query.expected_terms.map((term): WorkbenchEvidenceRow => ({
      source: query.corpus,
      tone: toneForSymbol(term),
      symbol: term,
      relation: "term_match",
      score: result?.passed ? "pass" : "source",
      path: `${snippet.path}:${snippet.line_start}-${snippet.line_end}`,
      snippet: snippet.text
    }))
  );

  const edgeRows = edges.map((edge): WorkbenchEvidenceRow => ({
    source: "edge",
    tone: toneForSymbol(edge.dst),
    symbol: edge.dst,
    relation: edge.relation,
    score: edge.confidence.toFixed(2),
    path: edge.evidence
  }));

  return [...sourceRows, ...edgeRows].filter(
    (row, index, allRows) =>
      allRows.findIndex(
        (candidate) =>
          candidate.symbol === row.symbol && candidate.relation === row.relation && candidate.path === row.path
      ) === index
  );
}

function addNode(nodes: Map<string, { id: string; kind: string; weight: number }>, id: string) {
  const normalized = normalizeNodeId(id);
  const existing = nodes.get(normalized);
  if (existing) {
    existing.weight += 1;
    return;
  }
  nodes.set(normalized, {
    id: normalized,
    kind: kindForSymbol(normalized),
    weight: 1
  });
}

function normalizeNodeId(id: string) {
  const fieldMarker = "__";
  if (id.includes(fieldMarker)) {
    return id.slice(id.lastIndexOf(fieldMarker) + fieldMarker.length);
  }
  return id;
}

function kindForSymbol(symbol: string) {
  if (/ENABLE|DISABLE|PENDING|MASK|SHIFT|MODE|SIZE|BASE/i.test(symbol) && !/CNTL|STATUS|REG/i.test(symbol)) {
    return "field";
  }
  if (/CNTL|STATUS|REG|GCVM|GRBM|CP_|BIF_|RLC_|RB_/i.test(symbol)) {
    return "register";
  }
  if (/\.pdf|doc|rst/i.test(symbol)) {
    return "doc";
  }
  return "code";
}

function toneForSymbol(symbol: string): WorkbenchEvidenceRow["tone"] {
  const kind = kindForSymbol(symbol);
  if (kind === "field") {
    return "success";
  }
  if (kind === "register") {
    return "register";
  }
  if (kind === "doc") {
    return "doc";
  }
  return "code";
}

function tokenize(query: string) {
  return query
    .toLowerCase()
    .split(/[^a-z0-9_]+/)
    .map((token) => token.trim())
    .filter((token) => token.length > 2 && !new Set(["which", "what", "who", "the", "and", "for"]).has(token));
}

function runIdFromArtifact(file: string) {
  return file
    .replace(/\.json$/, "")
    .replace(/^\d{4}-\d{2}-\d{2}-acceptance-/, "acceptance-")
    .replace(/^\d{4}-\d{2}-\d{2}-full-corpus-edge-generation-/, "");
}

function parseInlineList(value: string) {
  if (!value.startsWith("[") || !value.endsWith("]")) {
    return [];
  }
  return value
    .slice(1, -1)
    .split(",")
    .map((item) => item.trim().replace(/^['"]|['"]$/g, ""))
    .filter(Boolean);
}
