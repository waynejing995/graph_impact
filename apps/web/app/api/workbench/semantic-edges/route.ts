import { NextResponse } from "next/server";
import { defaultDbPath, ensureWorkbenchIndex, runAsipCli } from "@/lib/asip-cli";

type SemanticEdgesRequest = {
  dbPath?: string;
  q?: string;
  query?: string;
  mode?: string;
  limit?: number;
  batchSize?: number;
};

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as SemanticEdgesRequest;
  const dbPath = body.dbPath?.trim() || defaultDbPath;
  const query = (body.q ?? body.query ?? "").trim();
  const limit = Math.max(1, Math.min(24, Number(body.limit ?? 8) || 8));
  const batchSize = Math.max(1, Math.min(12, Number(body.batchSize ?? 6) || 6));
  const mode = String(body.mode ?? "query").trim().toLowerCase();

  if (mode !== "batch" && !query) {
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
          "--limit",
          String(limit),
          "--batch-size",
          String(batchSize)
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
        "--limit",
        String(limit)
      ])
    );
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "semantic edge generation failed" },
      { status: 500 }
    );
  }
}
