import { NextRequest, NextResponse } from "next/server";
import { defaultDbPath, runAsipCli } from "@/lib/asip-cli";

export function GET(request: NextRequest) {
  const dbPath = request.nextUrl.searchParams.get("dbPath")?.trim() || defaultDbPath;
  const limit = request.nextUrl.searchParams.get("limit")?.trim();
  try {
    const args = ["jobs", "--db", dbPath];
    if (limit) {
      args.push("--limit", limit);
    }
    return NextResponse.json(runAsipCli<Record<string, unknown>>(args));
  } catch (error) {
    return NextResponse.json(
      { jobs: [], error: error instanceof Error ? error.message : "jobs failed" },
      { status: 500 }
    );
  }
}
