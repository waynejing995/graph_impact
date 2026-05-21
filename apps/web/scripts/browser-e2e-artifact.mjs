import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

const appRoot = path.resolve(import.meta.dirname, "..");
const repoRoot = path.resolve(appRoot, "../..");
const requiredBrowserE2eTests = [
  "acceptance page runs no-mock AQ01 through the real workbench API",
  "graph page uses URL dbPath for no-mock graph and query requests",
  "graph page loads current data/asip.db through browser and API",
  "graph page filters no-mock graph layers and shows edge provenance",
  "evidence page initial query uses URL dbPath without default DB fallback"
];
const requiredBrowserE2eTestFile = "workbench-smoke.spec.ts";
const currentDbProbePrefix = "ASIP_BROWSER_CURRENT_DB_PROBE ";
const requiredCurrentDbProbeSurfaces = [
  "graph_page_api_request",
  "direct_api_graph_request",
  "graph_page_concept_detail_selection"
];

function parseArgs(argv) {
  const args = {
    outputJson: "",
    reportJson: "",
    baseUrl: process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3100",
    dbPath: process.env.ASIP_BROWSER_E2E_DB_PATH ?? "",
    latestIndexJobId: process.env.ASIP_BROWSER_E2E_LATEST_INDEX_JOB_ID ?? "",
    latestGraphRebuildJobId: process.env.ASIP_BROWSER_E2E_LATEST_GRAPH_REBUILD_JOB_ID ?? "",
    targetUrls: [],
    allowBlocked: false,
    skipWebServer: process.env.PLAYWRIGHT_SKIP_WEB_SERVER === "1",
    extraPlaywrightArgs: [],
    help: false
  };
  for (let index = 0; index < argv.length; index += 1) {
    const item = argv[index];
    if (item === "--") {
      args.extraPlaywrightArgs.push(...argv.slice(index + 1));
      break;
    } else if (item === "--help" || item === "-h") {
      args.help = true;
    } else if (item === "--allow-blocked") {
      args.allowBlocked = true;
    } else if (item === "--skip-web-server") {
      args.skipWebServer = true;
    } else if (item === "--base-url") {
      args.baseUrl = argv[++index] ?? "";
    } else if (item.startsWith("--base-url=")) {
      args.baseUrl = item.slice("--base-url=".length);
    } else if (item === "--db-path") {
      args.dbPath = argv[++index] ?? "";
    } else if (item.startsWith("--db-path=")) {
      args.dbPath = item.slice("--db-path=".length);
    } else if (item === "--latest-index-job-id") {
      args.latestIndexJobId = argv[++index] ?? "";
    } else if (item.startsWith("--latest-index-job-id=")) {
      args.latestIndexJobId = item.slice("--latest-index-job-id=".length);
    } else if (item === "--latest-graph-rebuild-job-id") {
      args.latestGraphRebuildJobId = argv[++index] ?? "";
    } else if (item.startsWith("--latest-graph-rebuild-job-id=")) {
      args.latestGraphRebuildJobId = item.slice("--latest-graph-rebuild-job-id=".length);
    } else if (item === "--target-url") {
      args.targetUrls.push(argv[++index] ?? "");
    } else if (item.startsWith("--target-url=")) {
      args.targetUrls.push(item.slice("--target-url=".length));
    } else if (item === "--output-json") {
      args.outputJson = argv[++index] ?? "";
    } else if (item.startsWith("--output-json=")) {
      args.outputJson = item.slice("--output-json=".length);
    } else if (item === "--report-json") {
      args.reportJson = argv[++index] ?? "";
    } else if (item.startsWith("--report-json=")) {
      args.reportJson = item.slice("--report-json=".length);
    } else {
      throw new Error(`unknown argument: ${item}`);
    }
  }
  if (!args.baseUrl) {
    throw new Error("--base-url must not be empty");
  }
  return args;
}

