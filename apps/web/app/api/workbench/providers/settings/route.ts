import { NextResponse } from "next/server";
import { defaultDbPath, runAsipCli } from "@/lib/asip-cli";
import { explicitTextOrError } from "@/lib/request-paths";

export function GET(request: Request) {
  let dbPath = defaultDbPath;
  try {
    dbPath = explicitTextOrError(new URL(request.url).searchParams.get("dbPath"), "dbPath") ?? defaultDbPath;
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "dbPath cannot be blank" },
      { status: 400 }
    );
  }
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
  let dbPath = defaultDbPath;
  try {
    dbPath = explicitTextOrError(requestedDbPath, "dbPath") ?? defaultDbPath;
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "dbPath cannot be blank" },
      { status: 400 }
    );
  }
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
