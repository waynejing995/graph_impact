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

type AcceptanceDetail = {
  id: string;
  status: string;
  query?: string;
  failureReasons: string[];
  missing: string[];
  missingSurfaces: string[];
  sourcePaths: string[];
  sourceTypes: string[];
  retrievalSources: string[];
  rowCount?: number;
  graphEdgeCount?: number;
  edgeCount?: number;
  sourceHitCount?: number;
  providerChecks?: {
    embedding?: ProviderAcceptanceCheck;
    semanticEdge?: ProviderAcceptanceCheck;
  };
};

type ProviderAcceptanceCheck = {
  status?: string;
  provider?: string;
  model?: string;
  message?: string;
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
    cases?: unknown[];
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
  database_health?: {
    status?: string;
    failure_reasons?: string[];
  };
  summary: {
    total: number;
    passed: number;
    partial: number;
    failed: number;
  };
  queries?: Array<{
    id: string;
    query?: string;
    status: string;
    failure_reasons?: string[];
    missing?: string[];
    missing_surfaces?: string[];
    source_paths?: string[];
    source_types?: string[];
    retrieval_sources?: string[];
    row_count?: number;
    graph_edge_count?: number;
    edge_count?: number;
    source_hit_count?: number;
    provider_checks?: {
      embedding?: ProviderAcceptanceCheck;
      semantic_edge?: ProviderAcceptanceCheck;
    };
  }>;
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
const fullCorpusConfigPath = path.join(repoRoot, "configs/edge_cases/full-corpus-gemma4-e4b.json");
const defaultRunPath = path.join(
  repoRoot,
  "docs/qa/2026-05-16-full-corpus-edge-generation-gemma4-e4b-strict-batch1.json"
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
        errorCount: run.summary.failed,
        databaseHealth: buildDatabaseHealthDetails(run),
        details: (run.queries ?? []).map((query) => ({
          id: query.id,
          status: query.status,
          query: query.query,
          failureReasons: query.failure_reasons ?? [],
          missing: query.missing ?? [],
          missingSurfaces: query.missing_surfaces ?? [],
          sourcePaths: query.source_paths ?? [],
          sourceTypes: query.source_types ?? [],
          retrievalSources: query.retrieval_sources ?? [],
          rowCount: query.row_count,
          graphEdgeCount: query.graph_edge_count,
          edgeCount: query.edge_count,
          sourceHitCount: query.source_hit_count,
          providerChecks: {
            embedding: query.provider_checks?.embedding,
            semanticEdge: query.provider_checks?.semantic_edge
          }
        }))
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
      errorCount: run.generated.errors?.length ?? 0,
      details: buildFullCorpusDetails(run)
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

function isAcceptanceQueryRun(run: FullCorpusRun | AcceptanceQueryRun): run is AcceptanceQueryRun {
  return (run as AcceptanceQueryRun).source === "asip.acceptance";
}

function buildDatabaseHealthDetails(run: AcceptanceQueryRun): AcceptanceDetail[] {
  if (!run.database_health || run.database_health.status === "pass") {
    return [];
  }
  return [
    {
      id: "database_health",
      status: run.database_health.status ?? "unknown",
      failureReasons: run.database_health.failure_reasons ?? [],
      missing: [],
      missingSurfaces: [],
      sourcePaths: [run.db_path],
      sourceTypes: [],
      retrievalSources: []
    }
  ];
}

function buildFullCorpusDetails(run: FullCorpusRun): AcceptanceDetail[] {
  const queriesById = new Map(run.scan.queries.map((query) => [query.id, query]));
  return run.query_results.map((result) => {
    const query = queriesById.get(result.case);
    return {
      id: result.id,
      status: result.passed ? "pass" : "fail",
      query: query?.question,
      failureReasons: result.passed ? [] : [`missing terms: ${result.missing.join(", ") || "not recorded"}`],
      missing: result.missing ?? [],
      missingSurfaces: result.missing_in_sources ?? [],
      sourcePaths: result.sources ?? [],
      sourceTypes: [],
      retrievalSources: [],
      edgeCount: result.edge_count,
      sourceHitCount: result.source_hit_count
    };
  });
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
