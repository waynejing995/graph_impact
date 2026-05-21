import { NextRequest, NextResponse } from "next/server";
import { defaultDbPath, runAsipCli } from "@/lib/asip-cli";
import { explicitTextOrError } from "@/lib/request-paths";

export function GET(request: NextRequest) {
  const query = request.nextUrl.searchParams.get("q") ?? "";
  let dbPath = defaultDbPath;
  try {
    dbPath = explicitTextOrError(request.nextUrl.searchParams.get("dbPath"), "dbPath") ?? defaultDbPath;
  } catch (error) {
    return NextResponse.json(
      { query, rows: [], graph: { nodes: [], edges: [] }, empty: true, error: error instanceof Error ? error.message : "dbPath cannot be blank" },
      { status: 400 }
    );
  }
  const ipBlock =
    request.nextUrl.searchParams.get("ipBlock") ?? request.nextUrl.searchParams.get("ip_block") ?? "";
  const asic =
    request.nextUrl.searchParams.get("asic") ?? request.nextUrl.searchParams.get("asic_or_generation") ?? "";
  const sourceTypes = request.nextUrl.searchParams
    .getAll("sourceType")
    .concat(
      request.nextUrl.searchParams
        .get("sourceTypes")
        ?.split(",")
        .map((item) => item.trim())
        .filter(Boolean) ?? []
    );
  const functionView =
    request.nextUrl.searchParams.get("functionView") ??
    request.nextUrl.searchParams.get("function_view") ??
    "concept";
  if (!["concept", "implementation"].includes(functionView)) {
    return NextResponse.json(
      { query, rows: [], graph: { nodes: [], edges: [] }, empty: true, error: "functionView must be concept or implementation" },
      { status: 400 }
    );
  }
  try {
    const args = ["query", "--db", dbPath, "--q", query, "--function-view", functionView, "--compact-graph"];
    if (ipBlock) {
      args.push("--ip-block", ipBlock);
    }
    if (asic) {
      args.push("--asic", asic);
    }
    for (const sourceType of sourceTypes) {
      args.push("--source-type", sourceType);
    }
    const payload = runAsipCli<Record<string, unknown>>(args);
    return NextResponse.json(payload);
  } catch (error) {
    return NextResponse.json(
      { query, rows: [], graph: { nodes: [], edges: [] }, empty: true, error: error instanceof Error ? error.message : "query failed" },
      { status: 500 }
    );
  }
}
