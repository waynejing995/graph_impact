import net from "node:net";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

function parseArgs(argv) {
  const args = {
    baseUrl: process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3100",
    outputJson: "",
    allowBlocked: false,
    requireExistingTarget: false,
    timeoutMs: 1000
  };
  for (let index = 0; index < argv.length; index += 1) {
    const item = argv[index];
    if (item === "--") {
      continue;
    } else if (item === "--allow-blocked") {
      args.allowBlocked = true;
    } else if (item === "--require-existing-target") {
      args.requireExistingTarget = true;
    } else if (item === "--base-url") {
      args.baseUrl = argv[++index] ?? "";
    } else if (item.startsWith("--base-url=")) {
      args.baseUrl = item.slice("--base-url=".length);
    } else if (item === "--output-json") {
      args.outputJson = argv[++index] ?? "";
    } else if (item.startsWith("--output-json=")) {
      args.outputJson = item.slice("--output-json=".length);
    } else if (item === "--timeout-ms") {
      args.timeoutMs = Number(argv[++index] ?? args.timeoutMs);
    } else if (item.startsWith("--timeout-ms=")) {
      args.timeoutMs = Number(item.slice("--timeout-ms=".length));
    } else {
      throw new Error(`unknown argument: ${item}`);
    }
  }
  if (!Number.isFinite(args.timeoutMs) || args.timeoutMs <= 0) {
    throw new Error("--timeout-ms must be a positive number");
  }
  return args;
}

function listenProbe(host, port, timeoutMs) {
  return new Promise((resolve) => {
    const server = net.createServer();
    let settled = false;
    const startedAt = Date.now();

    const finish = (result) => {
      if (settled) {
        return;
      }
      settled = true;
      clearTimeout(timer);
      server.removeAllListeners();
      if (server.listening) {
        server.close(() => resolve({ ...result, elapsed_ms: Date.now() - startedAt }));
      } else {
        resolve({ ...result, elapsed_ms: Date.now() - startedAt });
      }
    };

    const timer = setTimeout(() => {
      finish({
        status: "blocked",
        code: "TIMEOUT",
        message: `listen probe timed out after ${timeoutMs}ms`
      });
    }, timeoutMs);

    server.once("error", (error) => {
      const code = typeof error.code === "string" ? error.code : "ERROR";
      finish({
        status: code === "EADDRINUSE" ? "fail" : "blocked",
        code,
        message: error.message
      });
    });
    server.once("listening", () => {
      const address = server.address();
      finish({
        status: "pass",
        code: "LISTEN_OK",
        message: "listen probe succeeded",
        bound_port: typeof address === "object" && address ? address.port : port
      });
    });
    server.listen({ host, port });
  });
}

function connectProbe(host, port, timeoutMs) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host, port });
    let settled = false;
    const startedAt = Date.now();

    const finish = (result) => {
      if (settled) {
        return;
      }
      settled = true;
      clearTimeout(timer);
      socket.removeAllListeners();
      socket.destroy();
      resolve({ ...result, elapsed_ms: Date.now() - startedAt });
    };

    const timer = setTimeout(() => {
      finish({
        status: "blocked",
        code: "TIMEOUT",
        message: `connect probe timed out after ${timeoutMs}ms`
      });
    }, timeoutMs);

    socket.once("connect", () => {
      finish({
        status: "pass",
        code: "CONNECT_OK",
        message: "existing target connection succeeded"
      });
    });
    socket.once("error", (error) => {
      const code = typeof error.code === "string" ? error.code : "ERROR";
      finish({
        status: code === "ECONNREFUSED" ? "fail" : "blocked",
        code,
        message: error.message
      });
    });
  });
}

function derivedHostAndPort(baseUrl) {
  const parsed = new URL(baseUrl);
  const protocolDefault = parsed.protocol === "https:" ? "443" : "80";
  return {
    host: parsed.hostname || "127.0.0.1",
    port: Number(parsed.port || protocolDefault),
    normalized_url: parsed.toString()
  };
}

function skippedProbe(message) {
  return {
    status: "skipped",
    code: "NOT_APPLICABLE",
    message,
    elapsed_ms: 0
  };
}

const args = parseArgs(process.argv.slice(2));
const target = derivedHostAndPort(args.baseUrl);
const failureReasons = [];
const preflightMode = args.requireExistingTarget ? "existing_target" : "fresh_server";
const capability =
  preflightMode === "fresh_server"
    ? await listenProbe(target.host, 0, args.timeoutMs)
    : skippedProbe("fresh-server local listen capability probe skipped for existing-target mode");
const targetPort =
  preflightMode === "fresh_server"
    ? await listenProbe(target.host, target.port, args.timeoutMs)
    : skippedProbe("fresh-server target-port listen probe skipped for existing-target mode");
const existingTarget = await connectProbe(target.host, target.port, args.timeoutMs);

if (preflightMode === "fresh_server") {
  if (capability.status !== "pass") {
    failureReasons.push(`local listen capability ${capability.status}: ${capability.code} ${capability.message}`);
  }
  if (targetPort.status !== "pass") {
    failureReasons.push(`target port ${target.port} ${targetPort.status}: ${targetPort.code} ${targetPort.message}`);
  }
} else if (existingTarget.status !== "pass") {
  failureReasons.push(
    `existing target ${target.port} ${existingTarget.status}: ${existingTarget.code} ${existingTarget.message}`
  );
}

const result = {
  source: "asip.web.browser_gate_preflight",
  generated_at: new Date().toISOString(),
  base_url: args.baseUrl,
  normalized_url: target.normalized_url,
  host: target.host,
  port: target.port,
  timeout_ms: args.timeoutMs,
  preflight_mode: preflightMode,
  require_existing_target: args.requireExistingTarget,
  existing_target_reachable: existingTarget.status === "pass",
  gate_status: failureReasons.length === 0 ? "pass" : "blocked",
  failure_reasons: failureReasons,
  probes: {
    listen_capability: capability,
    target_port: targetPort,
    target_connect: existingTarget
  }
};

const rendered = `${JSON.stringify(result, null, 2)}\n`;
if (args.outputJson) {
  mkdirSync(path.dirname(args.outputJson), { recursive: true });
  writeFileSync(args.outputJson, rendered, "utf8");
}
process.stdout.write(rendered);

if (result.gate_status !== "pass" && !args.allowBlocked) {
  process.exitCode = 2;
}