function printHelp() {
  process.stdout.write(`Usage: node scripts/browser-e2e-artifact.mjs [options] [-- playwright args...]

Runs Playwright and writes an asip.web.browser_e2e artifact.

Options:
  --output-json <path>     Write the artifact JSON to a file.
  --report-json <path>     Build artifact from an existing Playwright JSON report.
  --base-url <url>         Set PLAYWRIGHT_BASE_URL for the run.
  --db-path <path>         Bind the artifact to the DB path under browser test.
  --latest-index-job-id <id>
                           Bind the artifact to the current DB index job.
  --latest-graph-rebuild-job-id <id>
                           Bind the artifact to the current graph rebuild job.
  --target-url <url>       Record a target URL containing dbPath; repeatable.
  --skip-web-server        Set PLAYWRIGHT_SKIP_WEB_SERVER=1 for existing-target runs.
  --allow-blocked          Exit 0 even when Playwright fails, after writing a blocked artifact.
  --help                   Show this help.
`);
}

function writeArtifact(outputJson, artifact) {
  const rendered = `${JSON.stringify(artifact, null, 2)}\n`;
  if (outputJson) {
    mkdirSync(path.dirname(outputJson), { recursive: true });
    writeFileSync(outputJson, rendered, "utf8");
  }
  process.stdout.write(rendered);
}

function tail(text, limit = 4000) {
  if (!text) {
    return "";
  }
  return text.length <= limit ? text : text.slice(text.length - limit);
}

function sha256(text) {
  return createHash("sha256").update(text).digest("hex");
}

function currentRepoHead() {
  const result = spawnSync("git", ["rev-parse", "HEAD"], {
    cwd: repoRoot,
    encoding: "utf8",
    stdio: "pipe"
  });
  return result.status === 0 ? result.stdout.trim() : "";
}

function summarizePlaywrightReport(report) {
  const stats = report?.stats && typeof report.stats === "object" ? report.stats : {};
  const expected = Number(stats.expected ?? 0);
  const unexpected = Number(stats.unexpected ?? 0);
  const flaky = Number(stats.flaky ?? 0);
  const skipped = Number(stats.skipped ?? 0);
  const total = expected + unexpected + flaky + skipped;
  if (total > 0) {
    return {
      total,
      passed: expected,
      failed: unexpected,
      flaky,
      skipped,
      duration_ms: Number(stats.duration ?? 0)
    };
  }
  return summarizeSuites(report?.suites ?? []);
}

function summarizeSuites(suites) {
  const summary = { total: 0, passed: 0, failed: 0, flaky: 0, skipped: 0, duration_ms: 0 };
  const visitSuite = (suite) => {
    for (const child of suite.suites ?? []) {
      visitSuite(child);
    }
    for (const spec of suite.specs ?? []) {
      for (const test of spec.tests ?? []) {
        summary.total += 1;
        const outcome = String(test.outcome ?? test.status ?? "");
        if (outcome === "expected") {
          summary.passed += 1;
        } else if (outcome === "skipped") {
          summary.skipped += 1;
        } else if (outcome === "flaky") {
          summary.flaky += 1;
        } else {
          summary.failed += 1;
        }
      }
    }
  };
  for (const suite of suites) {
    visitSuite(suite);
  }
  return summary;
}

function collectFailureReasons(report, exitCode, stderr, parseError) {
  const reasons = [];
  if (exitCode !== 0) {
    reasons.push(`Playwright exited with ${exitCode}`);
  }
  if (parseError) {
    reasons.push(`Playwright JSON report could not be parsed: ${parseError.message}`);
  }
  for (const error of report?.errors ?? []) {
    const message = typeof error?.message === "string" ? error.message : JSON.stringify(error);
    if (message) {
      reasons.push(message);
    }
  }
  const failedTitles = [];
  const visitSuite = (suite) => {
    for (const child of suite.suites ?? []) {
      visitSuite(child);
    }
    for (const spec of suite.specs ?? []) {
      for (const test of spec.tests ?? []) {
        const outcome = String(test.outcome ?? test.status ?? "");
        if (outcome && !["expected", "skipped"].includes(outcome)) {
          failedTitles.push(spec.title ?? test.title ?? "unknown Playwright test");
        }
      }
    }
  };
  for (const suite of report?.suites ?? []) {
    visitSuite(suite);
  }
  for (const title of failedTitles.slice(0, 20)) {
    reasons.push(`failed Playwright test: ${title}`);
  }
  if (!reasons.length && stderr.trim()) {
    reasons.push(tail(stderr.trim(), 1000));
  }
  return [...new Set(reasons)];
}

