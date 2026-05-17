import { NextResponse } from "next/server";
import { defaultWorkbenchLimitsPath, readWorkbenchLimits } from "@/lib/workbench-limits";

export function GET() {
  try {
    return NextResponse.json({ ...readWorkbenchLimits(), path: defaultWorkbenchLimitsPath });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "workbench limits failed" },
      { status: 500 }
    );
  }
}
