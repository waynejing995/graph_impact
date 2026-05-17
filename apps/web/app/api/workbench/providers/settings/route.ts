import { NextResponse } from "next/server";
import { defaultDbPath, runAsipCli } from "@/lib/asip-cli";

export function GET(request: Request) {
  const dbPath = new URL(request.url).searchParams.get("dbPath")?.trim() || defaultDbPath;
  try {
    return NextResponse.json(runAsipCli<Record<string, unknown>>(["provider-show", "--db", dbPath]));
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "provider settings read failed" },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as Record<string, unknown> & { dbPath?: string };
  const { dbPath: requestedDbPath, ...settings } = body;
  const dbPath = typeof requestedDbPath === "string" && requestedDbPath.trim() ? requestedDbPath.trim() : defaultDbPath;
  try {
    return NextResponse.json(
      runAsipCli<Record<string, unknown>>([
        "provider-save",
        "--db",
        dbPath,
        "--settings-json",
        JSON.stringify(settings)
      ])
    );
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "provider settings save failed" },
      { status: 500 }
    );
  }
}
