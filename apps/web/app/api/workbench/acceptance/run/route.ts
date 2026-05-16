import { NextResponse } from "next/server";
import { defaultDbPath, ensureWorkbenchIndex, runAsipCli } from "@/lib/asip-cli";

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
  const dbPath = body.dbPath?.trim() || defaultDbPath;
  const queryIds = normalizeList(body.queryIds ?? (body.queryId ? [body.queryId] : []));
  const surfaces = normalizeList(body.surfaces ?? ["CLI", "Web"]);

  try {
    if (dbPath === defaultDbPath) {
      ensureWorkbenchIndex();
    }
    const args = ["acceptance", "--db", dbPath, "--full"];
    for (const queryId of queryIds) {
      args.push("--query-id", queryId);
    }
    for (const surface of surfaces.length ? surfaces : ["CLI", "Web"]) {
      args.push("--surface", surface);
    }
    if (body.outputJson?.trim()) {
      args.push("--output-json", body.outputJson.trim());
    }
    if (body.outputMd?.trim()) {
      args.push("--output-md", body.outputMd.trim());
    }
    return NextResponse.json(runAsipCli<Record<string, unknown>>(args));
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
