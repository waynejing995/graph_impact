import { chromium } from "@playwright/test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const outputDir = resolve(__dirname, "images");
const baseURL = process.env.ASIP_WEB_BASE_URL ?? "http://127.0.0.1:3100";

const pages = [
  ["/", "evidence-workbench.png"],
  ["/graph", "graph-explorer.png"],
  ["/corpus", "corpus.png"],
  ["/resolver-profiles", "resolver-profiles.png"],
  ["/acceptance", "acceptance-tests.png"],
  ["/settings", "settings.png"]
];

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 2048, height: 1280 } });

for (const [route, fileName] of pages) {
  await page.goto(`${baseURL}${route}`, { waitUntil: "networkidle" });
  await page.screenshot({ path: resolve(outputDir, fileName), fullPage: false });
  console.log(`${route} -> ${fileName}`);
}

await browser.close();