function collectTestOutcomes(report) {
  const outcomes = new Map();
  const visitSuite = (suite, parentSources = []) => {
    const suiteSources = [...parentSources, ...sourceValues(suite)];
    for (const child of suite.suites ?? []) {
      visitSuite(child, suiteSources);
    }
    for (const spec of suite.specs ?? []) {
      for (const test of spec.tests ?? []) {
        const title = String(spec.title ?? test.title ?? "").trim();
        if (!title) {
          continue;
        }
        const outcome = String(test.outcome ?? test.status ?? "");
        const sources = [...suiteSources, ...sourceValues(spec), ...sourceValues(test)];
        const file =
          sources.find((source) => source.includes(requiredBrowserE2eTestFile) && source.includes("/")) ??
          sources.find((source) => source.includes(requiredBrowserE2eTestFile)) ??
          sources.at(-1) ??
          "";
        const sourceMatches = file.includes(requiredBrowserE2eTestFile);
        const existing = outcomes.get(title);
        if (existing?.status === "expected" && existing?.sourceMatches) {
          continue;
        }
        if (outcome === "expected" && sourceMatches) {
          outcomes.set(title, { status: "expected", file, sourceMatches });
        } else if (!existing || existing.status !== "expected") {
          outcomes.set(title, { status: outcome || "unknown", file, sourceMatches });
        }
      }
    }
  };
  for (const suite of report?.suites ?? []) {
    visitSuite(suite);
  }
  return outcomes;
}

function requiredTestResults(report) {
  const outcomes = collectTestOutcomes(report);
  return requiredBrowserE2eTests.map((title) => {
    const result = outcomes.get(title);
    if (!result) {
      return { title, status: "missing", file: "" };
    }
    if (result.status === "expected" && result.sourceMatches) {
      return { title, status: "pass", file: result.file };
    }
    if (result.status === "expected") {
      return { title, status: "wrong_source", file: result.file };
    }
    return { title, status: result.status || "unknown", file: result.file };
  });
}

function collectCurrentDbProbes(report) {
  const probes = [];
  const appendProbePayload = (payload) => {
    if (Array.isArray(payload)) {
      for (const item of payload) {
        if (item && typeof item === "object") {
          probes.push(item);
        }
      }
    } else if (payload && typeof payload === "object") {
      probes.push(payload);
    }
  };
  const parseProbeText = (text) => {
    for (const line of String(text ?? "").split(/\r?\n/u)) {
      const prefixIndex = line.indexOf(currentDbProbePrefix);
      if (prefixIndex < 0) {
        continue;
      }
      const rawPayload = line.slice(prefixIndex + currentDbProbePrefix.length).trim();
      if (!rawPayload) {
        continue;
      }
      try {
        appendProbePayload(JSON.parse(rawPayload));
      } catch {
        probes.push({ surface: "parse_error", raw: rawPayload });
      }
    }
  };
  const visit = (item) => {
    if (Array.isArray(item)) {
      for (const child of item) {
        visit(child);
      }
      return;
    }
    if (!item || typeof item !== "object") {
      return;
    }
    for (const entry of item.stdout ?? []) {
      parseProbeText(typeof entry === "string" ? entry : entry?.text ?? "");
    }
    for (const attachment of item.attachments ?? []) {
      if (attachment?.name !== "asip-current-db-probes") {
        continue;
      }
      const body = attachment.body ?? attachment.text ?? "";
      if (body) {
        try {
          appendProbePayload(JSON.parse(String(body)));
        } catch {
          parseProbeText(body);
        }
      } else if (attachment.path) {
        try {
          appendProbePayload(JSON.parse(readFileSync(attachment.path, "utf8")));
        } catch {
          // The stdout marker is the durable path for JSON reports; ignore unreadable attachment paths.
        }
      }
    }
    for (const value of Object.values(item)) {
      if (value && typeof value === "object") {
        visit(value);
      }
    }
  };
  visit(report);
  const deduped = [];
  const seen = new Set();
  for (const probe of probes) {
    const key = JSON.stringify(probe);
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    deduped.push(probe);
  }
  return deduped;
}

