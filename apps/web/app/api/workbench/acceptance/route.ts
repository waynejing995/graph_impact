import { NextResponse } from "next/server";
import { listAcceptanceRuns } from "@/lib/workbench-data";

export function GET() {
  return NextResponse.json({ runs: listAcceptanceRuns() });
}
