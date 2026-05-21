import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

const repoRoot = path.resolve(import.meta.dirname, "../../..");

const defaultArtifacts = {
  browserJson: "docs/qa/2026-05-21-browser-e2e-current.json",
  inAppBrowserJson: "docs/qa/2026-05-20-in-app-browser-probe.json",
  providerJson: "docs/qa/2026-05-21-provider-gate-current.json",
  runtimeSemanticJson: "docs/qa/2026-05-21-runtime-semantic-freshness-qa.json",
  semanticQualityJson: "docs/qa/2026-05-21-semantic-rerank-labeled-eval.json",
  callbackAuditJson: "docs/qa/2026-05-21-callback-edge-audit-current.json",
  acceptanceJson: "docs/qa/2026-05-21-acceptance-data-asip-live-web-current.json",
  webAcceptanceJson: "docs/qa/2026-05-21-acceptance-data-asip-live-web-current.json",
  completionJson: "docs/qa/2026-05-21-current-goal-completion-gate.json",
  webPackageJson: "apps/web/package.json"
};

const optionToKey = {
  "--browser-json": "browserJson",
  "--in-app-browser-json": "inAppBrowserJson",
  "--provider-json": "providerJson",
  "--runtime-semantic-json": "runtimeSemanticJson",
  "--semantic-quality-json": "semanticQualityJson",
  "--callback-audit-json": "callbackAuditJson",
  "--acceptance-json": "acceptanceJson",
  "--web-acceptance-json": "webAcceptanceJson",
  "--completion-json": "completionJson",
  "--web-package-json": "webPackageJson"
};

function parseArgs(argv) {
  const args = { ...defaultArtifacts };
  for (let index = 0; index < argv.length; index += 1) {
    const item = argv[index];
    if (item === "--") {
      continue;
    }
    if (item === "--help" || item === "-h") {
      printHelp();
      process.exit(0);
    }
    const equalsIndex = item.indexOf("=");
    const option = equalsIndex === -1 ? item : item.slice(0, equalsIndex);
    const key = optionToKey[option];
    if (!key) {
      throw new Error(`unknown argument: ${item}`);
    }
    args[key] = equalsIndex === -1 ? argv[++index] ?? "" : item.slice(equalsIndex + 1);
    if (!args[key]) {
      throw new Error(`${option} must not be empty`);
    }
  }
  return args;
}

function printHelp() {
  process.stdout.write(`Usage: node scripts/current-artifact-invariants-smoke.mjs [options]

Checks the current ASIP QA artifact set for truthful blocked/pass invariants.

Options:
  --browser-json <path>
  --in-app-browser-json <path>
  --provider-json <path>
  --runtime-semantic-json <path>
  --semantic-quality-json <path>
  --callback-audit-json <path>
  --acceptance-json <path>
  --web-acceptance-json <path>
  --completion-json <path>
  --web-package-json <path>
  --help
`);
}

function resolvePath(inputPath) {
  return path.isAbsolute(inputPath) ? inputPath : path.join(repoRoot, inputPath);
}

function readJson(inputPath) {
  return JSON.parse(readFileSync(resolvePath(inputPath), "utf8"));
}

function repoRelativePath(inputPath) {
  const resolved = resolvePath(inputPath);
  const relative = path.relative(repoRoot, resolved);
  return relative && !relative.startsWith("..") && !path.isAbsolute(relative) ? relative : "";
}

function textFrom(value) {
  return JSON.stringify(value);
}

const requiredProviderChecks = [
  "embedding",
  "embedding_live",
  "semantic_edge_provenance",
  "doc_node_provenance",
  "semantic_edge",
];
const requiredLiveSurfaces = ["CLI", "API", "API_LIVE", "Web", "MCP", "MCP_PROTOCOL"];

function assertProviderChecks(payload, label) {
  const checks = payload?.provider_checks ?? {};
  for (const checkId of requiredProviderChecks) {
    assert.ok(checkId in checks, `${label} missing provider check ${checkId}`);
  }
}

function surfaceResult(query, surface) {
  return (query?.surface_results ?? []).find((result) => result.surface === surface);
}

