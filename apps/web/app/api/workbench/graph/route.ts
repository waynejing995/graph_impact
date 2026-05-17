import { NextRequest, NextResponse } from "next/server";
import { defaultDbPath, runAsipCli } from "@/lib/asip-cli";
import { configuredInt, readWorkbenchLimits } from "@/lib/workbench-limits";

export function GET(request: NextRequest) {
  const seed =
    request.nextUrl.searchParams.get("seed") ??
    request.nextUrl.searchParams.get("queryId");
  const limits = readWorkbenchLimits();
  const hops = request.nextUrl.searchParams.get("hops") ?? String(limits.graph?.defaultHops ?? "");
  const requestedLimit = request.nextUrl.searchParams.get("limit")?.trim();
  const requestedAll = requestedLimit === "all" || requestedLimit === "full";
  const edgeBudget = configuredInt(requestedLimit) ?? limits.graph?.edgeBudget;
  const includeEvidenceDerived = ["1", "true", "yes"].includes(
    (request.nextUrl.searchParams.get("includeEvidenceDerived") ?? "").toLowerCase()
  );
  const evidenceRowCap = configuredInt(request.nextUrl.searchParams.get("evidenceRowCap")) ?? limits.graph?.evidenceRowCap;
  const dbPath = request.nextUrl.searchParams.get("dbPath")?.trim() || defaultDbPath;
  try {
    const args = seed
      ? ["graph", "--db", dbPath, "--seed", seed, ...(hops ? ["--hops", hops] : [])]
      : ["graph", "--db", dbPath];
    if (!seed && requestedAll) {
      args.push("--all");
    } else if (!seed && edgeBudget !== undefined) {
      args.push("--limit", String(edgeBudget));
    }
    if (!seed && includeEvidenceDerived) {
      args.push("--include-evidence-derived");
      if (evidenceRowCap !== undefined) {
        args.push("--evidence-row-cap", String(evidenceRowCap));
      }
    }
    return NextResponse.json(runAsipCli<Record<string, unknown>>(args));
  } catch (error) {
    return NextResponse.json(
      { queryId: seed ?? "global", nodes: [], edges: [], source: "sqlite", error: error instanceof Error ? error.message : "graph failed" },
      { status: 500 }
    );
  }
}
