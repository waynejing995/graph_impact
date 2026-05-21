import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
AUDIT_PATH = REPO_ROOT / "scripts" / "audit_callback_edges.py"
SPEC = importlib.util.spec_from_file_location("audit_callback_edges", AUDIT_PATH)
audit_callback_edges = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit_callback_edges)


class CallbackEdgeAuditTests(unittest.TestCase):
    def test_audit_passes_real_oracle_and_counts_callback_edges(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "callbacks.db"
            self._write_db(
                db_path,
                [
                    (
                        "amdgpu_device_ip_init",
                        "gfx_v10_0_hw_init",
                        "drivers/gpu/drm/amd/amdgpu/amdgpu_device.c",
                        {
                            "call_kind": "vtable_dispatch",
                            "function": "amdgpu_device_ip_init",
                            "callee": "gfx_v10_0_hw_init",
                            "type_flow": "clang_ast_json",
                            "dispatch_scope": "typed",
                        },
                    )
                ],
            )

            result = audit_callback_edges.run_audit(
                db_path,
                assert_no_parser_pollution=True,
                max_ambiguous_fanout=1,
                real_oracles=["drivers/gpu/drm/amd/amdgpu/amdgpu_device.c:amdgpu_device_ip_init"],
            )

            self.assertEqual(result["gate_status"], "pass")
            self.assertEqual(result["summary"]["callback_edge_count"], 1)
            self.assertEqual(result["summary"]["real_oracle_passed"], 1)

    def test_audit_blocks_parser_pollution(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "callbacks.db"
            self._write_db(
                db_path,
                [
                    (
                        "else",
                        "valid_callee",
                        "drivers/gpu/drm/amd/amdgpu/bad.c",
                        {
                            "call_kind": "vtable_dispatch",
                            "function": "else",
                            "callee": "valid_callee",
                        },
                    )
                ],
            )

            result = audit_callback_edges.run_audit(db_path, assert_no_parser_pollution=True)

            self.assertEqual(result["gate_status"], "blocked")
            self.assertIn("parser pollution candidates found: 1", result["failure_reasons"])

    def test_audit_blocks_excessive_ambiguous_fanout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "callbacks.db"
            self._write_db(
                db_path,
                [
                    (
                        "dispatch",
                        f"callee_{index}",
                        "drivers/gpu/drm/amd/amdgpu/dispatch.c",
                        {
                            "call_kind": "vtable_dispatch",
                            "function": "dispatch",
                            "callee": f"callee_{index}",
                            "callback_ambiguous": True,
                            "dispatch_scope": "ambiguous",
                        },
                    )
                    for index in range(3)
                ],
            )

            result = audit_callback_edges.run_audit(db_path, max_ambiguous_fanout=2)

            self.assertEqual(result["gate_status"], "blocked")
            self.assertTrue(
                any("unexplained ambiguous callback fanout exceeds 2" in reason for reason in result["failure_reasons"])
            )

    def test_audit_allows_explained_dynamic_dispatch_fanout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "callbacks.db"
            self._write_db(
                db_path,
                [
                    (
                        "amdgpu_device_ip_init",
                        f"callee_{index}",
                        "drivers/gpu/drm/amd/amdgpu/amdgpu_device.c",
                        {
                            "call_kind": "vtable_dispatch",
                            "function": "amdgpu_device_ip_init",
                            "callee": f"callee_{index}",
                            "callback_ambiguous": True,
                            "dispatch_scope": "ambiguous",
                            "receiver": "adev->ip_blocks[i].version->funcs",
                            "receiver_tables": ["gfx_ip_funcs", "sdma_ip_funcs"],
                        },
                    )
                    for index in range(3)
                ],
            )

            result = audit_callback_edges.run_audit(db_path, max_ambiguous_fanout=2)

            self.assertEqual(result["gate_status"], "pass")
            self.assertEqual(result["summary"]["explained_dynamic_dispatch_edge_count"], 3)
            self.assertEqual(result["summary"]["unexplained_ambiguous_callback_edge_count"], 0)

    def test_audit_allows_typed_receiver_dynamic_dispatch_fanout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "callbacks.db"
            self._write_db(
                db_path,
                [
                    (
                        "amdgpu_ras_query_error_status_helper",
                        f"ras_query_{index}",
                        "drivers/gpu/drm/amd/amdgpu/amdgpu_ras.c",
                        {
                            "call_kind": "vtable_dispatch",
                            "function": "amdgpu_ras_query_error_status_helper",
                            "callee": f"ras_query_{index}",
                            "callback_ambiguous": True,
                            "dispatch_scope": "ambiguous",
                            "receiver": "block_obj->hw_ops",
                            "receiver_type": "amdgpu_ras_block_hw_ops",
                            "type_flow": "clang_ast_json",
                            "callback_table_type": "amdgpu_ras_block_hw_ops",
                            "callback_candidate_count": 17,
                        },
                    )
                    for index in range(3)
                ],
            )

            result = audit_callback_edges.run_audit(db_path, max_ambiguous_fanout=2)

            self.assertEqual(result["gate_status"], "pass")
            self.assertEqual(result["summary"]["explained_dynamic_dispatch_edge_count"], 3)
            self.assertEqual(result["summary"]["unexplained_ambiguous_callback_edge_count"], 0)

    def test_audit_allows_named_typed_ops_table_dynamic_dispatch_fanout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "callbacks.db"
            self._write_db(
                db_path,
                [
                    (
                        "aca_bank_parser",
                        f"aca_bank_parser_impl_{index}",
                        "drivers/gpu/drm/amd/amdgpu/amdgpu_aca.c",
                        {
                            "call_kind": "vtable_dispatch",
                            "function": "aca_bank_parser",
                            "callee": f"aca_bank_parser_impl_{index}",
                            "callback_ambiguous": True,
                            "dispatch_scope": "ambiguous",
                            "receiver": "bank_ops",
                            "receiver_type": "aca_bank_ops",
                            "callback_table": f"aca_bank_ops_{index}",
                            "callback_table_type": "aca_bank_ops",
                            "callback_candidate_count": 9,
                        },
                    )
                    for index in range(3)
                ],
            )

            result = audit_callback_edges.run_audit(db_path, max_ambiguous_fanout=2)

            self.assertEqual(result["gate_status"], "pass")
            self.assertEqual(result["summary"]["explained_dynamic_dispatch_edge_count"], 3)
            self.assertEqual(result["summary"]["unexplained_ambiguous_callback_edge_count"], 0)

    def _write_db(self, db_path, edges):
        with sqlite3.connect(db_path) as connection:
            connection.execute(
                """
                create table edges (
                    id integer primary key,
                    src text not null,
                    dst text not null,
                    relation text not null,
                    confidence real not null,
                    stage text not null default 'deterministic',
                    source text not null default '',
                    path text not null default '',
                    line_start integer,
                    line_end integer,
                    provenance_json text not null default '{}'
                )
                """
            )
            for index, (src, dst, path, provenance) in enumerate(edges, start=1):
                connection.execute(
                    """
                    insert into edges
                    (id, src, dst, relation, confidence, path, line_start, line_end, provenance_json)
                    values (?, ?, ?, 'calls', 0.7, ?, 10, 20, json(?))
                    """,
                    (index, src, dst, path, __import__("json").dumps(provenance)),
                )


if __name__ == "__main__":
    unittest.main()