function assertLiveSurfaceResults(payload, label) {
  assert.deepEqual(payload.surfaces_checked, requiredLiveSurfaces, `${label} surfaces_checked`);
  for (const query of payload.queries ?? []) {
    const apiLive = surfaceResult(query, "API_LIVE");
    assert.equal(apiLive?.status, "pass", `${label} ${query.id} API_LIVE status`);
    assert.equal(apiLive?.transport, "fastapi.uvicorn.http.query", `${label} ${query.id} API_LIVE transport`);
    assert.ok(Number(apiLive?.row_count ?? 0) > 0, `${label} ${query.id} API_LIVE row_count`);
    assert.ok(Number(apiLive?.graph_node_count ?? 0) > 0, `${label} ${query.id} API_LIVE graph_node_count`);

    const web = surfaceResult(query, "Web");
    assert.equal(web?.status, "pass", `${label} ${query.id} Web status`);
    assert.equal(web?.transport, "next-bff.query", `${label} ${query.id} Web transport`);
    assert.ok(Number(web?.row_count ?? 0) > 0, `${label} ${query.id} Web row_count`);
    assert.ok(Number(web?.graph_node_count ?? 0) > 0, `${label} ${query.id} Web graph_node_count`);

    const mcpProtocol = surfaceResult(query, "MCP_PROTOCOL");
    assert.equal(mcpProtocol?.status, "pass", `${label} ${query.id} MCP_PROTOCOL status`);
    assert.equal(mcpProtocol?.transport, "mcp.stdio.protocol.search_evidence", `${label} ${query.id} MCP_PROTOCOL transport`);
    assert.equal(mcpProtocol?.server_registered, true, `${label} ${query.id} MCP_PROTOCOL registration`);
    assert.ok(Number(mcpProtocol?.row_count ?? 0) > 0, `${label} ${query.id} MCP_PROTOCOL row_count`);
    assert.ok(Number(mcpProtocol?.graph_node_count ?? 0) > 0, `${label} ${query.id} MCP_PROTOCOL graph_node_count`);
  }
}

const args = parseArgs(process.argv.slice(2));

const browserGate = readJson(args.browserJson);
assert.ok(
  ["asip.web.browser_gate_preflight", "asip.web.browser_e2e"].includes(browserGate.source),
  `unexpected browser artifact source ${browserGate.source}`
);
const browserArtifactIsE2e = browserGate.source === "asip.web.browser_e2e";
if (browserArtifactIsE2e) {
  assert.equal(browserGate.gate_status, "pass");
  assert.equal(browserGate.e2e_status, "pass");
  assert.equal(browserGate.summary?.failed, 0);
  assert.equal(browserGate.summary?.flaky, 0);
  assert.ok((browserGate.required_tests ?? []).length >= 4);
  assert.ok((browserGate.required_tests ?? []).every((test) => test.status === "pass"));
  assert.ok((browserGate.required_tests ?? []).every((test) => String(test.file ?? "").includes("workbench-smoke.spec.ts")));
  const currentDbProbeSurfaces = new Set((browserGate.current_db_probes ?? []).map((probe) => probe.surface));
  assert.ok(currentDbProbeSurfaces.has("graph_page_api_request"));
  assert.ok(currentDbProbeSurfaces.has("direct_api_document_request"));
  assert.ok(currentDbProbeSurfaces.has("graph_page_concept_detail_selection"));
  assert.ok((browserGate.current_db_probes ?? []).every((probe) => String(probe.url ?? "").includes("dbPath=")));
  assert.ok((browserGate.current_db_probes ?? []).every((probe) => Number(probe.status ?? 0) === 200));
  assert.ok((browserGate.current_db_probes ?? []).every((probe) => Number(probe.node_count ?? 0) > 0));
  assert.ok((browserGate.current_db_probes ?? []).every((probe) => Number(probe.edge_count ?? 0) > 0));
  const conceptDetailProbe = (browserGate.current_db_probes ?? []).find(
    (probe) => probe.surface === "graph_page_concept_detail_selection"
  );
  assert.ok(String(conceptDetailProbe?.selected_node_id ?? "").includes(":concept:"));
  assert.equal(conceptDetailProbe?.selected_kind, "function");
  assert.ok(Number(conceptDetailProbe?.implementation_count ?? 0) > 1);
  assert.equal(
    Number(conceptDetailProbe?.listed_implementation_count ?? 0),
    Number(conceptDetailProbe?.implementation_count ?? -1)
  );
  assert.ok(
    Number(conceptDetailProbe?.raw_implementation_record_count ?? conceptDetailProbe?.implementation_count ?? 0) >=
      Number(conceptDetailProbe?.implementation_count ?? 0)
  );
  assert.ok(String(conceptDetailProbe?.selected_implementation ?? "").trim());
  assert.equal(conceptDetailProbe?.selection_input, "canvas-node-click");
  assert.equal(conceptDetailProbe?.hovered_canvas_node_id, conceptDetailProbe?.selected_node_id);
  assert.ok(Number(conceptDetailProbe?.canvas_click_x ?? -1) >= 0);
  assert.ok(Number(conceptDetailProbe?.canvas_click_y ?? -1) >= 0);
  assert.equal(conceptDetailProbe?.detail_heading, "Concept Generated From");
  assert.equal(conceptDetailProbe?.detail_truncated, false);
  assert.ok((browserGate.command ?? []).join(" ").includes("pnpm exec playwright test"));
  assert.ok(String(browserGate.report_json ?? "").includes("playwright-report.json"));
} else if (browserGate.gate_status === "pass") {
  assert.equal(browserGate.existing_target_reachable || browserGate.probes?.listen_capability?.status === "pass", true);
} else {
  assert.equal(browserGate.gate_status, "blocked");
  assert.match(textFrom(browserGate.failure_reasons), /EPERM|TIMEOUT|EADDRINUSE|ECONNREFUSED/);
}

