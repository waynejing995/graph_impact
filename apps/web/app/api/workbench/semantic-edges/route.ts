import { NextResponse } from "next/server";
import { defaultDbPath, ensureWorkbenchIndex, runAsipCli } from "@/lib/asip-cli";

type SemanticEdgesRequest = {
  dbPath?: string;
  q?: string;
  query?: string;
  limit?: number;
};

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as SemanticEdgesRequest;
  const dbPath = body.dbPath?.trim() || defaultDbPath;
  const query = (body.q ?? body.query ?? "").trim();
  const limit = Math.max(1, Math.min(24, Number(body.limit ?? 8) || 8));

  if (!query) {
    return NextResponse.json({ error: "semantic edge query is required" }, { status: 400 });
  }

  try {
    if (dbPath === defaultDbPath) {
      ensureWorkbenchIndex();
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
