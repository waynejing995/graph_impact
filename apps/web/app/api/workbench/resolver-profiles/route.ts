import { NextResponse } from "next/server";
import { defaultDbPath, runAsipCli } from "@/lib/asip-cli";
import { listResolverProfiles as listCommittedResolverProfiles } from "@/lib/workbench-data";

export function GET() {
  try {
    const backend = runAsipCli<{ profiles?: Array<{ id: string }> }>(["resolver-list", "--db", defaultDbPath]);
    const merged = new Map<string, unknown>();
    for (const profile of listCommittedResolverProfiles()) {
      merged.set(profile.id, profile);
    }
    for (const profile of backend.profiles ?? []) {
      merged.set(profile.id, profile);
    }
    return NextResponse.json({ profiles: Array.from(merged.values()) });
  } catch {
    return NextResponse.json({ profiles: listCommittedResolverProfiles() });
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
      body.path ?? `configs/resolvers/${id}.yaml`
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