const inAppBrowserProbe = readJson(args.inAppBrowserJson);
assert.equal(inAppBrowserProbe.source, "asip.web.in_app_browser_probe");
assert.equal(inAppBrowserProbe.browser_surface, "codex-in-app-browser");
assert.ok((inAppBrowserProbe.target_urls ?? []).some((url) => String(url).includes("127.0.0.1:3100")));
if (inAppBrowserProbe.gate_status === "pass") {
  assert.ok((inAppBrowserProbe.attempts ?? []).some((attempt) => attempt.ok === true));
  assert.equal((inAppBrowserProbe.failure_reasons ?? []).length, 0);
} else {
  assert.equal(inAppBrowserProbe.gate_status, "blocked");
  assert.ok((inAppBrowserProbe.attempts ?? []).length >= 2);
  assert.ok((inAppBrowserProbe.target_urls ?? []).some((url) => String(url).includes("localhost:3100")));
  assert.match(textFrom(inAppBrowserProbe.failure_reasons), /ERR_BLOCKED_BY_CLIENT|ERR_CONNECTION_REFUSED/);
}

const providerGate = readJson(args.providerJson);
assert.equal(providerGate.source, "asip.provider_gate");
assertProviderChecks(providerGate, "provider gate");
if (providerGate.gate_status === "pass") {
  assert.equal(providerGate.summary?.passed, providerGate.summary?.total);
} else {
  assert.equal(providerGate.gate_status, "blocked");
  assert.match(textFrom(providerGate.failure_reasons), /embedding|semantic|provider|Operation not permitted|stale/i);
  assert.ok((providerGate.summary?.failed ?? 0) > 0 || (providerGate.summary?.partial ?? 0) > 0);
}

const runtimeSemanticFreshness = readJson(args.runtimeSemanticJson);
assert.equal(runtimeSemanticFreshness.source, "asip.runtime_semantic_freshness_qa");
assert.equal(runtimeSemanticFreshness.gate_status, "pass");
assert.equal(runtimeSemanticFreshness.summary?.failed, 0);
assert.ok(Number(runtimeSemanticFreshness.latest_index_job_id) > 0);
assert.ok(Number(runtimeSemanticFreshness.latest_graph_rebuild_job_id) > 0);
assert.ok(Number(runtimeSemanticFreshness.latest_semantic_edges_job_id) > 0);
assert.ok(Number(runtimeSemanticFreshness.latest_doc_nodes_job_id) > 0);
assert.ok((runtimeSemanticFreshness.checks ?? []).some((check) => check.id === "storage_runtime_extractor_job_kind_binding"));

