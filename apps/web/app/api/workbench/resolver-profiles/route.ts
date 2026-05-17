import { NextResponse } from "next/server";
import { existsSync } from "node:fs";
import path from "node:path";
import { defaultDbPath, repoRoot, runAsipCli } from "@/lib/asip-cli";
import { listResolverProfiles as listCommittedResolverProfiles } from "@/lib/workbench-data";

export function GET() {
  try {
    const backend = runAsipCli<{ profiles?: Array<{ id: string; path?: string }> }>(["resolver-list", "--db", defaultDbPath]);
    const merged = new Map<string, unknown>();
    for (const profile of listCommittedResolverProfiles()) {
      if (resolverConfigExists(profile.path)) {
        merged.set(profile.id, profile);
      }
    }
    for (const profile of backend.profiles ?? []) {
      if (resolverConfigExists(profile.path)) {
        merged.set(profile.id, profile);
      }
    }
    return NextResponse.json({ profiles: Array.from(merged.values()) });
  } catch {
    return NextResponse.json({
      profiles: listCommittedResolverProfiles().filter((profile) => resolverConfigExists(profile.path))
    });
  }
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as {
    id?: string;
    language?: string;
    wrappers?: string[];
    wrapper?: string;
    strategy?: string;
    path?: string;
    enabled?: boolean;
    validateSource?: string;
  };
  const id = body.id?.trim();
  if (!id) {
    return NextResponse.json({ error: "Resolver profile id is required." }, { status: 400 });
  }
  const resolverPath = body.path?.trim() || `configs/resolvers/${id}.yaml`;
  if (!resolverConfigExists(resolverPath)) {
    return NextResponse.json(
      { error: `Resolver profile must reference an existing YAML config: ${resolverPath}` },
      { status: 400 }
    );
  }
  try {
    if (body.validateSource !== undefined) {
      return NextResponse.json(
        runAsipCli<Record<string, unknown>>([
          "resolver-validate",
          "--db",
          defaultDbPath,
          "--id",
          id,
          "--source",
          body.validateSource
        ])
      );
    }
    const wrappers = body.wrappers?.length ? body.wrappers : body.wrapper ? [body.wrapper] : [];
    const args = [
      "resolver-add",
      "--db",
      defaultDbPath,
      "--id",
      id,
      "--language",
      body.language ?? "cpp",
      "--strategy",
      body.strategy ?? "macro",
      "--path",
      resolverPath
    ];
    for (const wrapper of wrappers) {
      args.push("--wrapper", wrapper);
    }
    if (body.enabled === false) {
      args.push("--disabled");
    }
    return NextResponse.json(runAsipCli<Record<string, unknown>>(args));
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "resolver profile operation failed" },
      { status: 500 }
    );
  }
}

function resolverConfigExists(configPath: string | undefined) {
  if (!configPath) {
    return false;
  }
  if (!/\.ya?ml$/i.test(configPath)) {
    return false;
  }
  const resolved = path.isAbsolute(configPath) ? configPath : path.join(repoRoot, configPath);
  return existsSync(resolved);
}