function sourceValues(item) {
  const values = [];
  for (const key of ["file", "path", "title"]) {
    const value = item?.[key];
    if (value) {
      values.push(String(value));
    }
  }
  if (item?.location?.file) {
    values.push(String(item.location.file));
  }
  return values;
}

function isPositiveIntegerText(value) {
  return /^\d+$/u.test(String(value ?? "").trim()) && Number(value) > 0;
}

function sameDbPath(left, right) {
  if (!left || !right) {
    return false;
  }
  return path.resolve(process.cwd(), String(left)) === path.resolve(process.cwd(), String(right));
}

function targetUrlHasDbPath(targetUrl, dbPath) {
  try {
    const parsed = new URL(targetUrl);
    return parsed.searchParams.getAll("dbPath").some((value) => sameDbPath(value, dbPath));
  } catch {
    return false;
  }
}

function collectBindingFailureReasons(args) {
  const reasons = [];
  if (!String(args.dbPath ?? "").trim()) {
    reasons.push("browser e2e db_path is missing");
  }
  if (!isPositiveIntegerText(args.latestIndexJobId)) {
    reasons.push(`browser e2e latest_index_job_id is missing or invalid: ${args.latestIndexJobId || "missing"}`);
  }
  if (!isPositiveIntegerText(args.latestGraphRebuildJobId)) {
    reasons.push(
      `browser e2e latest_graph_rebuild_job_id is missing or invalid: ${args.latestGraphRebuildJobId || "missing"}`
    );
  }
  if (!args.targetUrls.some((targetUrl) => targetUrlHasDbPath(targetUrl, args.dbPath))) {
    reasons.push("browser e2e target_urls do not include current dbPath");
  }
  return reasons;
}

function collectCurrentDbProbeFailureReasons(probes, args) {
  const reasons = [];
  if (!args.dbPath) {
    return reasons;
  }
  if (!Array.isArray(probes) || probes.length === 0) {
    return ["browser e2e current_db_probes are missing"];
  }
  for (const surface of requiredCurrentDbProbeSurfaces) {
    const probe = probes.find((item) => item?.surface === surface);
    if (!probe) {
      reasons.push(`browser e2e current_db_probes missing surface: ${surface}`);
      continue;
    }
    const status = Number(probe.status ?? 0);
    if (status !== 200) {
      reasons.push(`browser e2e ${surface} status=${status}`);
    }
    if (!sameDbPath(probe.db_path, args.dbPath)) {
      reasons.push(`browser e2e ${surface} db_path does not match current dbPath`);
    }
    if (!targetUrlHasDbPath(String(probe.url ?? ""), args.dbPath)) {
      reasons.push(`browser e2e ${surface} url does not include current dbPath`);
    }
    if (Number(probe.node_count ?? 0) <= 0) {
      reasons.push(`browser e2e ${surface} node_count is zero`);
    }
    if (Number(probe.edge_count ?? 0) <= 0) {
      reasons.push(`browser e2e ${surface} edge_count is zero`);
    }
    if (!/^[a-f0-9]{64}$/u.test(String(probe.response_sha256 ?? ""))) {
      reasons.push(`browser e2e ${surface} response_sha256 is missing or invalid`);
    }
    if (args.latestIndexJobId && String(probe.latest_index_job_id ?? "") !== String(args.latestIndexJobId)) {
      reasons.push(`browser e2e ${surface} latest_index_job_id does not match current DB`);
    }
    if (
      args.latestGraphRebuildJobId &&
      String(probe.latest_graph_rebuild_job_id ?? "") !== String(args.latestGraphRebuildJobId)
    ) {
      reasons.push(`browser e2e ${surface} latest_graph_rebuild_job_id does not match current DB`);
    }
    if (surface === "graph_page_concept_detail_selection") {
      reasons.push(...collectConceptDetailProbeFailureReasons(probe));
    }
  }
  return reasons;
}

