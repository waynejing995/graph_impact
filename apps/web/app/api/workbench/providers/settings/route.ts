import { NextResponse } from "next/server";
import { defaultDbPath, runAsipCli } from "@/lib/asip-cli";

export function GET() {
  try {
    return NextResponse.json(runAsipCli<Record<string, unknown>>(["provider-show", "--db", defaultDbPath]));
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "provider settings read failed" },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  const settings = (await request.json().catch(() => ({}))) as Record<string, unknown>;
  try {
    return NextResponse.json(
      runAsipCli<Record<string, unknown>>([
        "provider-save",
        "--db",
        defaultDbPath,
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
