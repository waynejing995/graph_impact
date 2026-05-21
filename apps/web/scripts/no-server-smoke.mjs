import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

const appRoot = path.resolve(import.meta.dirname, "..");
const repoRoot = path.resolve(appRoot, "../..");
const currentArtifactOptions = new Set([
  "--browser-json",
  "--in-app-browser-json",
  "--provider-json",
  "--runtime-semantic-json",
  "--semantic-quality-json",
  "--callback-audit-json",
  "--acceptance-json",
  "--web-acceptance-json",
  "--completion-json",
  "--web-package-json"
]);
const selfReferentialArtifactOptions = new Set(["--completion-json"]);
const informationalArtifactOptions = new Set(["--web-package-json"]);

function parseArgs(argv) {
  const args = { outputJson: "", currentArtifactArgs: [] };
  for (let index = 0; index < argv.length; index += 1) {
    const item = argv[index];
    if (item === "--") {
      continue;
    }
    if (item === "--output-json") {
      args.outputJson = argv[++index] ?? "";
    } else if (item.startsWith("--output-json=")) {
      args.outputJson = item.slice("--output-json=".length);
    } else {
      const equalsIndex = item.indexOf("=");
      const option = equalsIndex === -1 ? item : item.slice(0, equalsIndex);
      if (!currentArtifactOptions.has(option)) {
        throw new Error(`unknown argument: ${item}`);
      }
      if (equalsIndex === -1) {
        args.currentArtifactArgs.push(option, argv[++index] ?? "");
      } else {
        args.currentArtifactArgs.push(option, item.slice(equalsIndex + 1));
      }
    }
  }
  return args;
}

const args = parseArgs(process.argv.slice(2));
const currentArtifactInputs = snapshotCurrentArtifactInputs(args.currentArtifactArgs);

function currentArtifactInvariantArgs() {
  if (!args.currentArtifactArgs.length) {
    return ["scripts/current-artifact-invariants-smoke.mjs"];
  }
  return ["scripts/current-artifact-invariants-smoke.mjs", ...args.currentArtifactArgs];
}

function writeArtifact(outputJson, artifact) {
  if (!outputJson) {
    return;
  }
  const resolvedOutput = resolveArtifactPath(outputJson);
  mkdirSync(path.dirname(resolvedOutput), { recursive: true });
  writeFileSync(resolvedOutput, `${JSON.stringify(artifact, null, 2)}\n`, "utf8");
}

function resolveArtifactPath(inputPath) {
  return path.isAbsolute(inputPath) ? inputPath : path.join(repoRoot, inputPath);
}

