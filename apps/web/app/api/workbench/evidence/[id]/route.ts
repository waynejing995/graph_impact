import { NextRequest, NextResponse } from "next/server";
import { defaultDbPath, runAsipCli } from "@/lib/asip-cli";

type RouteContext = {
  params: Promise<{ id: string }>;
};

export async function GET(request: NextRequest, context: RouteContext) {
  const { id } = await context.params;
  const evidenceId = Number(id);
  if (!Number.isInteger(evidenceId) || evidenceId <= 0) {
    return NextResponse.json({ error: `invalid evidence id: ${id}` }, { status: 400 });
  }
  const dbPath = request.nextUrl.searchParams.get("dbPath")?.trim() || defaultDbPath;
  try {
    const payload = runAsipCli<Record<string, unknown>>([
      "evidence-detail",
      "--db",
      dbPath,
      "--id",
      String(evidenceId)
    ]);
    return NextResponse.json(payload);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "evidence detail failed" },
      { status: 404 }
    );
  }
}
