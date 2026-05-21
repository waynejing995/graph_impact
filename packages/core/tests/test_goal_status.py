import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from asip.cli import main as cli_main
from asip.goal_status import run_goal_status


class GoalStatusTests(unittest.TestCase):
    def test_goal_status_reports_current_blockers_from_completion_gate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = root / "repo"
            repo.mkdir()
            self._git(repo, "init", "-b", "main")
            self._git(repo, "config", "user.email", "asip@example.test")
            self._git(repo, "config", "user.name", "ASIP Test")
            (repo / "tracked.txt").write_text("ok\n", encoding="utf-8")
            self._git(repo, "add", "tracked.txt")
            self._git(repo, "commit", "-m", "initial")
            head = self._git(repo, "rev-parse", "HEAD").stdout.strip()

            git_gate = self._write_json(
                root / "git-gate.json",
                {
                    "source": "asip.git_gate",
                    "gate_status": "pass",
                    "branch": "main",
                    "head": head,
                    "upstream": "",
                },
            )
            completion = self._write_json(
                root / "completion-gate.json",
                {
                    "source": "asip.completion_gate",
                    "generated_at": "2026-05-21T12:00:00+00:00",
                    "gate_status": "blocked",
                    "summary": {"total": 20, "passed": 18, "blocked": 2, "failed": 0, "missing": 0},
                    "artifacts": {
                        "git_gate": {
                            "status": "loaded",
                            "path": str(git_gate),
                            "source": "asip.git_gate",
                            "gate_status": "pass",
                        }
                    },
                    "requirements": [
                        {"id": "real_index_db", "title": "Real index", "status": "pass"},
                        {
                            "id": "hosted_openai_compatible",
                            "title": "Hosted smoke",
                            "status": "blocked",
                            "evidence": "credential missing",
                            "failure_reasons": ["credential env var is missing: OPENAI_API_KEY"],
                        },
                        {
                            "id": "residual_acceptance",
                            "title": "Residual acceptance",
                            "status": "blocked",
                            "evidence": "accepted_residuals=0",
                            "failure_reasons": ["explicit user acceptance has not been recorded"],
                        },
                    ],
                },
            )

            result = run_goal_status(repo_root=repo, completion_json=completion)

            self.assertEqual(result["goal_status"], "blocked")
            self.assertEqual(result["completion_gate_status"], "blocked")
            self.assertTrue(result["artifact_matches_current_head"])
            self.assertEqual(
                [item["id"] for item in result["blockers"]],
                ["hosted_openai_compatible", "residual_acceptance"],
            )
            self.assertEqual([item["id"] for item in result["next_actions"]], ["hosted_openai_compatible", "residual_acceptance"])

    def test_goal_status_blocks_stale_completion_artifact_head(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = root / "repo"
            repo.mkdir()
            self._git(repo, "init", "-b", "main")
            self._git(repo, "config", "user.email", "asip@example.test")
            self._git(repo, "config", "user.name", "ASIP Test")
            (repo / "tracked.txt").write_text("ok\n", encoding="utf-8")
            self._git(repo, "add", "tracked.txt")
            self._git(repo, "commit", "-m", "initial")
            current_head = self._git(repo, "rev-parse", "HEAD").stdout.strip()

            git_gate = self._write_json(
                root / "git-gate.json",
                {
                    "source": "asip.git_gate",
                    "gate_status": "pass",
                    "branch": "main",
                    "head": "old-head",
                },
            )
            completion = self._write_json(
                root / "completion-gate.json",
                {
                    "source": "asip.completion_gate",
                    "gate_status": "pass",
                    "summary": {"total": 20, "passed": 20, "blocked": 0, "failed": 0, "missing": 0},
                    "artifacts": {"git_gate": {"status": "loaded", "path": str(git_gate)}},
                    "requirements": [{"id": "git_gate", "title": "Git", "status": "pass"}],
                },
            )

            result = run_goal_status(repo_root=repo, completion_json=completion)

            self.assertEqual(result["goal_status"], "blocked")
            self.assertFalse(result["artifact_matches_current_head"])
            self.assertIn(
                f"completion artifact head old-head does not match current head {current_head}",
                result["failure_reasons"],
            )

    def test_goal_status_cli_writes_artifact_and_require_pass_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = root / "repo"
            repo.mkdir()
            self._git(repo, "init", "-b", "main")
            completion = self._write_json(
                root / "completion-gate.json",
                {
                    "source": "asip.completion_gate",
                    "gate_status": "blocked",
                    "summary": {"total": 1, "passed": 0, "blocked": 1, "failed": 0, "missing": 0},
                    "requirements": [
                        {
                            "id": "residual_acceptance",
                            "title": "Residual acceptance",
                            "status": "blocked",
                            "evidence": "accepted_residuals=0",
                            "failure_reasons": ["explicit user acceptance has not been recorded"],
                        }
                    ],
                },
            )
            output_json = root / "goal-status.json"

            exit_code = cli_main(
                [
                    "goal-status",
                    "--repo-root",
                    str(repo),
                    "--completion-json",
                    str(completion),
                    "--output-json",
                    str(output_json),
                    "--require-pass",
                ]
            )

            self.assertEqual(exit_code, 2)
            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["source"], "asip.goal_status")
            self.assertEqual(payload["goal_status"], "blocked")

    def _write_json(self, path: Path, payload: dict) -> Path:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def _git(self, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=True,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )


if __name__ == "__main__":
    unittest.main()
