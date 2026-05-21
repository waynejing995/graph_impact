import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";

const appRoot = path.resolve(import.meta.dirname, "..");
const specFiles = [
  "tests/workbench-smoke.spec.ts",
  "tests/workbench-api.spec.ts",
  "tests/visual-anchor-routes.spec.ts"
];

function findMatchingBrace(source, openIndex) {
  let depth = 0;
  let state = "";
  for (let index = openIndex; index < source.length; index += 1) {
    const char = source[index];
    const next = source[index + 1] ?? "";
    if (state === "line") {
      if (char === "\n") {
        state = "";
      }
      continue;
    }
    if (state === "block") {
      if (char === "*" && next === "/") {
        index += 1;
        state = "";
      }
      continue;
    }
    if (state === "single" || state === "double" || state === "template") {
      const quote = state === "single" ? "'" : state === "double" ? '"' : "`";
      if (char === "\\") {
        index += 1;
        continue;
      }
      if (char === quote) {
        state = "";
      }
      continue;
    }
    if (char === "/" && next === "/") {
      index += 1;
      state = "line";
      continue;
    }
    if (char === "/" && next === "*") {
      index += 1;
      state = "block";
      continue;
    }
    if (char === "'") {
      state = "single";
      continue;
    }
    if (char === '"') {
      state = "double";
      continue;
    }
    if (char === "`") {
      state = "template";
      continue;
    }
    if (char === "{") {
      depth += 1;
    } else if (char === "}") {
      depth -= 1;
      if (depth === 0) {
        return index;
      }
    }
  }
  return -1;
}

function noMockTests(source) {
  const tests = [];
  const pattern = /\btest\(\s*(["'`])([^"'`]*no-mock[^"'`]*)\1/gi;
  for (const match of source.matchAll(pattern)) {
    const bodyStart = source.indexOf("{", match.index ?? 0);
    assert.notEqual(bodyStart, -1, `cannot find test body for ${match[2]}`);
    const bodyEnd = findMatchingBrace(source, bodyStart);
    assert.notEqual(bodyEnd, -1, `cannot find matching test body brace for ${match[2]}`);
    tests.push({ title: match[2], body: source.slice(bodyStart, bodyEnd + 1) });
  }
  return tests;
}

let checked = 0;
for (const specFile of specFiles) {
  const source = readFileSync(path.join(appRoot, specFile), "utf8");
  for (const testCase of noMockTests(source)) {
    checked += 1;
    assert.doesNotMatch(
      testCase.body,
      /page\.route\s*\([^]*?route\.fulfill\s*\(/,
      `${specFile}: "${testCase.title}" is named no-mock but fulfills a Playwright route`
    );
  }
}

assert.ok(checked > 0, "expected at least one no-mock Playwright test");
console.log(`no-mock hygiene smoke passed (${checked} tests checked)`);
