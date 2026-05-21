import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from asip.cli import main as cli_main
from asip.closure_gates import run_git_gate, run_residual_acceptance_gate


class ClosureGateTests(unittest.TestCase):
    def test_residual_gate_blocks_until_user_acceptance_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            residual_doc = root / "g13.md"
            residual_doc.write_text(
                "\n".join(
                    [
                        "# G13",
                        "",
                        "Status: Partial; final user acceptance remains blocking",
                        "",
                        "| Spec area | MVP status | User acceptance status |",
                        "| --- | --- | --- |",
                        "| Full clangd/libclang | Partial | Needs acceptance |",
                    ]
                ),
                encoding="utf-8",
            )

            result = run_residual_acceptance_gate(residual_doc)

            self.assertEqual(result["gate_status"], "blocked")
            self.assertFalse(result["accepted"])
            self.assertEqual(result["ledger_items_count"], 1)
            self.assertIn("explicit user acceptance has not been recorded", result["failure_reasons"])

    def test_residual_gate_can_record_explicit_acceptance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            residual_doc = root / "g13.md"
            residual_doc.write_text(
                "\n".join(
                    [
                        "# G13",
                        "",
                        "Status: Accepted",
                        "",
                        "| Spec area | MVP status | User acceptance status |",
                        "| --- | --- | --- |",
                        "| Full clangd/libclang | Deferred | Accepted |",
                    ]
                ),
                encoding="utf-8",
            )

            result = run_residual_acceptance_gate(
                residual_doc,
                accepted=True,
                accepted_residuals=["Full clangd/libclang"],
            )

            self.assertEqual(result["gate_status"], "pass")
            self.assertEqual(result["accepted_residuals"], ["Full clangd/libclang"])

    def test_residual_gate_requires_accepted_document_status_even_with_user_acceptance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            residual_doc = root / "g13.md"
            residual_doc.write_text(
                "\n".join(
                    [
                        "# G13",
                        "",
                        "Status: Partial; final user acceptance remains blocking",
                        "",
                        "| Spec area | MVP status | User acceptance status |",
                        "| --- | --- | --- |",
                        "| Full clangd/libclang | Deferred | Needs acceptance |",
                    ]
                ),
                encoding="utf-8",
            )

            result = run_residual_acceptance_gate(
                residual_doc,
                accepted=True,
                accepted_residuals=["Full clangd/libclang"],
            )

            self.assertEqual(result["gate_status"], "blocked")
            self.assertIn(
                "residual document status remains open: Status: Partial; final user acceptance remains blocking",
                result["failure_reasons"],
            )

    def test_residual_gate_blocks_when_only_some_acceptance_required_rows_are_accepted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            residual_doc = root / "g13.md"
            residual_doc.write_text(
                "\n".join(
                    [
                        "# G13",
                        "",
                        "Status: Accepted",
                        "",
                        "| Spec area | MVP status | User acceptance status |",
                        "| --- | --- | --- |",
                        "| Full clangd/libclang | Deferred | Needs acceptance |",
                        "| Credentialed live QA | Deferred | Needs acceptance |",
                    ]
                ),
                encoding="utf-8",
            )

            result = run_residual_acceptance_gate(
                residual_doc,
                accepted=True,
                accepted_residuals=["Full clangd/libclang"],
            )

            self.assertEqual(result["gate_status"], "blocked")
            self.assertIn(
                "residual row needs acceptance but is not listed in accepted_residuals: Credentialed live QA",
                result["failure_reasons"],
            )

    def test_residual_gate_does_not_accept_wildcard_residual_names(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            residual_doc = root / "g13.md"
            residual_doc.write_text(
                "\n".join(
                    [
                        "# G13",
                        "",
                        "Status: Accepted",
                        "",
                        "| Spec area | MVP status | User acceptance status |",
                        "| --- | --- | --- |",
                        "| Full clangd/libclang | Deferred | Needs acceptance |",
                    ]
                ),
                encoding="utf-8",
            )

            result = run_residual_acceptance_gate(
                residual_doc,
                accepted=True,
                accepted_residuals=["all"],
            )

            self.assertEqual(result["gate_status"], "blocked")
            self.assertIn(
                "residual row needs acceptance but is not listed in accepted_residuals: Full clangd/libclang",
                result["failure_reasons"],
            )

    def test_git_gate_blocks_dirty_unpushed_repo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._git(root, "init")
            self._git(root, "config", "user.email", "asip@example.test")
            self._git(root, "config", "user.name", "ASIP Test")
            (root / "tracked.txt").write_text("ok\n", encoding="utf-8")
            self._git(root, "add", "tracked.txt")
            self._git(root, "commit", "-m", "initial")
            (root / "tracked.txt").write_text("dirty\n", encoding="utf-8")

            result = run_git_gate(root)

            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(result["worktree_status"], "dirty")
            self.assertFalse(result["pushed"])
            self.assertTrue(any("worktree has" in reason for reason in result["failure_reasons"]))

    def test_git_gate_cli_writes_artifact(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._git(root, "init")
            output_json = root / "git-gate.json"

            exit_code = cli_main(
                [
                    "git-gate",
                    "--repo-root",
                    str(root),
                    "--output-json",
                    str(output_json),
                ]
            )

            self.assertEqual(exit_code, 0)
            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["source"], "asip.git_gate")
            self.assertEqual(payload["gate_status"], "blocked")

    def test_residual_gate_cli_require_pass_returns_nonzero_when_blocked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            residual_doc = root / "g13.md"
            output_json = root / "residual-gate.json"
            residual_doc.write_text(
                "\n".join(
                    [
                        "# G13",
                        "",
                        "Status: Partial; final user acceptance remains blocking",
                        "",
                        "| Spec area | MVP status | User acceptance status |",
                        "| --- | --- | --- |",
                        "| Full clangd/libclang | Deferred | Needs acceptance |",
                    ]
                ),
                encoding="utf-8",
            )

            exit_code = cli_main(
                [
                    "residual-gate",
                    "--residual-doc",
                    str(residual_doc),
                    "--accepted",
                    "--accepted-residual",
                    "Full clangd/libclang",
                    "--output-json",
                    str(output_json),
                    "--require-pass",
                ]
            )

            self.assertEqual(exit_code, 2)
            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["gate_status"], "blocked")

    def _git(self, cwd: Path, *args: str) -> None:
        subprocess.run(["git", *args], cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


if __name__ == "__main__":
    unittest.main()
