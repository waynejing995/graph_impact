import { NextResponse } from "next/server";
import { defaultDbPath, ensureWorkbenchIndex, runAsipCli } from "@/lib/asip-cli";
import { explicitTextOrError } from "@/lib/request-paths";
import { configuredInt, readWorkbenchLimits } from "@/lib/workbench-limits";

type SemanticEdgesRequest = {
  dbPath?: string;
  q?: string;
  query?: string;
  mode?: string;
  limit?: number;
  batchSize?: number;
  includeEvidenceDerived?: boolean;
  evidenceRowCap?: number;
};

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as SemanticEdgesRequest;
  const limits = readWorkbenchLimits();
  let dbPath = defaultDbPath;
  try {
    dbPath = explicitTextOrError(body.dbPath, "dbPath") ?? defaultDbPath;
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "dbPath cannot be blank" },
      { status: 400 }
    );
  }
  const query = (body.q ?? body.query ?? "").trim();
  const limit = configuredInt(body.limit) ?? limits.semantic?.queryLimit;
  const batchLimit = configuredInt(body.limit) ?? limits.semantic?.batchCandidateLimit;
  const batchSize = configuredInt(body.batchSize) ?? limits.semantic?.batchSize;
  const mode = String(body.mode ?? "query").trim().toLowerCase();
  const includeEvidenceDerived = body.includeEvidenceDerived === true;
  const evidenceRowCap = configuredInt(body.evidenceRowCap) ?? limits.graph?.evidenceRowCap;

  if (mode !== "batch" && mode !== "doc-nodes" && !query) {
    return NextResponse.json({ error: "semantic edge query is required" }, { status: 400 });
  }

  try {
    if (dbPath === defaultDbPath) {
      ensureWorkbenchIndex();
    }
    if (mode === "batch") {
      return NextResponse.json(
        runAsipCli<Record<string, unknown>>([
          "semantic-edges-batch",
          "--db",
          dbPath,
          ...(batchLimit !== undefined ? ["--limit", String(batchLimit)] : []),
          ...(batchSize !== undefined ? ["--batch-size", String(batchSize)] : []),
          ...(includeEvidenceDerived
            ? ["--include-evidence-derived", ...(evidenceRowCap !== undefined ? ["--evidence-row-cap", String(evidenceRowCap)] : [])]
            : [])
        ])
      );
    }
    if (mode === "doc-nodes") {
      return NextResponse.json(
        runAsipCli<Record<string, unknown>>([
          "doc-nodes-batch",
          "--db",
          dbPath,
          ...(batchLimit !== undefined ? ["--limit", String(batchLimit)] : []),
          ...(batchSize !== undefined ? ["--batch-size", String(batchSize)] : [])
        ])
      );
    }
    return NextResponse.json(
      runAsipCli<Record<string, unknown>>([
        "semantic-edges",
        "--db",
        dbPath,
        "--q",
        query,
        ...(limit !== undefined ? ["--limit", String(limit)] : [])
      ])
    );
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "semantic edge generation failed" },
      { status: 500 }
    );
  }
}
