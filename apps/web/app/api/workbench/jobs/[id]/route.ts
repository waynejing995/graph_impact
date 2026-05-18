import { NextRequest, NextResponse } from "next/server";
import { defaultDbPath, runAsipCli } from "@/lib/asip-cli";

type RouteContext = {
  params: Promise<{ id: string }>;
};

export async function GET(request: NextRequest, context: RouteContext) {
  const { id } = await context.params;
  const dbPath = request.nextUrl.searchParams.get("dbPath")?.trim() || defaultDbPath;
  const jobId = id?.trim();
  if (!jobId) {
    return NextResponse.json({ error: "job id is required" }, { status: 400 });
  }
  try {
    return NextResponse.json(runAsipCli<Record<string, unknown>>(["jobs", "--db", dbPath, "--id", jobId]));
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "job not found" },
      { status: 404 }
    );
  }
}
