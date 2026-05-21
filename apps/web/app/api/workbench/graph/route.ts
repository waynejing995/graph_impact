import { NextRequest, NextResponse } from "next/server";
import { defaultDbPath, runAsipCli } from "@/lib/asip-cli";
import { explicitTextOrError } from "@/lib/request-paths";
import { configuredInt, readWorkbenchLimits } from "@/lib/workbench-limits";

export function GET(request: NextRequest) {
  const seed =
    request.nextUrl.searchParams.get("seed") ??
    request.nextUrl.searchParams.get("queryId");
  const limits = readWorkbenchLimits();
  const hops = clampedHops(request.nextUrl.searchParams.get("hops"), limits.graph?.defaultHops);
  const requestedLimit = request.nextUrl.searchParams.get("limit")?.trim();
  const requestedAll = requestedLimit === "all" || requestedLimit === "full";
  const configuredEdgeBudget = configuredInt(requestedLimit) ?? limits.graph?.edgeBudget;
  const maxEdgeBudget = limits.graph?.maxEdgeBudget;
  const edgeBudget =
    configuredEdgeBudget !== undefined && maxEdgeBudget !== undefined
      ? Math.min(configuredEdgeBudget, maxEdgeBudget)
      : configuredEdgeBudget;
  const includeEvidenceDerived = ["1", "true", "yes"].includes(
    (request.nextUrl.searchParams.get("includeEvidenceDerived") ?? "").toLowerCase()
  );
  const evidenceRowCap = configuredInt(request.nextUrl.searchParams.get("evidenceRowCap")) ?? limits.graph?.evidenceRowCap;
  const functionView =
    request.nextUrl.searchParams.get("functionView") ??
    request.nextUrl.searchParams.get("function_view") ??
    "concept";
  if (!["concept", "implementation"].includes(functionView)) {
    return NextResponse.json(
      { queryId: seed ?? "global", nodes: [], edges: [], source: "sqlite", error: "functionView must be concept or implementation" },
      { status: 400 }
    );
  }
  let dbPath = defaultDbPath;
  try {
    dbPath = explicitTextOrError(request.nextUrl.searchParams.get("dbPath"), "dbPath") ?? defaultDbPath;
  } catch (error) {
    return NextResponse.json(
      { queryId: seed ?? "global", nodes: [], edges: [], source: "sqlite", error: error instanceof Error ? error.message : "dbPath cannot be blank" },
      { status: 400 }
    );
  }
  try {
    const args = seed
      ? ["graph", "--db", dbPath, "--seed", seed, "--function-view", functionView, "--hops", String(hops)]
      : ["graph", "--db", dbPath, "--function-view", functionView, "--compact"];
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

function clampedHops(value: string | null, fallback = 3) {
  const parsed = configuredInt(value) ?? fallback;
  return Math.max(1, Math.min(10, parsed));
}
