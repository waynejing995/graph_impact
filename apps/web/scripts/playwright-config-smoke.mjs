import assert from "node:assert/strict";
import path from "node:path";
import { pathToFileURL } from "node:url";

const configUrl = pathToFileURL(path.resolve(import.meta.dirname, "../playwright.config.ts"));
const envKeys = [
  "PLAYWRIGHT_BASE_URL",
  "PLAYWRIGHT_SKIP_WEB_SERVER",
  "PLAYWRIGHT_WEB_SERVER_COMMAND",
  "PLAYWRIGHT_REUSE_EXISTING_SERVER"
];

let importCounter = 0;

async function withEnv(overrides, callback) {
  const previous = new Map(envKeys.map((key) => [key, process.env[key]]));
  for (const key of envKeys) {
    if (Object.hasOwn(overrides, key)) {
      const value = overrides[key];
      if (value === undefined) {
        delete process.env[key];
      } else {
        process.env[key] = value;
      }
    } else {
      delete process.env[key];
    }
  }

  try {
    return await callback();
  } finally {
    for (const [key, value] of previous) {
      if (value === undefined) {
        delete process.env[key];
      } else {
        process.env[key] = value;
      }
    }
  }
}

async function loadConfig(label) {
  importCounter += 1;
  const configModule = await import(`${configUrl.href}?smoke=${label}-${importCounter}`);
  return configModule.default;
}

function singleWebServer(config) {
  assert.ok(!Array.isArray(config.webServer), "webServer must stay a single shared server config");
  return config.webServer;
}

await withEnv({}, async () => {
  const config = await loadConfig("default");
  const webServer = singleWebServer(config);
  assert.equal(config.use.baseURL, "http://127.0.0.1:3100");
  assert.equal(webServer.url, "http://127.0.0.1:3100");
  assert.equal(webServer.command, "pnpm dev --hostname 127.0.0.1 --port 3100");
  assert.equal(webServer.reuseExistingServer, false);
});

await withEnv({ PLAYWRIGHT_BASE_URL: "http://localhost:3998" }, async () => {
  const config = await loadConfig("base-url");
  const webServer = singleWebServer(config);
  assert.equal(config.use.baseURL, "http://localhost:3998");
  assert.equal(webServer.url, "http://localhost:3998");
  assert.equal(webServer.command, "pnpm dev --hostname localhost --port 3998");
  assert.equal(webServer.reuseExistingServer, false);
});

await withEnv({ PLAYWRIGHT_SKIP_WEB_SERVER: "1" }, async () => {
  const config = await loadConfig("skip-server");
  assert.equal(config.webServer, undefined);
  assert.equal(config.use.baseURL, "http://127.0.0.1:3100");
});

await withEnv({ PLAYWRIGHT_REUSE_EXISTING_SERVER: "true" }, async () => {
  const config = await loadConfig("strict-reuse");
  const webServer = singleWebServer(config);
  assert.equal(webServer.reuseExistingServer, false, "reuse must require explicit value 1");
});

await withEnv(
  {
    PLAYWRIGHT_BASE_URL: "http://127.0.0.1:3999",
    PLAYWRIGHT_REUSE_EXISTING_SERVER: "1",
    PLAYWRIGHT_WEB_SERVER_COMMAND: "pnpm dev --hostname 127.0.0.1 --port 3999"
  },
  async () => {
    const config = await loadConfig("reuse-custom-command");
    const webServer = singleWebServer(config);
    assert.equal(config.use.baseURL, "http://127.0.0.1:3999");
    assert.equal(webServer.url, "http://127.0.0.1:3999");
    assert.equal(webServer.command, "pnpm dev --hostname 127.0.0.1 --port 3999");
    assert.equal(webServer.reuseExistingServer, true);
  }
);

console.log("playwright config smoke passed");
