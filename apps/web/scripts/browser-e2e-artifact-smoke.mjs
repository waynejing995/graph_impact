import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";

const appRoot = path.resolve(import.meta.dirname, "..");
const tmpdir = mkdtempSync(path.join(os.tmpdir(), "asip-browser-e2e-artifact-"));

function writeReport(name, report) {
  const filePath = path.join(tmpdir, name);
  writeFileSync(filePath, `${JSON.stringify(report)}\n`, "utf8");
  return filePath;
}

function runArtifact(reportPath, outputName, extraArgs = []) {
  const outputPath = path.join(tmpdir, outputName);
  const result = spawnSync(
    process.execPath,
    [
      "scripts/browser-e2e-artifact.mjs",
      "--report-json",
      reportPath,
      ...extraArgs,
      "--output-json",
      outputPath,
      "--allow-blocked"
    ],
    {
      cwd: appRoot,
      encoding: "utf8",
      stdio: "pipe"
    }
  );
  if (result.error) {
    throw result.error;
  }
  assert.equal(result.status, 0, result.stderr || result.stdout);
  return JSON.parse(readFileSync(outputPath, "utf8"));
}

const allSkippedReport = writeReport("all-skipped.json", {
  stats: {
    expected: 0,
    unexpected: 0,
    flaky: 0,
    skipped: 3,
    duration: 12
  },
  suites: []
});
const allSkippedArtifact = runArtifact(allSkippedReport, "all-skipped-artifact.json");
assert.equal(allSkippedArtifact.source, "asip.web.browser_e2e");
assert.equal(allSkippedArtifact.gate_status, "blocked");
assert.equal(allSkippedArtifact.e2e_status, "blocked");
assert.equal(allSkippedArtifact.summary.total, 3);
assert.equal(allSkippedArtifact.summary.passed, 0);
assert.match(JSON.stringify(allSkippedArtifact.failure_reasons), /no passed tests/);

const currentDbProbes = [
  {
    surface: "graph_page_api_request",
    url: "http://127.0.0.1:3100/api/workbench/graph?dbPath=data%2Fasip.db&functionView=concept",
    db_path: "data/asip.db",
    status: 200,
    node_count: 2552,
    edge_count: 3000,
    response_sha256: "a".repeat(64),
    latest_index_job_id: "10",
    latest_graph_rebuild_job_id: "13"
  },
  {
    surface: "direct_api_graph_request",
    url: "http://127.0.0.1:3100/api/workbench/graph?dbPath=data%2Fasip.db",
    db_path: "data/asip.db",
    status: 200,
    node_count: 2552,
    edge_count: 3000,
    response_sha256: "b".repeat(64),
    latest_index_job_id: "10",
    latest_graph_rebuild_job_id: "13"
  },
  {
    surface: "graph_page_concept_detail_selection",
    url: "http://127.0.0.1:3100/graph?dbPath=data%2Fasip.db",
    db_path: "data/asip.db",
    status: 200,
    node_count: 2552,
    edge_count: 3000,
    response_sha256: "c".repeat(64),
    latest_index_job_id: "10",
    latest_graph_rebuild_job_id: "13",
    selected_node_id: "function:linux-amdgpu:concept:linux-amdgpu:amd-ip-versioned-functions:gfx_hw_init",
    selected_is_concept: true,
    selected_kind: "function",
    selected_label: "gfx_hw_init",
    implementation_count: 9,
    listed_implementation_count: 9,
    raw_implementation_record_count: 92,
    selected_implementation: "gfx_v10_0_hw_init",
    selection_input: "canvas-node-click",
    hovered_canvas_node_id: "function:linux-amdgpu:concept:linux-amdgpu:amd-ip-versioned-functions:gfx_hw_init",
    canvas_click_x: 704,
    canvas_click_y: 491,
    detail_heading: "Concept Generated From",
    detail_truncated: false
  }
];

