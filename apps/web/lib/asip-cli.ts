import { existsSync } from "node:fs";
import path from "node:path";
import { spawn, spawnSync } from "node:child_process";

export const repoRoot = path.resolve(process.cwd(), "../..");
export const defaultDbPath = path.join(repoRoot, "data/asip.db");
export const defaultConfigPath = path.join(repoRoot, "configs/edge_cases/full-corpus-gemma4-e4b.json");

export function runAsipCli<T>(args: string[], envOverrides: Record<string, string> = {}): T {
  const result = spawnSync("python3", ["-m", "asip.cli", ...args], {
    cwd: repoRoot,
    env: {
      ...process.env,
      ...envOverrides,
      PYTHONDONTWRITEBYTECODE: "1",
      PYTHONPATH: [path.join(repoRoot, "packages/core/src"), repoRoot].join(":")
    },
    encoding: "utf8",
    maxBuffer: 128 * 1024 * 1024
  });

  if (result.status !== 0) {
    throw new Error(result.stderr || result.stdout || `asip cli failed: ${args.join(" ")}`);
  }
  return JSON.parse(result.stdout) as T;
}

export function runAsipCliAsync<T>(args: string[], envOverrides: Record<string, string> = {}): Promise<T> {
  return new Promise((resolve, reject) => {
    const child = spawn("python3", ["-m", "asip.cli", ...args], {
      cwd: repoRoot,
      env: {
        ...process.env,
        ...envOverrides,
        PYTHONDONTWRITEBYTECODE: "1",
        PYTHONPATH: [path.join(repoRoot, "packages/core/src"), repoRoot].join(":")
      }
    });
    let stdout = "";
    let stderr = "";
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk) => {
      stdout += chunk;
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk;
    });
    child.on("error", reject);
    child.on("close", (status) => {
      if (status !== 0) {
        reject(new Error(stderr || stdout || `asip cli failed: ${args.join(" ")}`));
        return;
      }
      try {
        resolve(JSON.parse(stdout) as T);
      } catch (error) {
        reject(error);
      }
    });
  });
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
