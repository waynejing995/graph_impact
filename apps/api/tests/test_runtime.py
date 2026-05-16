import json
import os
import socket
import subprocess
import time
import unittest
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[3]


class ApiRuntimeTests(unittest.TestCase):
    def test_dev_api_script_starts_live_server_and_serves_http(self):
        package_json = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertIn("dev:api", package_json.get("scripts", {}))

        port = _free_port()
        env = os.environ.copy()
        env["PORT"] = str(port)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        with TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "missing.db")
            process = subprocess.Popen(
                ["pnpm", "dev:api"],
                cwd=REPO_ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            try:
                payload = _wait_for_json(
                    f"http://127.0.0.1:{port}/providers/settings?db_path={db_path}",
                    process,
                )
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                if process.stdout is not None:
                    process.stdout.close()

            self.assertEqual(payload, {})
            self.assertFalse(Path(db_path).exists())


def _wait_for_json(url: str, process: subprocess.Popen[str]) -> dict:
    deadline = time.time() + 15
    last_error: Exception | None = None
    while time.time() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise AssertionError(f"dev:api exited before serving HTTP:\n{output}")
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - retry loop diagnostics
            last_error = exc
            time.sleep(0.2)
    output = process.stdout.read() if process.stdout else ""
    raise AssertionError(f"dev:api did not serve {url}: {last_error}\n{output}")


def _free_port() -> int:
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()


if __name__ == "__main__":
    unittest.main()