const semanticQuality = readJson(args.semanticQualityJson);
assert.equal(semanticQuality.source, "asip.semantic_quality_eval");
assert.equal(semanticQuality.gate_status, "pass");
assert.equal(semanticQuality.summary?.passed, semanticQuality.summary?.total);
assert.equal(semanticQuality.summary?.failed, 0);
assert.ok(Number(semanticQuality.summary?.provider_vector_cases ?? 0) > 0);
assert.ok((semanticQuality.cases ?? []).length > 0);
assert.ok((semanticQuality.cases ?? []).every((item) => item.status === "pass"));
assert.ok((semanticQuality.cases ?? []).every((item) => Number(item.row_count ?? 0) > 0));

const callbackAudit = readJson(args.callbackAuditJson);
assert.equal(callbackAudit.source, "asip.callback_edge_audit");
assert.equal(callbackAudit.gate_status, "pass");
assert.ok(Number(callbackAudit.summary?.callback_edge_count ?? 0) > 0);
assert.equal(Number(callbackAudit.summary?.parser_pollution_candidate_count ?? -1), 0);
assert.equal(Number(callbackAudit.summary?.unexplained_ambiguous_callback_edge_count ?? -1), 0);
assert.ok(Number(callbackAudit.summary?.real_oracle_total ?? 0) >= 3);
assert.equal(
  Number(callbackAudit.summary?.real_oracle_passed ?? -1),
  Number(callbackAudit.summary?.real_oracle_total ?? -2)
);

const cliAcceptance = readJson(args.acceptanceJson);
assert.equal(cliAcceptance.source, "asip.acceptance");
assertLiveSurfaceResults(cliAcceptance, "live acceptance");
assert.equal(cliAcceptance.database_health?.status, "pass");
assert.ok(["pass", "blocked"].includes(cliAcceptance.gate_status));
assertProviderChecks(
  cliAcceptance.queries.find((query) => query.id === "AQ09"),
  "live AQ09 acceptance"
);

const webAcceptance = readJson(args.webAcceptanceJson);
assert.equal(webAcceptance.source, "asip.acceptance");
assertLiveSurfaceResults(webAcceptance, "web acceptance");
assert.ok(["pass", "blocked"].includes(webAcceptance.gate_status));
assertProviderChecks(
  webAcceptance.queries.find((query) => query.id === "AQ09"),
  "Web-included AQ09 acceptance"
);

const completionGate = readJson(args.completionJson);
assert.equal(completionGate.source, "asip.completion_gate");
assert.equal(completionGate.summary?.total, 20);
assert.equal(completionGate.summary?.missing ?? 0, 0);
assert.equal(completionGate.artifacts?.runtime_semantic_freshness?.status, "loaded");
assert.equal(completionGate.artifacts?.runtime_semantic_freshness?.source, "asip.runtime_semantic_freshness_qa");
assert.equal(completionGate.artifacts?.semantic_quality?.status, "loaded");
assert.equal(completionGate.artifacts?.semantic_quality?.source, "asip.semantic_quality_eval");
assert.equal(completionGate.artifacts?.callback_audit?.status, "loaded");
assert.equal(completionGate.artifacts?.callback_audit?.source, "asip.callback_edge_audit");
assert.equal(completionGate.artifacts?.hosted_openai_compatible?.status, "loaded");
assert.equal(completionGate.artifacts?.hosted_openai_compatible?.source, "asip.openai_compatible_live_smoke");
assert.equal(completionGate.artifacts?.in_app_browser?.status, "loaded");
assert.equal(completionGate.artifacts?.in_app_browser?.source, "asip.web.in_app_browser_probe");
assert.equal(completionGate.artifacts?.residual_acceptance?.status, "loaded");
assert.equal(completionGate.artifacts?.residual_acceptance?.source, "asip.residual_acceptance");
assert.equal(completionGate.artifacts?.git_gate?.status, "loaded");
assert.equal(completionGate.artifacts?.git_gate?.source, "asip.git_gate");
const completionRequirements = new Map(
  (completionGate.requirements ?? []).map((requirement) => [requirement.id, requirement])
);
for (const requirementId of [
  "real_index_db",
  "artifact_binding",
  "stage1_deterministic_graph",
  "product_graph_schema",
  "cli_api_mcp_surfaces",
  "api_live_surface",
  "mcp_protocol_surface",
  "web_surface",
  "acceptance_gate",
  "provider_live_gate",
  "stage2_semantic_edges",
  "runtime_semantic_freshness",
  "semantic_quality",
  "callback_edge_audit",
  "hosted_openai_compatible",
  "browser_e2e",
  "web_no_server_smoke",
  "performance_smoke",
  "residual_acceptance",
  "git_gate",
]) {
  assert.ok(completionRequirements.has(requirementId), `missing completion requirement ${requirementId}`);
}
const completionRelativePath = repoRelativePath(args.completionJson);
const completionIsCommittedQaArtifact =
  completionRelativePath.startsWith(`docs${path.sep}qa${path.sep}`) && completionRelativePath.endsWith(".json");