const passingReport = writeReport("passing.json", {
  stats: {
    expected: 5,
    unexpected: 0,
    flaky: 0,
    skipped: 1,
    duration: 34
  },
  suites: [
    {
      title: "workbench-smoke.spec.ts",
      suites: [],
      specs: [
        {
          title: "acceptance page runs no-mock AQ01 through the real workbench API",
          file: "tests/workbench-smoke.spec.ts",
          tests: [{ outcome: "expected" }]
        },
        {
          title: "graph page uses URL dbPath for no-mock graph and query requests",
          file: "tests/workbench-smoke.spec.ts",
          tests: [{ outcome: "expected" }]
        },
        {
          title: "graph page loads current data/asip.db through browser and API",
          file: "tests/workbench-smoke.spec.ts",
          tests: [
            {
              outcome: "expected",
              results: [
                {
                  stdout: [
                    {
                      text: `ASIP_BROWSER_CURRENT_DB_PROBE ${JSON.stringify(currentDbProbes)}\n`
                    }
                  ],
                  attachments: [
                    {
                      name: "asip-current-db-probes",
                      contentType: "application/json",
                      body: JSON.stringify(currentDbProbes)
                    }
                  ]
                }
              ]
            }
          ]
        },
        {
          title: "graph page filters no-mock graph layers and shows edge provenance",
          file: "tests/workbench-smoke.spec.ts",
          tests: [{ outcome: "expected" }]
        },
        {
          title: "evidence page initial query uses URL dbPath without default DB fallback",
          file: "tests/workbench-smoke.spec.ts",
          tests: [{ outcome: "expected" }]
        },
        {
          title: "unrelated skipped test",
          tests: [{ outcome: "skipped" }]
        }
      ]
    }
  ]
});
const unboundArtifact = runArtifact(passingReport, "passing-unbound-artifact.json");
assert.equal(unboundArtifact.source, "asip.web.browser_e2e");
assert.equal(unboundArtifact.gate_status, "blocked");
assert.equal(unboundArtifact.e2e_status, "blocked");
assert.match(JSON.stringify(unboundArtifact.failure_reasons), /db_path is missing/);
assert.match(JSON.stringify(unboundArtifact.failure_reasons), /latest_index_job_id is missing or invalid/);
assert.match(JSON.stringify(unboundArtifact.failure_reasons), /offline Playwright JSON report cannot satisfy live browser e2e proof/);

const boundOfflineArtifact = runArtifact(passingReport, "passing-bound-offline-artifact.json", [
  "--db-path",
  "data/asip.db",
  "--latest-index-job-id",
  "10",
  "--latest-graph-rebuild-job-id",
  "13",
  "--target-url",
  "http://127.0.0.1:3100/graph?dbPath=data%2Fasip.db"
]);
assert.equal(boundOfflineArtifact.source, "asip.web.browser_e2e");
assert.equal(boundOfflineArtifact.gate_status, "blocked");
assert.equal(boundOfflineArtifact.e2e_status, "blocked");
assert.equal(boundOfflineArtifact.db_path, "data/asip.db");
assert.equal(boundOfflineArtifact.latest_index_job_id, "10");
assert.equal(boundOfflineArtifact.latest_graph_rebuild_job_id, "13");
assert.deepEqual(boundOfflineArtifact.target_urls, ["http://127.0.0.1:3100/graph?dbPath=data%2Fasip.db"]);
assert.equal(boundOfflineArtifact.report_json, passingReport);
assert.equal(
  boundOfflineArtifact.report_sha256,
  createHash("sha256").update(readFileSync(passingReport, "utf8")).digest("hex")
);
assert.equal(boundOfflineArtifact.summary.total, 6);
assert.equal(boundOfflineArtifact.summary.passed, 5);
assert.equal(boundOfflineArtifact.required_tests.length, 5);
assert.deepEqual(boundOfflineArtifact.current_db_probes, currentDbProbes);
for (const test of boundOfflineArtifact.required_tests) {
  assert.equal(test.file, "tests/workbench-smoke.spec.ts");
}
assert.match(JSON.stringify(boundOfflineArtifact.failure_reasons), /offline Playwright JSON report cannot satisfy live browser e2e proof/);
assert.doesNotMatch(JSON.stringify(boundOfflineArtifact.failure_reasons), /db_path is missing/);
assert.doesNotMatch(JSON.stringify(boundOfflineArtifact.failure_reasons), /target_urls do not include current dbPath/);
assert.doesNotMatch(JSON.stringify(boundOfflineArtifact.failure_reasons), /current_db_probes missing surface/);
assert.doesNotMatch(JSON.stringify(boundOfflineArtifact.failure_reasons), /functionView=concept/);

