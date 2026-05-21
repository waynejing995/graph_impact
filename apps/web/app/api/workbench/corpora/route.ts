import { NextResponse } from "next/server";
import { defaultConfigPath, defaultDbPath, runAsipCli } from "@/lib/asip-cli";
import { explicitTextOrError } from "@/lib/request-paths";

export function GET(request: Request) {
  let dbPath = defaultDbPath;
  try {
    dbPath = explicitTextOrError(new URL(request.url).searchParams.get("dbPath"), "dbPath") ?? defaultDbPath;
  } catch (error) {
    return NextResponse.json(
      { corpora: [], error: error instanceof Error ? error.message : "dbPath cannot be blank" },
      { status: 400 }
    );
  }
  try {
    return NextResponse.json(
      runAsipCli<Record<string, unknown>>(["corpora", "--db", dbPath, "--config", defaultConfigPath])
    );
  } catch (error) {
    return NextResponse.json(
      { corpora: [], error: error instanceof Error ? error.message : "corpora failed" },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as {
    id?: string;
    repo?: string;
    sourceRoot?: string;
    source_root?: string;
    include?: string[] | string;
    subfolders?: Array<{ relativeRoot?: string; relative_root?: string; path?: string; include?: string[] | string }> | string;
    type?: string;
    dbPath?: string;
  };
  const id = body.id?.trim();
  const sourceRoot = (body.sourceRoot ?? body.source_root ?? "").trim();
  let dbPath = defaultDbPath;
  try {
    dbPath = explicitTextOrError(body.dbPath, "dbPath") ?? defaultDbPath;
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "dbPath cannot be blank" },
      { status: 400 }
    );
  }
  if (!id || !sourceRoot) {
    return NextResponse.json({ error: "Corpus id and source root are required." }, { status: 400 });
  }
  const include = Array.isArray(body.include)
    ? body.include
    : String(body.include ?? "**/*")
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
  try {
    const args = [
      "corpus-add",
      "--db",
      dbPath,
      "--id",
      id,
      "--repo",
      body.repo ?? "local",
      "--source-root",
      sourceRoot,
      "--type",
      body.type ?? "code"
    ];
    for (const pattern of include.length ? include : ["**/*"]) {
      args.push("--include", pattern);
    }
    const subfolders = normalizeSubfolders(body.subfolders);
    for (const subfolder of subfolders) {
      args.push("--subfolder", `${subfolder.relativeRoot}:${subfolder.include.join(",")}`);
    }
    return NextResponse.json(runAsipCli<Record<string, unknown>>(args));
  } catch (error) {
    const message = error instanceof Error ? error.message : "corpus add failed";
    return NextResponse.json(
      { error: message },
      { status: message.includes("repo-relative") ? 400 : 500 }
    );
  }
}

function normalizeSubfolders(
  value: Array<{ relativeRoot?: string; relative_root?: string; path?: string; include?: string[] | string }> | string | undefined
) {
  if (!value) {
    return [];
  }
  const rawItems = typeof value === "string" ? value.split(/\n+/).map((item) => item.trim()).filter(Boolean) : value;
  return rawItems.flatMap((item) => {
    if (typeof item === "string") {
      const [relativeRoot, includeText = ""] = item.split(/[:=]/, 2);
      const include = includeText.split(",").map((part) => part.trim()).filter(Boolean);
      const normalizedRoot = normalizeRelativeRoot(relativeRoot);
      return normalizedRoot ? [{ relativeRoot: normalizedRoot, include: include.length ? include : ["**/*"] }] : [];
    }
    const relativeRoot = normalizeRelativeRoot(item.relativeRoot ?? item.relative_root ?? item.path ?? "");
    if (!relativeRoot) {
      return [];
    }
    const include = Array.isArray(item.include)
      ? item.include
      : String(item.include ?? "**/*").split(",").map((part) => part.trim()).filter(Boolean);
    return [{ relativeRoot, include: include.length ? include : ["**/*"] }];
  });
}

function normalizeRelativeRoot(value: string) {
  const text = String(value ?? "").trim().replaceAll("\\", "/");
  if (!text || text === ".") {
    return "";
  }
  const parts = text.split("/");
  if (text.startsWith("/") || text.startsWith("~") || text.includes(":") || parts.some((part) => !part || part === "." || part === "..")) {
    throw new Error(`corpus subfolder must be repo-relative: ${text}`);
  }
  return parts.join("/");
}
