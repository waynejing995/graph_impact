import { NextRequest, NextResponse } from "next/server";
import { defaultDbPath, runAsipCli } from "@/lib/asip-cli";

export function GET(request: NextRequest) {
  const seed =
    request.nextUrl.searchParams.get("seed") ??
    request.nextUrl.searchParams.get("queryId");
  const hops = request.nextUrl.searchParams.get("hops") ?? "1";
  const limit = request.nextUrl.searchParams.get("limit") ?? "100";
  const dbPath = request.nextUrl.searchParams.get("dbPath")?.trim() || defaultDbPath;
  try {
    const args = seed
      ? ["graph", "--db", dbPath, "--seed", seed, "--hops", hops]
      : ["graph", "--db", dbPath, "--limit", limit];
    return NextResponse.json(runAsipCli<Record<string, unknown>>(args));
  } catch (error) {
    return NextResponse.json(
      { queryId: seed ?? "global", nodes: [], edges: [], source: "sqlite", error: error instanceof Error ? error.message : "graph failed" },
      { status: 500 }
    );
  }
}