if (completionIsCommittedQaArtifact) {
  assert.notEqual(
    completionGate.gate_status,
    "pass",
    "repo-local docs/qa completion artifacts are self-referential and must not be used as final post-push pass proof"
  );
}
if (completionGate.gate_status === "pass") {
  assert.equal(completionGate.summary?.passed, completionGate.summary?.total);
} else {
  assert.equal(completionGate.gate_status, "blocked");
  assert.ok((completionGate.summary?.blocked ?? 0) > 0);
  assert.equal(completionRequirements.get("real_index_db")?.status, "pass");
  assert.equal(completionRequirements.get("artifact_binding")?.status, "pass");
  assert.equal(completionRequirements.get("stage1_deterministic_graph")?.status, "pass");
  assert.equal(completionRequirements.get("api_live_surface")?.status, "pass");
  assert.equal(completionRequirements.get("mcp_protocol_surface")?.status, "pass");
  assert.equal(completionRequirements.get("runtime_semantic_freshness")?.status, "pass");
  assert.equal(completionRequirements.get("semantic_quality")?.status, "pass");
  assert.equal(completionRequirements.get("callback_edge_audit")?.status, "pass");
  assert.equal(completionRequirements.get("hosted_openai_compatible")?.status, "blocked");
  const webNoServerRequirement = completionRequirements.get("web_no_server_smoke");
  if (webNoServerRequirement?.status === "pass") {
    assert.equal(webNoServerRequirement.status, "pass");
  } else {
    assert.equal(webNoServerRequirement?.status, "blocked");
    assert.match(
      textFrom(webNoServerRequirement?.failure_reasons),
      /no-server --.* does not match|no-server current_artifact_inputs missing|current artifact invariants smoke/,
    );
  }
  assert.equal(completionRequirements.get("performance_smoke")?.status, "pass");
  assert.equal(completionRequirements.get("browser_e2e")?.status, browserArtifactIsE2e ? "pass" : "blocked");
  assert.equal(completionRequirements.get("residual_acceptance")?.status, "blocked");
  const gitGateRequirement = completionRequirements.get("git_gate");
  if (gitGateRequirement?.status === "pass") {
    assert.equal(gitGateRequirement.status, "pass");
  } else {
    assert.equal(gitGateRequirement?.status, "blocked");
    assert.match(textFrom(gitGateRequirement?.failure_reasons), /worktree|upstream|committed|pushed|git/i);
  }
  if (!browserArtifactIsE2e) {
    assert.match(textFrom(completionRequirements.get("browser_e2e")?.failure_reasons), /ERR_BLOCKED_BY_CLIENT|ERR_CONNECTION_REFUSED/);
    assert.match(
      textFrom(completionRequirements.get("browser_e2e")?.failure_reasons),
      /in-app browser artifact source=asip\.web\.in_app_browser_probe is not no-mock browser e2e proof/
    );
  }
  assert.match(textFrom(completionGate.failure_reasons), /Web|provider|semantic|residual|git|Operation not permitted/i);
}

const webPackage = readJson(args.webPackageJson);
assert.equal(webPackage.scripts?.["test:ui:artifact"], "node scripts/browser-e2e-artifact.mjs");
assert.equal(existsSync(path.join(repoRoot, "apps/web/scripts/browser-e2e-artifact.mjs")), true);

console.log("current artifact invariants smoke passed");
