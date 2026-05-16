import { NextRequest, NextResponse } from "next/server";
import { defaultDbPath, runAsipCli } from "@/lib/asip-cli";

type RouteContext = {
  params: Promise<{ symbol: string }>;
};

export async function GET(request: NextRequest, context: RouteContext) {
  const { symbol } = await context.params;
  const entitySymbol = decodeURIComponent(symbol).trim();
  if (!entitySymbol) {
    return NextResponse.json({ error: "missing entity symbol" }, { status: 400 });
  }
  const dbPath = request.nextUrl.searchParams.get("dbPath")?.trim() || defaultDbPath;
  try {
    const payload = runAsipCli<Record<string, unknown>>([
      "entity-explain",
      "--db",
      dbPath,
      "--symbol",
      entitySymbol
    ]);
    return NextResponse.json(payload);
  } catch (error) {
    return NextResponse.json(
      { symbol: entitySymbol, evidence: [], graph: { nodes: [], edges: [] }, resolved_chains: [], error: error instanceof Error ? error.message : "entity explain failed" },
      { status: 500 }
    );
  }
}
