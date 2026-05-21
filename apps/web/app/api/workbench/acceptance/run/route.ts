import { NextResponse } from "next/server";
import { defaultDbPath, ensureWorkbenchIndex, runAsipCliAsync } from "@/lib/asip-cli";
import { explicitTextOrError } from "@/lib/request-paths";

type AcceptanceRunRequest = {
  dbPath?: string;
  queryId?: string;
  queryIds?: string[];
  surfaces?: string[];
  outputJson?: string;
  outputMd?: string;
};

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as AcceptanceRunRequest;
  let dbPath = defaultDbPath;
  try {
    dbPath = explicitTextOrError(body.dbPath, "dbPath") ?? defaultDbPath;
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "dbPath cannot be blank" },
      { status: 400 }
    );
  }
  const queryIds = normalizeList(body.queryIds ?? (body.queryId ? [body.queryId] : []));
  const surfaces = normalizeList(body.surfaces ?? ["CLI", "API", "MCP"]);

  try {
    if (dbPath === defaultDbPath) {
      ensureWorkbenchIndex();
    }
    const args = ["acceptance", "--db", dbPath, "--full"];
    for (const queryId of queryIds) {
      args.push("--query-id", queryId);
    }
    for (const surface of surfaces.length ? surfaces : ["CLI", "API", "MCP"]) {
      args.push("--surface", surface);
    }
    if (body.outputJson?.trim()) {
      args.push("--output-json", body.outputJson.trim());
    }
    if (body.outputMd?.trim()) {
      args.push("--output-md", body.outputMd.trim());
    }
    return NextResponse.json(
      await runAsipCliAsync<Record<string, unknown>>(args, {
        ASIP_WEB_BASE_URL: new URL(request.url).origin
      })
    );
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "acceptance run failed" },
      { status: 500 }
    );
  }
}

function normalizeList(items: string[] | undefined) {
  return (items ?? []).map((item) => item.trim()).filter(Boolean);
}
