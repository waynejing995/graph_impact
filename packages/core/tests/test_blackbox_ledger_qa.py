import json
import io
import os
import re
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from asip import workbench
from asip.blackbox_coverage_qa import run_blackbox_coverage_qa
from asip.blackbox_ledger_qa import run_blackbox_ledger_qa
from asip.blackbox_provider_gate import run_blackbox_provider_gate
from asip.blackbox_residual_qa import run_blackbox_residual_delta, run_blackbox_residual_qa
from asip.cli import main as cli_main
from asip.storage import AsipStore
from asip.workbench import generate_blackbox_profiles_batch, save_provider_settings


class FakeBlackboxProvider:
    def generate(self, prompt, model):
        return {
            "profiles": [
                {
                    "id": "function:test:driver.c:program_l2",
                    "method": "blackbox_io",
                    "inputs": ["GCVM_L2_CNTL enable request"],
                    "outputs": ["writes GCVM_L2_CNTL"],
                    "observed_behavior": "program_l2 writes the L2 control register",
                    "explanation_layer": "explains cache setup behavior",
                    "confidence": 0.86,
                    "evidence": "program_l2 writes GCVM_L2_CNTL",
                }
            ],
            "relationships": [
                {
                    "src": "function:test:driver.c:program_l2",
                    "relation": "writes",
                    "dst": "register:GC:GCVM_L2_CNTL",
                    "confidence": 0.82,
                    "evidence": "write to GCVM_L2_CNTL",
                }
            ],
        }


class PromptEndpointBlackboxProvider:
    def generate(self, prompt, model):
        endpoints = re.findall(r"^ENDPOINT (.+)$", prompt, flags=re.MULTILINE)
        return {
            "profiles": [
                {
                    "id": endpoint,
                    "method": "blackbox_io",
                    "inputs": [],
                    "outputs": [],
                    "observed_behavior": f"{endpoint.rsplit(':', 1)[-1]} routes boundary effects",
                    "explanation_layer": "explains endpoint input-output behavior",
                    "confidence": 0.83,
                    "evidence": "neighbor:1 source:1",
                }
                for endpoint in endpoints
            ],
            "relationships": [],
        }


class RecordingPromptBlackboxProvider(PromptEndpointBlackboxProvider):
    def __init__(self):
        self.prompts = []

    def generate(self, prompt, model):
        self.prompts.append(prompt)
        return super().generate(prompt, model)


class InconsistentEvidenceBlackboxProvider:
    def generate(self, prompt, model):
        endpoints = re.findall(r"^ENDPOINT (.+)$", prompt, flags=re.MULTILINE)
        sample_match = re.search(r"^SAMPLE_INDEX: (\d+)$", prompt, flags=re.MULTILINE)
        sample_index = int(sample_match.group(1)) if sample_match else 1
        ref_by_sample = {1: "neighbor:1", 2: "source:1", 3: "snippet:1"}
        ref = ref_by_sample.get(sample_index, "source:1")
        return {
            "profiles": [
                {
                    "id": endpoint,
                    "method": "blackbox_io",
                    "inputs": [{"text": "configuration request", "refs": ["candidate:invocation"]}],
                    "outputs": [{"text": "writes boundary output", "refs": [ref]}],
                    "observed_behavior": {"text": "writes boundary output", "refs": [ref]},
                    "explanation_layer": "explains endpoint boundary behavior",
                    "confidence": 0.76,
                    "evidence": {"text": f"{ref} supports output", "refs": [ref]},
                }
                for endpoint in endpoints
            ],
            "relationships": [],
        }


class RetryOnceBlackboxProvider:
    def __init__(self):
        self.prompts = []

    def generate(self, prompt, model):
        self.prompts.append(prompt)
        if "COMPACT_JSON_RETRY: 1" not in prompt:
            raise RuntimeError("Ollama returned no parseable JSON content: {\"profiles\":[")
        endpoints = re.findall(r"^ENDPOINT (.+)$", prompt, flags=re.MULTILINE)
        return {
            "profiles": [
                {
                    "id": endpoint,
                    "method": "blackbox_io",
                    "inputs": [{"text": "configuration request", "refs": ["candidate:invocation"]}],
                    "outputs": [{"text": "writes boundary register", "refs": ["neighbor:1"]}],
                    "observed_behavior": {"text": "writes boundary register", "refs": ["neighbor:1"]},
                    "explanation_layer": "explains endpoint boundary behavior",
                    "confidence": 0.82,
                    "evidence": {"text": "neighbor:1 supports output", "refs": ["neighbor:1"]},
                }
                for endpoint in endpoints
            ]
        }