function collectConceptDetailProbeFailureReasons(probe) {
  const reasons = [];
  if (!String(probe.selected_node_id ?? "").includes(":concept:")) {
    reasons.push("browser e2e concept detail selected_node_id is not a concept node");
  }
  if (String(probe.selected_kind ?? "") !== "function") {
    reasons.push(`browser e2e concept detail selected_kind=${probe.selected_kind ?? "missing"}`);
  }
  if (!String(probe.selected_label ?? "").trim()) {
    reasons.push("browser e2e concept detail selected_label is missing");
  }
  if (Number(probe.implementation_count ?? 0) <= 1) {
    reasons.push(`browser e2e concept detail implementation_count=${probe.implementation_count ?? "missing"}`);
  }
  if (Number(probe.listed_implementation_count ?? 0) !== Number(probe.implementation_count ?? -1)) {
    reasons.push(
      `browser e2e concept detail listed_implementation_count=${probe.listed_implementation_count ?? "missing"} does not match implementation_count=${probe.implementation_count ?? "missing"}`
    );
  }
  if (
    probe.raw_implementation_record_count !== undefined &&
    Number(probe.raw_implementation_record_count ?? 0) < Number(probe.implementation_count ?? 0)
  ) {
    reasons.push(
      `browser e2e concept detail raw_implementation_record_count=${probe.raw_implementation_record_count} is below implementation_count=${probe.implementation_count}`
    );
  }
  if (!String(probe.selected_implementation ?? "").trim()) {
    reasons.push("browser e2e concept detail selected_implementation is missing");
  }
  if (String(probe.selection_input ?? "") !== "canvas-node-click") {
    reasons.push(
      `browser e2e concept detail selection_input=${probe.selection_input ?? "missing"} is not canvas-node-click`
    );
  }
  if (String(probe.hovered_canvas_node_id ?? "") !== String(probe.selected_node_id ?? "")) {
    reasons.push(
      `browser e2e concept detail hovered_canvas_node_id=${probe.hovered_canvas_node_id ?? "missing"} does not match selected_node_id=${probe.selected_node_id ?? "missing"}`
    );
  }
  if (!Number.isFinite(Number(probe.canvas_click_x)) || Number(probe.canvas_click_x) < 0) {
    reasons.push(`browser e2e concept detail canvas_click_x=${probe.canvas_click_x ?? "missing"}`);
  }
  if (!Number.isFinite(Number(probe.canvas_click_y)) || Number(probe.canvas_click_y) < 0) {
    reasons.push(`browser e2e concept detail canvas_click_y=${probe.canvas_click_y ?? "missing"}`);
  }
  if (String(probe.detail_heading ?? "") !== "Concept Generated From") {
    reasons.push(`browser e2e concept detail heading=${probe.detail_heading ?? "missing"}`);
  }
  if (probe.detail_truncated !== false) {
    reasons.push(`browser e2e concept detail_truncated=${probe.detail_truncated ?? "missing"}`);
  }
  return reasons;
}

const args = parseArgs(process.argv.slice(2));
if (args.help) {
  printHelp();
  process.exit(0);
}

const commandArgs = ["exec", "playwright", "test", "--reporter=json", ...args.extraPlaywrightArgs];
const startedAt = Date.now();
const result = args.reportJson
  ? {
      status: 0,
      stdout: readFileSync(args.reportJson, "utf8"),
      stderr: "",
      error: null
    }
  : spawnSync("pnpm", commandArgs, {
      cwd: appRoot,
      env: {
        ...process.env,
        PLAYWRIGHT_BASE_URL: args.baseUrl,
        ...(args.dbPath ? { ASIP_BROWSER_E2E_DB_PATH: args.dbPath } : {}),
        ...(args.latestIndexJobId ? { ASIP_BROWSER_E2E_LATEST_INDEX_JOB_ID: args.latestIndexJobId } : {}),
        ...(args.latestGraphRebuildJobId
          ? { ASIP_BROWSER_E2E_LATEST_GRAPH_REBUILD_JOB_ID: args.latestGraphRebuildJobId }
          : {}),
        ...(args.skipWebServer ? { PLAYWRIGHT_SKIP_WEB_SERVER: "1" } : {})
      },
      encoding: "utf8",
      stdio: "pipe",
      maxBuffer: 50 * 1024 * 1024
    });
