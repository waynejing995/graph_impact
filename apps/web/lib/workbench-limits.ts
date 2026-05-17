import { readFileSync } from "node:fs";
import path from "node:path";
import { repoRoot } from "@/lib/asip-cli";

export type WorkbenchLimits = {
  graph?: {
    defaultHops?: number;
    edgeBudget?: number;
    maxEdgeBudget?: number;
    visibleNodeBudget?: number;
    visibleEdgeBudget?: number;
    minimumEdgeWeight?: number;
    evidenceRowCap?: number;
    inspectorEdgePreviewLimit?: number;
    accessibilitySummaryLimit?: number;
  };
  semantic?: {
    queryLimit?: number;
    batchCandidateLimit?: number;
    batchSize?: number;
  };
  retrieval?: {
    resultLimit?: number;
  };
};

export const defaultWorkbenchLimitsPath = path.join(repoRoot, "configs/workbench-limits.json");

export function readWorkbenchLimits(): WorkbenchLimits {
  return JSON.parse(readFileSync(defaultWorkbenchLimitsPath, "utf8")) as WorkbenchLimits;
}

export function configuredInt(value: unknown): number | undefined {
  if (value === null || value === undefined || value === "") {
    return undefined;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.trunc(parsed) : undefined;
}
