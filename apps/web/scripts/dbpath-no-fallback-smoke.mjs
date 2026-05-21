import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";

const repoRoot = path.resolve(import.meta.dirname, "../../..");

const dbPathRoutes = [
  "apps/web/app/api/workbench/acceptance/run/route.ts",
  "apps/web/app/api/workbench/corpora/route.ts",
  "apps/web/app/api/workbench/entities/[symbol]/route.ts",
  "apps/web/app/api/workbench/evidence/[id]/route.ts",
  "apps/web/app/api/workbench/graph/route.ts",
  "apps/web/app/api/workbench/index/route.ts",
  "apps/web/app/api/workbench/jobs/route.ts",
  "apps/web/app/api/workbench/jobs/[id]/route.ts",
  "apps/web/app/api/workbench/providers/settings/route.ts",
  "apps/web/app/api/workbench/query/route.ts",
  "apps/web/app/api/workbench/resolver-profiles/route.ts",
  "apps/web/app/api/workbench/semantic-edges/route.ts"
];

const unsafeFallbacks = [
  /dbPath[^;\n]*trim\(\)\s*\|\|\s*defaultDbPath/,
  /requestedDbPath[^;\n]*trim\(\)[^;\n]*\?\s*requestedDbPath[^;\n]*:\s*defaultDbPath/,
  /searchParams\.get\(["']dbPath["']\)\?\.trim\(\)\s*\|\|\s*defaultDbPath/
];

for (const route of dbPathRoutes) {
  const source = readFileSync(path.join(repoRoot, route), "utf8");
  assert.match(source, /explicitTextOrError/, `${route} must validate explicit blank dbPath`);
  for (const unsafeFallback of unsafeFallbacks) {
    assert.doesNotMatch(source, unsafeFallback, `${route} must not silently fallback on explicit blank dbPath`);
  }
}

const workbenchPage = readFileSync(path.join(repoRoot, "apps/web/components/workbench-page.tsx"), "utf8");
assert.match(workbenchPage, /dbPathInputPayload\(acceptanceDbPath,\s*acceptanceDbPathExplicit\)/);
assert.match(workbenchPage, /dbPathInputPayload\(acceptanceRunnerDraft\.dbPath,\s*acceptanceRunnerDbPathExplicit\)/);
assert.doesNotMatch(workbenchPage, /acceptanceDbPath\.trim\(\)\s*\?\s*\{\s*dbPath/);
assert.doesNotMatch(workbenchPage, /acceptanceRunnerDraft\.dbPath\.trim\(\)\s*\?\s*\{\s*dbPath/);

const workbenchDbPathTrimUses = workbenchPage.match(/workbenchDbPath\.trim\(\)/g) ?? [];
assert.equal(workbenchDbPathTrimUses.length, 1, "workbenchDbPath should only be trimmed inside the request helper");

console.log("dbPath no-fallback smoke passed");