const elapsedMs = Date.now() - startedAt;
const rawReportText = result.stdout ?? "";
const outputPath = args.outputJson ? path.resolve(process.cwd(), args.outputJson) : "";
const rawReportPath = args.reportJson
  ? path.resolve(process.cwd(), args.reportJson)
  : outputPath
    ? outputPath.replace(/\.json$/u, ".playwright-report.json")
    : "";
if (!args.reportJson && rawReportPath && rawReportText) {
  mkdirSync(path.dirname(rawReportPath), { recursive: true });
  writeFileSync(rawReportPath, rawReportText, "utf8");
}

let report = null;
let parseError = null;
try {
  report = rawReportText ? JSON.parse(rawReportText) : null;
} catch (error) {
  parseError = error;
}

const exitCode = result.status ?? (result.error ? 1 : 0);
const summary = report ? summarizePlaywrightReport(report) : { total: 0, passed: 0, failed: 0, flaky: 0, skipped: 0, duration_ms: elapsedMs };
const failureReasons = collectFailureReasons(report, exitCode, result.stderr ?? "", parseError);
const requiredTests = requiredTestResults(report);
const currentDbProbes = collectCurrentDbProbes(report);
const missingRequiredTests = requiredTests.filter((test) => test.status !== "pass");
if (result.error) {
  failureReasons.unshift(`Playwright process failed: ${result.error.message}`);
}
if (summary.failed > 0) {
  failureReasons.push(`Playwright summary failed=${summary.failed}`);
}
if (summary.total <= 0) {
  failureReasons.push("Playwright reported no tests");
} else if (summary.passed <= 0) {
  failureReasons.push("Playwright reported no passed tests");
}
for (const test of missingRequiredTests) {
  failureReasons.push(`required no-mock browser test did not pass: ${test.title} (${test.status})`);
}
if (args.reportJson) {
  failureReasons.push("offline Playwright JSON report cannot satisfy live browser e2e proof");
}
failureReasons.push(...collectBindingFailureReasons(args));
failureReasons.push(...collectCurrentDbProbeFailureReasons(currentDbProbes, args));

const passed = exitCode === 0 && failureReasons.length === 0 && summary.failed === 0 && summary.passed > 0;
const artifact = {
  source: "asip.web.browser_e2e",
  generated_at: new Date().toISOString(),
  repo_head: currentRepoHead(),
  base_url: args.baseUrl,
  db_path: args.dbPath,
  latest_index_job_id: args.latestIndexJobId,
  latest_graph_rebuild_job_id: args.latestGraphRebuildJobId,
  target_urls: args.targetUrls,
  skip_web_server: args.skipWebServer,
  command: args.reportJson ? ["playwright-json-report", args.reportJson] : ["pnpm", ...commandArgs],
  report_json: rawReportPath,
  report_sha256: rawReportText ? sha256(rawReportText) : "",
  report_bytes: Buffer.byteLength(rawReportText, "utf8"),
  exit_code: exitCode,
  gate_status: passed ? "pass" : "blocked",
  e2e_status: passed ? "pass" : "blocked",
  summary,
  required_tests: requiredTests,
  current_db_probes: currentDbProbes,
  failure_reasons: failureReasons,
  stdout_tail: parseError ? tail(result.stdout ?? "") : "",
  stderr_tail: tail(result.stderr ?? "")
};

writeArtifact(args.outputJson, artifact);

if (!passed && !args.allowBlocked) {
  process.exitCode = exitCode || 2;
}
