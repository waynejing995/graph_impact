import { NextResponse } from "next/server";
import { defaultConfigPath, defaultDbPath, runAsipCli } from "@/lib/asip-cli";

export function GET() {
  try {
    return NextResponse.json(
      runAsipCli<Record<string, unknown>>(["corpora", "--db", defaultDbPath, "--config", defaultConfigPath])
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
    type?: string;
  };
  const id = body.id?.trim();
  const sourceRoot = (body.sourceRoot ?? body.source_root ?? "").trim();
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
      defaultDbPath,
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
    return NextResponse.json(runAsipCli<Record<string, unknown>>(args));
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "corpus add failed" },
      { status: 500 }
    );
  }
}