const wrongProbePathReport = writeReport("wrong-probe-path.json", {
  ...JSON.parse(readFileSync(passingReport, "utf8")),
  suites: [
    {
      title: "workbench-smoke.spec.ts",
      suites: [],
      specs: [
        {
          title: "acceptance page runs no-mock AQ01 through the real workbench API",
          file: "tests/workbench-smoke.spec.ts",
          tests: [{ outcome: "expected" }]
        },
        {
          title: "graph page uses URL dbPath for no-mock graph and query requests",
          file: "tests/workbench-smoke.spec.ts",
          tests: [{ outcome: "expected" }]
        },
        {
          title: "graph page loads current data/asip.db through browser and API",
          file: "tests/workbench-smoke.spec.ts",
          tests: [
            {
              outcome: "expected",
              results: [
                {
                  stdout: [
                    {
                      text: `ASIP_BROWSER_CURRENT_DB_PROBE ${JSON.stringify(
                        currentDbProbes.map((probe) =>
                          probe.surface === "direct_api_graph_request"
                            ? { ...probe, url: "http://127.0.0.1:3100/api/workbench/documents?dbPath=data%2Fasip.db" }
                            : probe
                        )
                      )}\n`
                    }
                  ]
                }
              ]
            }
          ]
        },
        {
          title: "graph page filters no-mock graph layers and shows edge provenance",
          file: "tests/workbench-smoke.spec.ts",
          tests: [{ outcome: "expected" }]
        },
        {
          title: "evidence page initial query uses URL dbPath without default DB fallback",
          file: "tests/workbench-smoke.spec.ts",
          tests: [{ outcome: "expected" }]
        }
      ]
    }
  ]
});
const wrongProbePathArtifact = runArtifact(wrongProbePathReport, "wrong-probe-path-artifact.json", [
  "--db-path",
  "data/asip.db",
  "--latest-index-job-id",
  "10",
  "--latest-graph-rebuild-job-id",
  "13",
  "--target-url",
  "http://127.0.0.1:3100/graph?dbPath=data%2Fasip.db"
]);
assert.equal(wrongProbePathArtifact.gate_status, "blocked");
assert.match(
  JSON.stringify(wrongProbePathArtifact.failure_reasons),
  /direct_api_graph_request url path=\/api\/workbench\/documents does not match \/api\/workbench\/graph/
);

const missingConceptViewReport = writeReport("missing-concept-view.json", {
  ...JSON.parse(readFileSync(passingReport, "utf8")),
  suites: [
    {
      title: "workbench-smoke.spec.ts",
      suites: [],
      specs: [
        {
          title: "acceptance page runs no-mock AQ01 through the real workbench API",
          file: "tests/workbench-smoke.spec.ts",
          tests: [{ outcome: "expected" }]
        },
        {
          title: "graph page uses URL dbPath for no-mock graph and query requests",
          file: "tests/workbench-smoke.spec.ts",
          tests: [{ outcome: "expected" }]
        },
        {
          title: "graph page loads current data/asip.db through browser and API",
          file: "tests/workbench-smoke.spec.ts",
          tests: [
            {
              outcome: "expected",
              results: [
                {
                  stdout: [
                    {
                      text: `ASIP_BROWSER_CURRENT_DB_PROBE ${JSON.stringify(
                        currentDbProbes.map((probe) =>
                          probe.surface === "graph_page_api_request"
                            ? { ...probe, url: "http://127.0.0.1:3100/api/workbench/graph?dbPath=data%2Fasip.db" }
                            : probe
                        )
                      )}\n`
                    }
                  ]
                }
              ]
            }
          ]
        },
        {
          title: "graph page filters no-mock graph layers and shows edge provenance",
          file: "tests/workbench-smoke.spec.ts",
          tests: [{ outcome: "expected" }]
        },
        {
          title: "evidence page initial query uses URL dbPath without default DB fallback",
          file: "tests/workbench-smoke.spec.ts",
          tests: [{ outcome: "expected" }]
        }
      ]
    }
  ]
});
const missingConceptViewArtifact = runArtifact(missingConceptViewReport, "missing-concept-view-artifact.json", [
  "--db-path",
  "data/asip.db",
  "--latest-index-job-id",
  "10",
  "--latest-graph-rebuild-job-id",
  "13",
  "--target-url",
  "http://127.0.0.1:3100/graph?dbPath=data%2Fasip.db"
]);
assert.equal(missingConceptViewArtifact.gate_status, "blocked");
assert.match(JSON.stringify(missingConceptViewArtifact.failure_reasons), /functionView=concept/);

