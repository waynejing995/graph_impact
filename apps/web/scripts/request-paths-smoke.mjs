import assert from "node:assert/strict";

const { explicitTextOrError, normalizeStringList, textOrFallback } = await import("../lib/request-paths.ts");

assert.equal(textOrFallback(undefined, "fallback"), "fallback");
assert.equal(textOrFallback(null, "fallback"), "fallback");
assert.equal(textOrFallback("   ", "fallback"), "fallback");
assert.equal(textOrFallback("  /tmp/asip.db  ", "fallback"), "/tmp/asip.db");

assert.equal(explicitTextOrError(undefined, "dbPath"), undefined);
assert.equal(explicitTextOrError(null, "dbPath"), undefined);
assert.equal(explicitTextOrError("  /tmp/asip.db  ", "dbPath"), "/tmp/asip.db");
assert.throws(() => explicitTextOrError("", "dbPath"), /dbPath cannot be blank/);
assert.throws(() => explicitTextOrError("   ", "dbPath"), /dbPath cannot be blank/);

assert.deepEqual(normalizeStringList(undefined), []);
assert.deepEqual(normalizeStringList([" linux-amdgpu ", "", "  mxgpu"]), ["linux-amdgpu", "mxgpu"]);

console.log("request path helpers smoke passed");