class WrongSchemaThenRetryBlackboxProvider:
    def __init__(self):
        self.prompts = []

    def generate(self, prompt, model):
        self.prompts.append(prompt)
        if "COMPACT_JSON_RETRY: 1" not in prompt:
            return {"function": "call", "arguments": {"query": "not a blackbox profile"}}
        endpoints = re.findall(r"^ENDPOINT (.+)$", prompt, flags=re.MULTILINE)
        return {
            "profiles": [
                {
                    "id": endpoint,
                    "method": "blackbox_io",
                    "inputs": [{"text": "configuration request", "refs": ["candidate:invocation"]}],
                    "outputs": [{"text": "writes boundary register", "refs": ["neighbor:1"]}],
                    "observed_behavior": {"text": "writes boundary register", "refs": ["neighbor:1"]},
                    "explanation_layer": "explains endpoint boundary behavior",
                    "confidence": 0.82,
                    "evidence": {"text": "neighbor:1 supports output", "refs": ["neighbor:1"]},
                }
                for endpoint in endpoints
            ]
        }


class AlwaysParseFailBlackboxProvider:
    def generate(self, prompt, model):
        raise RuntimeError("Ollama returned no parseable JSON content: {\"profiles\":[")


class BlackboxLedgerQaTests(unittest.TestCase):
    def test_blackbox_profiles_batch_dry_run_defaults_to_missing_inventory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            self._write_blackbox_db(db_path)
            store = AsipStore.connect(str(db_path))
            try:
                covered = store.usable_blackbox_profile_keys()
            finally:
                store.con.close()

            selection = generate_blackbox_profiles_batch(
                db_path,
                limit=100,
                edge_provider=PromptEndpointBlackboxProvider(),
                dry_run_selection=True,
            )

            selected_keys = {
                (str(candidate.get("view") or ""), str(candidate.get("endpoint_id") or ""))
                for candidate in selection["selection_manifest"]["candidates"]
            }
            self.assertTrue(covered)
            self.assertTrue(selected_keys)
            self.assertFalse(selected_keys & covered)
            self.assertEqual(selection["batch_size"], 1)
            self.assertEqual(selection["requested_batch_size"], 1)

    def test_blackbox_profiles_batch_splits_pending_and_terminal_retry_scopes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            self._write_blackbox_db(db_path)
            store = AsipStore.connect(str(db_path))
            try:
                covered = store.usable_blackbox_profile_keys()
                terminal = store.blackbox_manifest_candidate_keys()
            finally:
                store.con.close()

            pending = generate_blackbox_profiles_batch(
                db_path,
                limit=100,
                edge_provider=PromptEndpointBlackboxProvider(),
                dry_run_selection=True,
                candidate_scope="pending",
            )
            retry = generate_blackbox_profiles_batch(
                db_path,
                limit=100,
                edge_provider=PromptEndpointBlackboxProvider(),
                dry_run_selection=True,
                candidate_scope="retry-terminal",
            )

            pending_keys = {
                (str(candidate.get("view") or ""), str(candidate.get("endpoint_id") or ""))
                for candidate in pending["selection_manifest"]["candidates"]
            }
            retry_keys = {
                (str(candidate.get("view") or ""), str(candidate.get("endpoint_id") or ""))
                for candidate in retry["selection_manifest"]["candidates"]
            }
            self.assertTrue(terminal)
            self.assertEqual(pending["candidate_scope"], "pending")
            self.assertEqual(retry["candidate_scope"], "retry-terminal")
            self.assertFalse(pending_keys & covered)
            self.assertFalse(pending_keys & terminal)
            self.assertTrue(retry_keys)
            self.assertTrue(retry_keys <= (terminal - covered))

    def test_blackbox_profiles_batch_splits_terminal_retry_by_failure_reason(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            self._write_blackbox_db(db_path)
            generate_blackbox_profiles_batch(
                db_path,
                limit=1,
                sample_count=1,
                edge_provider=AlwaysParseFailBlackboxProvider(),
                candidate_scope="pending",
                include_graph=False,
            )

            parse_retry = generate_blackbox_profiles_batch(
                db_path,
                limit=100,
                edge_provider=PromptEndpointBlackboxProvider(),
                dry_run_selection=True,
                candidate_scope="retry-terminal-parse",
            )
            consensus_retry = generate_blackbox_profiles_batch(
                db_path,
                limit=100,
                edge_provider=PromptEndpointBlackboxProvider(),
                dry_run_selection=True,
                candidate_scope="retry-terminal-consensus",
            )

            parse_keys = {
                (str(candidate.get("view") or ""), str(candidate.get("endpoint_id") or ""))
                for candidate in parse_retry["selection_manifest"]["candidates"]
            }
            consensus_keys = {
                (str(candidate.get("view") or ""), str(candidate.get("endpoint_id") or ""))
                for candidate in consensus_retry["selection_manifest"]["candidates"]
            }
            self.assertEqual(parse_retry["candidate_scope"], "retry-terminal-parse")
            self.assertEqual(consensus_retry["candidate_scope"], "retry-terminal-consensus")
            self.assertTrue(parse_keys)
            self.assertTrue(consensus_keys)
            self.assertFalse(parse_keys & consensus_keys)
            residual = run_blackbox_residual_qa(db_path, residual_limit=1)
            self.assertGreater(residual["residuals"]["terminal_count"], residual["residuals"]["terminal_sample_count"])
            self.assertIn("failed_parse_exhausted", residual["residuals"]["failure_reason_counts"])
            self.assertIn("rejected_reconcile_insufficient_consensus", residual["residuals"]["failure_reason_counts"])

    def test_blackbox_profiles_batch_provider_preflight_fails_without_creating_job(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            self._write_base_graph_db(db_path)

            with patch(
                "asip.workbench._preflight_blackbox_provider_reachability",
                side_effect=RuntimeError("blackbox provider unreachable: operation not permitted"),
            ):
                with self.assertRaisesRegex(RuntimeError, "blackbox provider unreachable"):
                    generate_blackbox_profiles_batch(
                        db_path,
                        limit=1,
                        include_graph=False,
                    )

            store = AsipStore.connect(str(db_path))
            try:
                row = store.con.execute(
                    "select count(*) from jobs where kind = 'blackbox_profiles_batch'"
                ).fetchone()
            finally:
                store.con.close()
            self.assertEqual(int(row[0]), 0)

    def test_blackbox_provider_gate_writes_blocked_artifact_when_provider_unreachable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            output_json = root / "blackbox-provider.json"
            output_md = root / "blackbox-provider.md"
            self._write_base_graph_db(db_path)

            with patch(
                "asip.blackbox_provider_gate._preflight_blackbox_provider_reachability",
                side_effect=RuntimeError("blackbox provider unreachable: operation not permitted"),
            ):
                payload = run_blackbox_provider_gate(
                    db_path,
                    output_json=output_json,
                    output_md=output_md,
                )

            self.assertEqual(payload["source"], "asip.blackbox_provider_gate")
            self.assertEqual(payload["gate_status"], "blocked")
            self.assertEqual(payload["provider_check"]["status"], "fail")
            self.assertIn("operation not permitted", payload["provider_check"]["message"])
            self.assertEqual(payload["provider_check"]["failure_class"], "local_network_permission")
            self.assertIn("local provider socket", payload["provider_check"]["recovery_hint"])
            self.assertTrue(output_json.exists())
            self.assertIn("Failure class: local_network_permission", output_md.read_text(encoding="utf-8"))
            self.assertIn("Blackbox Provider Gate", output_md.read_text(encoding="utf-8"))

    def test_blackbox_provider_gate_cli_require_pass_exits_nonzero_when_blocked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            output_json = root / "blackbox-provider.json"
            self._write_base_graph_db(db_path)

            with patch(
                "asip.blackbox_provider_gate._preflight_blackbox_provider_reachability",
                side_effect=RuntimeError("blackbox provider unreachable: operation not permitted"),
            ):
                exit_code = cli_main([
                    "blackbox-provider-gate",
                    "--db",
                    str(db_path),
                    "--output-json",
                    str(output_json),
                    "--require-pass",
                ])

            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 2)
            self.assertEqual(payload["gate_status"], "blocked")
            self.assertEqual(payload["provider_check"]["status"], "fail")

    def test_blackbox_full_generation_provider_failure_writes_current_qa_artifacts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            out_dir = root / "full-generation"
            self._write_blackbox_db(db_path)
            repo_root = Path(__file__).resolve().parents[3]
            env = os.environ.copy()
            env.update(
                {
                    "ASIP_BLACKBOX_DB_PATH": str(db_path),
                    "ASIP_BLACKBOX_OUT_DIR": str(out_dir),
                    "ASIP_BLACKBOX_REQUIRE_CLEAN_WORKTREE": "0",
                    "ASIP_BLACKBOX_SKIP_SMOKE": "1",
                    "ASIP_BLACKBOX_MAX_ROUNDS": "1",
                    "PYTHONDONTWRITEBYTECODE": "1",
                }
            )

            completed = subprocess.run(
                ["bash", "scripts/blackbox_full_generation.sh"],
                cwd=repo_root,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
            )

            self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
            expected_sources = {
                "blackbox-ledger-latest.json": "asip.blackbox_ledger_qa",
                "blackbox-coverage-latest.json": "asip.blackbox_coverage_qa",
                "blackbox-residual-latest.json": "asip.blackbox_residual_qa",
            }
            for filename, source in expected_sources.items():
                artifact = out_dir / filename
                self.assertTrue(artifact.exists(), completed.stdout + completed.stderr)
                payload = json.loads(artifact.read_text(encoding="utf-8"))
                self.assertEqual(payload["source"], source)
            run_artifact = out_dir / "blackbox-full-generation-run.json"
            self.assertTrue(run_artifact.exists(), completed.stdout + completed.stderr)
            run_payload = json.loads(run_artifact.read_text(encoding="utf-8"))
            self.assertEqual(run_payload["source"], "asip.blackbox_full_generation_run")
            self.assertEqual(run_payload["gate_status"], "blocked")
            self.assertEqual(run_payload["failure_stage"], "provider_gate")
            self.assertEqual(run_payload["db_path"], str(db_path))
            self.assertEqual(
                run_payload["artifacts"]["blackbox_coverage_qa"]["path"],
                str(out_dir / "blackbox-coverage-latest.json"),
            )

    def test_blackbox_full_generation_provider_failure_writes_artifacts_before_clean_check(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            out_dir = root / "full-generation"
            self._write_blackbox_db(db_path)
            repo_root = Path(__file__).resolve().parents[3]
            dirty_marker = repo_root / f"blackbox-dirty-marker-{os.getpid()}.tmp"
            dirty_marker.write_text("dirty marker for blackbox runner test\n", encoding="utf-8")
            env = os.environ.copy()
            env.update(
                {
                    "ASIP_BLACKBOX_DB_PATH": str(db_path),
                    "ASIP_BLACKBOX_OUT_DIR": str(out_dir),
                    "ASIP_BLACKBOX_SKIP_SMOKE": "1",
                    "ASIP_BLACKBOX_MAX_ROUNDS": "1",
                    "PYTHONDONTWRITEBYTECODE": "1",
                }
            )
            try:
                completed = subprocess.run(
                    ["bash", "scripts/blackbox_full_generation.sh"],
                    cwd=repo_root,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=30,
                )
            finally:
                dirty_marker.unlink(missing_ok=True)

            self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
            run_artifact = out_dir / "blackbox-full-generation-run.json"
            self.assertTrue(run_artifact.exists(), completed.stdout + completed.stderr)
            run_payload = json.loads(run_artifact.read_text(encoding="utf-8"))
            self.assertEqual(run_payload["source"], "asip.blackbox_full_generation_run")
            self.assertEqual(run_payload["gate_status"], "blocked")
            self.assertEqual(run_payload["failure_stage"], "provider_gate")
            self.assertEqual(
                run_payload["artifacts"]["blackbox_provider_gate"]["path"],
                str(out_dir / "blackbox-provider-gate.json"),
            )
            provider_payload = json.loads((out_dir / "blackbox-provider-gate.json").read_text(encoding="utf-8"))
            self.assertEqual(provider_payload["source"], "asip.blackbox_provider_gate")
            self.assertEqual(provider_payload["gate_status"], "blocked")

    def test_blackbox_profiles_batch_can_omit_post_batch_graph_for_scale_runs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            self._write_base_graph_db(db_path)

            result = generate_blackbox_profiles_batch(
                db_path,
                limit=1,
                edge_provider=PromptEndpointBlackboxProvider(),
                include_graph=False,
            )

            self.assertEqual(result["profile_count"], 1)
            self.assertNotIn("graph", result)

    def test_blackbox_profiles_batch_cli_summary_only_writes_full_artifact(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            self._write_base_graph_db(db_path)
            output_json = root / "blackbox-selection.json"
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                exit_code = cli_main([
                    "blackbox-profiles-batch",
                    "--db",
                    str(db_path),
                    "--limit",
                    "2",
                    "--dry-run-selection",
                    "--summary-only",
                    "--output-json",
                    str(output_json),
                ])

            printed = json.loads(stdout.getvalue())
            artifact = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertIn("candidate_count", printed)
            self.assertNotIn("candidates", json.dumps(printed))
            self.assertTrue(artifact["selection_manifest"]["candidates"])

    def test_blackbox_profiles_batch_retries_parse_failures_with_compact_prompt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            self._write_base_graph_db(db_path)
            provider = RetryOnceBlackboxProvider()

            result = generate_blackbox_profiles_batch(
                db_path,
                limit=1,
                sample_count=1,
                edge_provider=provider,
                include_graph=False,
            )
            ledger = result["ledger"][0]

            self.assertEqual(result["profile_count"], 1)
            self.assertEqual(len(provider.prompts), 2)
            self.assertIn("COMPACT_JSON_RETRY: 1", provider.prompts[1])
            self.assertEqual(ledger["attempts"][0]["status"], "accepted")
            self.assertEqual(ledger["attempts"][0]["metadata"]["provider_response_ids"], [1, 2])

    def test_blackbox_profiles_batch_retries_wrong_schema_with_compact_prompt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            self._write_base_graph_db(db_path)
            provider = WrongSchemaThenRetryBlackboxProvider()

            result = generate_blackbox_profiles_batch(
                db_path,
                limit=1,
                sample_count=1,
                edge_provider=provider,
                include_graph=False,
            )
            ledger = result["ledger"][0]

            self.assertEqual(result["profile_count"], 1)
            self.assertEqual(len(provider.prompts), 2)
            self.assertIn("COMPACT_JSON_RETRY: 1", provider.prompts[1])
            self.assertEqual(ledger["attempts"][0]["status"], "accepted")
            self.assertEqual(ledger["attempts"][0]["metadata"]["provider_response_ids"], [1, 2])
            self.assertEqual(
                ledger["attempts"][0]["metadata"]["sample_failures"][0]["error_class"],
                "BlackboxProfileSchemaError",
            )

    def test_blackbox_reconcile_abstains_samples_without_independent_ref_agreement(self):
        candidate = {
            "candidate_id": "concept:function:test:program_l2",
            "endpoint_id": "function:test:driver.c:program_l2",
            "view": "concept",
            "kind": "function",
            "label": "program_l2",
            "neighbors": [
                {"direction": "out", "relation": "writes", "kind": "register", "endpoint_id": "register:GC:GCVM_L2_CNTL"},
                {"direction": "out", "relation": "writes", "kind": "register", "endpoint_id": "register:GC:GCVM_L3_CNTL"},
            ],
            "raw_ast_sources": [{"path": "driver.c", "raw_function_name": "program_l2"}],
        }
        samples = [
            {
                "profiles": [
                    {
                        "id": "function:test:driver.c:program_l2",
                        "method": "blackbox_io",
                        "inputs": [{"text": "configuration request", "refs": ["candidate:invocation"]}],
                        "outputs": [{"text": "writes L2 control register", "refs": ["neighbor:1"]}],
                        "observed_behavior": {"text": "writes control register", "refs": ["neighbor:1"]},
                        "explanation_layer": "explains register programming",
                        "evidence": {"text": "neighbor:1 supports the output", "refs": ["neighbor:1"]},
                    }
                ],
                "relationships": [],
            },
            {
                "profiles": [
                    {
                        "id": "function:test:driver.c:program_l2",
                        "method": "blackbox_io",
                        "inputs": [{"text": "configuration request", "refs": ["candidate:invocation"]}],
                        "outputs": [{"text": "writes source described control register", "refs": ["source:1"]}],
                        "observed_behavior": {"text": "writes control register", "refs": ["source:1"]},
                        "explanation_layer": "explains register programming",
                        "evidence": {"text": "source:1 supports the output", "refs": ["source:1"]},
                    }
                ],
                "relationships": [],
            },
            {
                "profiles": [
                    {
                        "id": "function:test:driver.c:program_l2",
                        "method": "blackbox_io",
                        "inputs": [{"text": "configuration request", "refs": ["candidate:invocation"]}],
                        "outputs": [{"text": "writes L3 control register", "refs": ["neighbor:2"]}],
                        "observed_behavior": {"text": "writes control register", "refs": ["neighbor:2"]},
                        "explanation_layer": "explains register programming",
                        "evidence": {"text": "neighbor:2 supports the output", "refs": ["neighbor:2"]},
                    }
                ],
                "relationships": [],
            },
        ]

        result = workbench._reconcile_blackbox_profile_samples(samples, candidate, sample_count=3)

        self.assertEqual(result["status"], "abstained")
        self.assertIn("insufficient_independent_ref_agreement", result["metadata"]["rejected_reason_counts"])

    def test_blackbox_profile_prompts_specialize_each_evidence_view(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            self._write_base_graph_db(db_path)
            provider = RecordingPromptBlackboxProvider()

            generate_blackbox_profiles_batch(
                db_path,
                limit=1,
                sample_count=3,
                edge_provider=provider,
            )

            self.assertEqual(len(provider.prompts), 3)
            self.assertIn("PRIMARY_EVIDENCE_VIEW: neighbor-heavy", provider.prompts[0])
            self.assertIn("Prioritize GRAPH NEIGHBORS", provider.prompts[0])
            self.assertIn("PRIMARY_EVIDENCE_VIEW: source-span-heavy", provider.prompts[1])
            self.assertIn("Prioritize AST SOURCES", provider.prompts[1])
            self.assertIn("PRIMARY_EVIDENCE_VIEW: snippet-minimal-allowlist", provider.prompts[2])
            self.assertIn("Prioritize EVIDENCE_REFS and ALLOWLIST", provider.prompts[2])

    def test_blackbox_profile_prompt_is_profile_first_without_relationship_generation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            self._write_base_graph_db(db_path)
            provider = RecordingPromptBlackboxProvider()

            generate_blackbox_profiles_batch(
                db_path,
                limit=1,
                sample_count=1,
                edge_provider=provider,
            )

            prompt = provider.prompts[0]
            self.assertIn("Return JSON only with profiles.", prompt)
            self.assertIn("\"inputs\":[{\"text\":string,\"refs\":[string]}]", prompt)
            self.assertNotIn("\"relationships\"", prompt)
            self.assertNotIn("at most one relationship", prompt)

    def test_blackbox_profiles_batch_records_abstain_terminal_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            self._write_base_graph_db(db_path)

            result = generate_blackbox_profiles_batch(
                db_path,
                limit=1,
                sample_count=3,
                edge_provider=InconsistentEvidenceBlackboxProvider(),
            )
            coverage = run_blackbox_coverage_qa(db_path)

            self.assertEqual(result["profile_count"], 0)
            self.assertEqual(result["abstained_count"], 1)
            self.assertEqual(result["ledger"][0]["attempts"][0]["status"], "abstained")
            self.assertEqual(coverage["terminal_status_counts"]["abstained"], 1)

    def test_blackbox_ledger_qa_binds_inventory_ledger_provenance_and_runtime_visibility(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            self._write_blackbox_db(db_path)
            output_json = root / "blackbox-ledger.json"
            output_md = root / "blackbox-ledger.md"

            payload = run_blackbox_ledger_qa(db_path, output_json=output_json, output_md=output_md)

            self.assertEqual(payload["source"], "asip.blackbox_ledger_qa")
            self.assertEqual(payload["gate_status"], "pass")
            self.assertGreaterEqual(payload["inventory"]["total"], 2)
            self.assertEqual(payload["ledger"]["batch_count"], 1)
            self.assertEqual(payload["ledger"]["attempt_status_counts"]["accepted"], 1)
            self.assertEqual(payload["entity_ledger"]["provider_response_count"], 3)
            self.assertIn("repaired_legacy_evidence_refs", payload["ledger"]["reason_code_counts"])
            self.assertEqual(len(payload["ledger"]["manifest_sha256_values"][0]), 64)
            self.assertEqual(payload["latest_manifest_group"]["observed_shard_count"], 1)
            self.assertEqual(payload["latest_manifest_group"]["expected_shard_count"], 1)
            self.assertTrue(payload["latest_manifest_group"]["complete"])
            self.assertEqual(payload["profiles"]["storage_mode"], "canonical_table_with_self_edge_projection")
            self.assertEqual(payload["profiles"]["profile_table_count"], 1)
            self.assertEqual(payload["profiles"]["content_grounded_count"], 1)
            self.assertEqual(payload["profiles"]["profile_edge_count"], 1)
            self.assertGreaterEqual(payload["profiles"]["relationship_edge_count"], 1)
            self.assertEqual(payload["profiles"]["provenance_failure_count"], 0)
            self.assertEqual(payload["profiles"]["runtime_visible_count"], payload["profiles"]["stored_edge_count"])
            self.assertTrue(output_json.exists())
            self.assertIn("Blackbox Ledger QA", output_md.read_text(encoding="utf-8"))

    def test_blackbox_ledger_qa_cli_writes_artifact(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            self._write_blackbox_db(db_path)
            output_json = root / "cli-blackbox-ledger.json"

            exit_code = cli_main([
                "blackbox-ledger-qa",
                "--db",
                str(db_path),
                "--output-json",
                str(output_json),
            ])

            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["gate_status"], "pass")
            self.assertEqual(payload["source"], "asip.blackbox_ledger_qa")

    def test_blackbox_ledger_qa_aggregates_manifest_group_across_shards(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            self._write_sharded_blackbox_db(db_path)

            payload = run_blackbox_ledger_qa(db_path)

            self.assertEqual(payload["gate_status"], "pass")
            latest_group = payload["latest_manifest_group"]
            self.assertEqual(latest_group["observed_shard_count"], 2)
            self.assertEqual(latest_group["expected_shard_count"], 2)
            self.assertTrue(latest_group["complete"])
            self.assertEqual(len(latest_group["job_ids"]), 2)
            self.assertEqual(latest_group["attempted_count"], 2)
            self.assertEqual(latest_group["terminal_attempt_count"], 2)
            self.assertGreaterEqual(latest_group["profile_table_count"], 2)
            self.assertGreaterEqual(len(latest_group["manifest_sha256_values"]), 2)

    def test_blackbox_coverage_qa_reports_missing_inventory_profiles(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            self._write_blackbox_db(db_path)
            output_json = root / "blackbox-coverage.json"
            output_md = root / "blackbox-coverage.md"

            payload = run_blackbox_coverage_qa(
                db_path,
                output_json=output_json,
                output_md=output_md,
                min_coverage=1.0,
            )

            self.assertEqual(payload["source"], "asip.blackbox_coverage_qa")
            self.assertEqual(payload["gate_status"], "blocked")
            self.assertTrue(payload["generated_at"])
            self.assertEqual(payload["db_sha256"], workbench._sha256_file(db_path))
            self.assertTrue(payload["limits_config_sha256"])
            self.assertIn("repo_head", payload)
            self.assertGreaterEqual(payload["coverage"]["inventory_total"], 2)
            self.assertGreaterEqual(payload["coverage"]["covered_count"], 1)
            self.assertGreater(payload["coverage"]["missing_count"], 0)
            self.assertIn("concept", payload["by_view"])
            self.assertTrue(payload["missing_samples"])
            self.assertTrue(output_json.exists())
            self.assertIn("Blackbox Coverage QA", output_md.read_text(encoding="utf-8"))

    def test_blackbox_residual_qa_lists_terminal_without_passing_gate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            self._write_blackbox_db(db_path)

            payload = run_blackbox_residual_qa(db_path, residual_limit=10)

            self.assertEqual(payload["source"], "asip.blackbox_residual_qa")
            self.assertEqual(payload["gate_status"], "blocked")
            self.assertGreater(payload["coverage"]["missing_count"], 0)
            self.assertGreater(payload["residuals"]["terminal_count"], 0)
            self.assertEqual(payload["residuals"]["terminal_sample_count"], payload["residuals"]["terminal_count"])
            self.assertTrue(payload["residuals"]["terminal_samples"])
            self.assertGreater(payload["residuals"]["failure_reason_counts"]["rejected_reconcile_insufficient_consensus"], 0)
            self.assertGreater(payload["residuals"]["failure_gate_counts"]["sample_reconcile"], 0)
            self.assertTrue(payload["summary"]["top_failure_reasons"])
            self.assertEqual(payload["summary"]["status"], "blocked")
            md = root / "blackbox-residual.md"
            payload_with_md = run_blackbox_residual_qa(db_path, output_md=md, residual_limit=10)
            self.assertEqual(payload_with_md["summary"]["status"], "blocked")
            self.assertIn("Terminal Breakdown", md.read_text(encoding="utf-8"))

    def test_blackbox_residual_qa_cli_writes_artifact(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            output_json = root / "blackbox-residual.json"
            self._write_blackbox_db(db_path)

            exit_code = cli_main([
                "blackbox-residual-qa",
                "--db",
                str(db_path),
                "--output-json",
                str(output_json),
                "--residual-limit",
                "5",
            ])

            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["source"], "asip.blackbox_residual_qa")
            self.assertEqual(payload["gate_status"], "blocked")
            self.assertLessEqual(payload["residuals"]["terminal_sample_count"], 5)

    def test_blackbox_residual_delta_reports_terminal_reason_changes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            before_json = root / "before.json"
            after_json = root / "after.json"
            output_json = root / "delta.json"
            output_md = root / "delta.md"
            before_json.write_text(json.dumps({
                "summary": {"covered": 7, "missing": 10, "pending": 7, "terminal": 3},
                "residuals": {
                    "failure_reason_counts": {
                        "failed_parse_exhausted": 2,
                        "rejected_reconcile_insufficient_consensus": 1,
                    }
                },
            }), encoding="utf-8")
            after_json.write_text(json.dumps({
                "summary": {"covered": 8, "missing": 8, "pending": 7, "terminal": 1},
                "residuals": {
                    "failure_reason_counts": {
                        "failed_parse_exhausted": 1,
                        "rejected_reconcile_insufficient_consensus": 0,
                    }
                },
            }), encoding="utf-8")

            payload = run_blackbox_residual_delta(
                before_json,
                after_json,
                output_json=output_json,
                output_md=output_md,
                round_number=1,
                scope="retry-terminal-consensus",
            )

            self.assertEqual(payload["source"], "asip.blackbox_residual_delta")
            self.assertEqual(payload["status"], "improved")
            self.assertEqual(payload["delta"]["terminal"], -2)
            self.assertEqual(payload["delta"]["failure_reasons"]["failed_parse_exhausted"], -1)
            self.assertEqual(payload["delta"]["failure_reasons"]["rejected_reconcile_insufficient_consensus"], -1)
            self.assertTrue(output_json.exists())
            self.assertIn("Blackbox Terminal Warmup Delta", output_md.read_text(encoding="utf-8"))

    def test_blackbox_residual_delta_cli_writes_artifact(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            before_json = root / "before.json"
            after_json = root / "after.json"
            output_json = root / "delta.json"
            before_json.write_text(json.dumps({
                "summary": {"covered": 1, "missing": 2, "pending": 1, "terminal": 1},
                "residuals": {"failure_reason_counts": {"failed_parse_exhausted": 1}},
            }), encoding="utf-8")
            after_json.write_text(json.dumps({
                "summary": {"covered": 1, "missing": 2, "pending": 1, "terminal": 1},
                "residuals": {"failure_reason_counts": {"failed_parse_exhausted": 1}},
            }), encoding="utf-8")

            exit_code = cli_main([
                "blackbox-residual-delta",
                "--before-json",
                str(before_json),
                "--after-json",
                str(after_json),
                "--round",
                "2",
                "--scope",
                "retry-terminal-parse",
                "--output-json",
                str(output_json),
            ])

            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["status"], "no_change")
            self.assertEqual(payload["round"], 2)
            self.assertEqual(payload["scope"], "retry-terminal-parse")

    def test_blackbox_coverage_qa_reports_latest_manifest_scope_separately_from_full_goal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            self._write_sharded_blackbox_db(db_path)

            payload = run_blackbox_coverage_qa(db_path, min_coverage=1.0)

            self.assertEqual(payload["gate_status"], "blocked")
            latest_scope = payload["latest_manifest_scope"]
            self.assertEqual(latest_scope["scope_type"], "latest_manifest_group")
            self.assertTrue(latest_scope["explicit_not_full_goal"])
            self.assertEqual(latest_scope["expected_shard_count"], 2)
            self.assertEqual(latest_scope["observed_shard_count"], 2)
            self.assertEqual(latest_scope["selected_candidate_count"], 2)
            self.assertEqual(latest_scope["terminal_candidate_count"], 2)
            self.assertEqual(latest_scope["selected_covered_count"], 2)
            self.assertEqual(latest_scope["selected_missing_count"], 0)
            self.assertEqual(latest_scope["selected_coverage_ratio"], 1.0)

    def test_blackbox_coverage_qa_cli_writes_artifact(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            self._write_blackbox_db(db_path)
            output_json = root / "cli-blackbox-coverage.json"

            exit_code = cli_main([
                "blackbox-coverage-qa",
                "--db",
                str(db_path),
                "--output-json",
                str(output_json),
                "--min-coverage",
                "1.0",
            ])

            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["source"], "asip.blackbox_coverage_qa")
            self.assertEqual(payload["gate_status"], "blocked")

    def test_blackbox_coverage_qa_cli_require_pass_exits_nonzero_when_blocked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            self._write_blackbox_db(db_path)
            output_json = root / "cli-blackbox-coverage.json"

            exit_code = cli_main([
                "blackbox-coverage-qa",
                "--db",
                str(db_path),
                "--output-json",
                str(output_json),
                "--min-coverage",
                "1.0",
                "--require-pass",
            ])

            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 2)
            self.assertEqual(payload["source"], "asip.blackbox_coverage_qa")
            self.assertEqual(payload["gate_status"], "blocked")

    def test_blackbox_residual_qa_cli_require_pass_exits_nonzero_when_blocked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            self._write_blackbox_db(db_path)
            output_json = root / "cli-blackbox-residual.json"

            exit_code = cli_main([
                "blackbox-residual-qa",
                "--db",
                str(db_path),
                "--output-json",
                str(output_json),
                "--require-pass",
            ])

            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 2)
            self.assertEqual(payload["source"], "asip.blackbox_residual_qa")
            self.assertEqual(payload["gate_status"], "blocked")

    def _write_blackbox_db(self, db_path: Path) -> None:
        self._write_base_graph_db(db_path)
        generate_blackbox_profiles_batch(
            db_path,
            limit=2,
            batch_size=2,
            edge_provider=FakeBlackboxProvider(),
        )

    def _write_sharded_blackbox_db(self, db_path: Path) -> None:
        self._write_base_graph_db(db_path)
        for shard_index in (0, 1):
            generate_blackbox_profiles_batch(
                db_path,
                limit=1,
                batch_size=1,
                edge_provider=PromptEndpointBlackboxProvider(),
                phase="fixture-scale",
                selection_seed="fixture-sharded-blackbox",
                shard_count=2,
                shard_index=shard_index,
            )

    def _write_base_graph_db(self, db_path: Path) -> None:
        store = AsipStore.connect(str(db_path))
        store.migrate()
        store.save_provider_settings({"edge": {"provider": "ollama", "model": "gemma4:e4b"}})
        store.add_edge(
            "program_l2",
            "GCVM_L2_CNTL",
            "writes",
            0.97,
            stage="deterministic",
            source="clang_ast",
            path="driver.c",
            provenance={
                "extractor": "code_graph",
                "corpus_id": "test",
                "repo": "local",
                "function": "program_l2",
                "function_name": "program_l2",
                "ip": "GC",
            },
        )
        store.add_edge(
            "program_l3",
            "GCVM_L3_CNTL",
            "writes",
            0.94,
            stage="deterministic",
            source="clang_ast",
            path="driver.c",
            provenance={
                "extractor": "code_graph",
                "corpus_id": "test",
                "repo": "local",
                "function": "program_l3",
                "function_name": "program_l3",
                "ip": "GC",
            },
        )
        store.con.close()
        save_provider_settings(
            db_path,
            {
                "edge": {
                    "provider": "ollama",
                    "base_url": "http://edge.local",
                    "api_path": "/api/chat",
                    "model": "gemma4:e4b",
                    "timeout_seconds": 2,
                }
            },
        )