const fakeConceptDetailReport = writeReport("fake-concept-detail.json", {
  ...JSON.parse(readFileSync(passingReport, "utf8")),
  suites: [
    {
      title: "workbench-smoke.spec.ts",
      suites: [],
      specs: [
        {
          title: "acceptance page runs no-mock AQ01 through the real workbench API",
          file: "tests/workbench-smoke.spec.ts",
          tests: [{ outcome: "expected" }]
        },
        {
          title: "graph page uses URL dbPath for no-mock graph and query requests",
          file: "tests/workbench-smoke.spec.ts",
          tests: [{ outcome: "expected" }]
        },
        {
          title: "graph page loads current data/asip.db through browser and API",
          file: "tests/workbench-smoke.spec.ts",
          tests: [
            {
              outcome: "expected",
              results: [
                {
                  stdout: [
                    {
                      text: `ASIP_BROWSER_CURRENT_DB_PROBE ${JSON.stringify(
                        currentDbProbes.map((probe) =>
                          probe.surface === "graph_page_concept_detail_selection"
                            ? { ...probe, selected_is_concept: false }
                            : probe
                        )
                      )}\n`
                    }
                  ]
                }
              ]
            }
          ]
        },
        {
          title: "graph page filters no-mock graph layers and shows edge provenance",
          file: "tests/workbench-smoke.spec.ts",
          tests: [{ outcome: "expected" }]
        },
        {
          title: "evidence page initial query uses URL dbPath without default DB fallback",
          file: "tests/workbench-smoke.spec.ts",
          tests: [{ outcome: "expected" }]
        }
      ]
    }
  ]
});
const fakeConceptDetailArtifact = runArtifact(fakeConceptDetailReport, "fake-concept-detail-artifact.json", [
  "--db-path",
  "data/asip.db",
  "--latest-index-job-id",
  "10",
  "--latest-graph-rebuild-job-id",
  "13",
  "--target-url",
  "http://127.0.0.1:3100/graph?dbPath=data%2Fasip.db"
]);
assert.equal(fakeConceptDetailArtifact.gate_status, "blocked");
assert.match(JSON.stringify(fakeConceptDetailArtifact.failure_reasons), /selected_is_concept=false/);

const wrongSuiteReport = writeReport("wrong-suite.json", {
  stats: {
    expected: 5,
    unexpected: 0,
    flaky: 0,
    skipped: 0,
    duration: 13
  },
  suites: [
    {
      title: "other-smoke.spec.ts",
      file: "tests/other-smoke.spec.ts",
      suites: [],
      specs: [
        "acceptance page runs no-mock AQ01 through the real workbench API",
        "graph page uses URL dbPath for no-mock graph and query requests",
        "graph page loads current data/asip.db through browser and API",
        "graph page filters no-mock graph layers and shows edge provenance",
        "evidence page initial query uses URL dbPath without default DB fallback"
      ].map((title) => ({
        title,
        file: "tests/other-smoke.spec.ts",
        tests: [{ outcome: "expected" }]
      }))
    }
  ]
});
const wrongSuiteArtifact = runArtifact(wrongSuiteReport, "wrong-suite-artifact.json", [
  "--db-path",
  "data/asip.db",
  "--latest-index-job-id",
  "10",
  "--latest-graph-rebuild-job-id",
  "13",
  "--target-url",
  "http://127.0.0.1:3100/graph?dbPath=data%2Fasip.db"
]);
assert.equal(wrongSuiteArtifact.gate_status, "blocked");
assert.ok(wrongSuiteArtifact.required_tests.every((test) => test.status === "wrong_source"));
assert.match(JSON.stringify(wrongSuiteArtifact.failure_reasons), /wrong_source/);

const subsetReport = writeReport("subset.json", {
  stats: {
    expected: 1,
    unexpected: 0,
    flaky: 0,
    skipped: 0,
    duration: 8
  },
  suites: [
    {
      title: "workbench-smoke.spec.ts",
      suites: [],
      specs: [
        {
          title: "graph page uses URL dbPath for no-mock graph and query requests",
          tests: [{ outcome: "expected" }]
        }
      ]
    }
  ]
});
const subsetArtifact = runArtifact(subsetReport, "subset-artifact.json");
assert.equal(subsetArtifact.source, "asip.web.browser_e2e");
assert.equal(subsetArtifact.gate_status, "blocked");
assert.equal(subsetArtifact.e2e_status, "blocked");
assert.match(JSON.stringify(subsetArtifact.failure_reasons), /required no-mock browser test did not pass/);

console.log("browser e2e artifact smoke passed");
