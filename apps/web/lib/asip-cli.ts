import { existsSync } from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";

export const repoRoot = path.resolve(process.cwd(), "../..");
export const defaultDbPath = path.join(repoRoot, "data/asip.db");
export const defaultConfigPath = path.join(repoRoot, "configs/edge_cases/full-corpus-qwen35.json");

export function runAsipCli<T>(args: string[]): T {
  const result = spawnSync("python3", ["-m", "asip.cli", ...args], {
    cwd: repoRoot,
    env: {
      ...process.env,
      PYTHONDONTWRITEBYTECODE: "1",
      PYTHONPATH: [path.join(repoRoot, "packages/core/src"), repoRoot].join(":")
    },
    encoding: "utf8"
  });

  if (result.status !== 0) {
    throw new Error(result.stderr || result.stdout || `asip cli failed: ${args.join(" ")}`);
  }
  return JSON.parse(result.stdout) as T;
}

export function ensureWorkbenchIndex() {
  if (hasWorkbenchEvidence()) {
    return;
  }
  runAsipCli(["index", "--config", defaultConfigPath, "--db", defaultDbPath]);
}

function hasWorkbenchEvidence() {
  if (!existsSync(defaultDbPath)) {
    return false;
  }
  const result = spawnSync(
    "python3",
    [
      "-c",
      [
        "import sqlite3,sys",
        "con=sqlite3.connect(sys.argv[1])",
        "cur=con.execute(\"select count(*) from sqlite_master where type='table' and name='evidence'\")",
        "exists=cur.fetchone()[0]",
        "print(con.execute('select count(*) from evidence').fetchone()[0] if exists else 0)"
      ].join(";"),
      defaultDbPath
    ],
    { encoding: "utf8" }
  );
  return result.status === 0 && Number(result.stdout.trim()) > 0;
}