function sha256(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

function snapshotCurrentArtifactInputs(inputArgs) {
  const inputs = [];
  for (let index = 0; index < inputArgs.length; index += 2) {
    const option = inputArgs[index];
    const inputPath = inputArgs[index + 1] ?? "";
    const resolvedPath = resolveArtifactPath(inputPath);
    const hashPolicy = selfReferentialArtifactOptions.has(option)
      ? "self-referential-not-final-gate-input"
      : informationalArtifactOptions.has(option)
        ? "informational"
        : "sha256";
    try {
      const bytes = readFileSync(resolvedPath);
      const input = {
        option,
        path: inputPath,
        resolved_path: resolvedPath,
        status: "loaded",
        bytes: bytes.length,
        hash_policy: hashPolicy,
        sha256: hashPolicy === "sha256" ? sha256(bytes) : ""
      };
      inputs.push(input);
    } catch (error) {
      inputs.push({
        option,
        path: inputPath,
        resolved_path: resolvedPath,
        status: "missing",
        hash_policy: hashPolicy,
        bytes: 0,
        sha256: "",
        error: error.message
      });
    }
  }
  return inputs;
}

const checks = [
  {
    label: "dbPath no-fallback route smoke",
    command: process.execPath,
    args: ["scripts/dbpath-no-fallback-smoke.mjs"]
  },
  {
    label: "request path helper smoke",
    command: process.execPath,
    args: ["--experimental-strip-types", "scripts/request-paths-smoke.mjs"]
  },
  {
    label: "Playwright config smoke",
    command: process.execPath,
    args: ["--experimental-strip-types", "scripts/playwright-config-smoke.mjs"]
  },
  {
    label: "no-mock Playwright hygiene smoke",
    command: process.execPath,
    args: ["scripts/no-mock-hygiene-smoke.mjs"]
  },
  {
    label: "acceptance route command wiring smoke",
    command: process.execPath,
    args: ["scripts/acceptance-route-smoke.mjs"]
  },
  {
    label: "current artifact invariants smoke",
    command: process.execPath,
    args: currentArtifactInvariantArgs()
  },
  {
    label: "browser e2e artifact producer smoke",
    command: process.execPath,
    args: ["scripts/browser-e2e-artifact-smoke.mjs"]
  },
  {
    label: "Playwright discovery smoke",
    command: "pnpm",
    args: ["exec", "playwright", "test", "--list"],
    env: { PLAYWRIGHT_SKIP_WEB_SERVER: "1" },
    expectOutput: ["Total: 111 tests in 3 files", "acceptance page runs no-mock AQ01 through the real workbench API"],
    successMessage: "Playwright discovery registered 111 tests"
  },
  {
    label: "Browser preflight existing-target shape smoke",
    command: process.execPath,
    args: ["scripts/browser-gate-preflight.mjs", "--timeout-ms", "500", "--allow-blocked", "--require-existing-target"],
    expectOutput: [
      '"preflight_mode": "existing_target"',
      '"listen_capability"',
      '"target_port"',
      '"target_connect"',
      '"status": "skipped"',
      '"code": "NOT_APPLICABLE"'
    ],
    rejectOutput: ["local listen capability blocked", "target port 3100 blocked"],
    successMessage: "browser preflight existing-target shape verified"
  }
];

const results = [];
let failureReason = "";

for (const check of checks) {
  console.log(`\n[no-server-smoke] ${check.label}`);
  const result = spawnSync(check.command, check.args, {
    cwd: appRoot,
    env: { ...process.env, ...(check.env ?? {}) },
    encoding: "utf8",
    stdio: "pipe"
  });
  if (result.stdout) {
    process.stdout.write(result.stdout);
  }
  if (result.stderr) {
    process.stderr.write(result.stderr);
  }
  if (result.error) {
    throw result.error;
  }
  const checkResult = {
    label: check.label,
    status: result.status === 0 ? "pass" : "fail",
    exit_code: result.status ?? 1,
    expected_output: check.expectOutput ?? [],
    rejected_output: check.rejectOutput ?? []
  };
  results.push(checkResult);
  if (result.status !== 0) {
    failureReason = `${check.label} exited with ${result.status ?? 1}`;
    console.error(`[no-server-smoke] failed: ${check.label}`);
    writeArtifact(args.outputJson, renderArtifact(results, failureReason));
    process.exit(result.status ?? 1);
  }
  if (check.expectOutput) {
    const output = `${result.stdout ?? ""}\n${result.stderr ?? ""}`;
    for (const expected of check.expectOutput) {
      if (!output.includes(expected)) {
        failureReason = `${check.label} missing expected output: ${expected}`;
        checkResult.status = "fail";
        console.error(`[no-server-smoke] missing expected output for ${check.label}: ${expected}`);
        writeArtifact(args.outputJson, renderArtifact(results, failureReason));
        process.exit(1);
      }
    }
    for (const rejected of check.rejectOutput ?? []) {
      if (output.includes(rejected)) {
        failureReason = `${check.label} included rejected output: ${rejected}`;
        checkResult.status = "fail";
        console.error(`[no-server-smoke] rejected output for ${check.label}: ${rejected}`);
        writeArtifact(args.outputJson, renderArtifact(results, failureReason));
        process.exit(1);
      }
    }
    console.log(`[no-server-smoke] ${check.successMessage ?? `${check.label} output verified`}`);
  }
}

console.log("\n[no-server-smoke] all checks passed");
writeArtifact(args.outputJson, renderArtifact(results, ""));

function renderArtifact(checkResults, failure) {
  const passed = checkResults.filter((item) => item.status === "pass").length;
  const failed = checkResults.filter((item) => item.status !== "pass").length;
  return {
    source: "asip.web.no_server_smoke",
    generated_at: new Date().toISOString(),
    gate_status: failed === 0 && !failure ? "pass" : "blocked",
    current_artifact_args: args.currentArtifactArgs,
    current_artifact_inputs: currentArtifactInputs,
    summary: {
      total: checkResults.length,
      passed,
      failed
    },
    checks: checkResults,
    failure_reasons: failure ? [failure] : []
  };
}
