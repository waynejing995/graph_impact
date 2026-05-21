import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";

const appRoot = path.resolve(import.meta.dirname, "..");
const routeSource = readFileSync(path.join(appRoot, "app/api/workbench/acceptance/run/route.ts"), "utf8");

assert.match(routeSource, /explicitTextOrError\(body\.dbPath,\s*"dbPath"\)/);
assert.match(routeSource, /const queryIds = normalizeList\(body\.queryIds \?\? \(body\.queryId \? \[body\.queryId\] : \[\]\)\)/);
assert.match(routeSource, /const surfaces = normalizeList\(body\.surfaces \?\? \["CLI", "API", "MCP"\]\)/);
assert.match(routeSource, /if \(dbPath === defaultDbPath\) \{\s*ensureWorkbenchIndex\(\);\s*\}/);
assert.match(routeSource, /const args = \["acceptance", "--db", dbPath, "--full"\]/);
assert.match(routeSource, /args\.push\("--query-id", queryId\)/);
assert.match(routeSource, /args\.push\("--surface", surface\)/);
assert.doesNotMatch(routeSource, /body\.dbPath\?\.trim\(\)\s*\|\|\s*defaultDbPath/);
assert.doesNotMatch(routeSource, /ensureWorkbenchIndex\(\);\s*const args/s);

console.log("acceptance route smoke passed");
