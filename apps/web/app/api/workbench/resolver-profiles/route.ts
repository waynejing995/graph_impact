import { NextResponse } from "next/server";
import { existsSync } from "node:fs";
import path from "node:path";
import { defaultDbPath, repoRoot, runAsipCli } from "@/lib/asip-cli";
import { explicitTextOrError } from "@/lib/request-paths";
import { listResolverProfiles as listCommittedResolverProfiles } from "@/lib/workbench-data";

export function GET(request: Request) {
  let dbPath = defaultDbPath;
  try {
    dbPath = explicitTextOrError(new URL(request.url).searchParams.get("dbPath"), "dbPath") ?? defaultDbPath;
  } catch (error) {
    return NextResponse.json(
      { profiles: [], error: error instanceof Error ? error.message : "dbPath cannot be blank" },
      { status: 400 }
    );
  }
  try {
    const backend = runAsipCli<{ profiles?: Array<{ id: string; path?: string; config?: unknown }> }>([
      "resolver-list",
      "--db",
      dbPath
    ]);
    const merged = new Map<string, unknown>();
    for (const profile of listCommittedResolverProfiles()) {
      if (resolverConfigExists(profile.path)) {
        merged.set(profile.id, profile);
      }
    }
    for (const profile of backend.profiles ?? []) {
      if (resolverProfileHasConfig(profile)) {
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
    functionNormalization?: FunctionNormalizationInput;
    validateSource?: string;
    dbPath?: string;
  };
  const id = body.id?.trim();
  if (!id) {
    return NextResponse.json({ error: "Resolver profile id is required." }, { status: 400 });
  }
  const resolverPath = body.path?.trim() || `configs/resolvers/${id}.yaml`;
  const wrappers = body.wrappers?.length ? body.wrappers : body.wrapper ? [body.wrapper] : [];
  const inlineConfig = buildResolverProfileConfig({
    id,
    language: body.language ?? "cpp",
    wrappers,
    strategy: body.strategy ?? "macro",
    functionNormalization: body.functionNormalization
  });
  if (!resolverConfigExists(resolverPath) && !inlineConfig) {
    return NextResponse.json(
      { error: `Resolver profile must reference an existing YAML config: ${resolverPath}` },
      { status: 400 }
    );
  }
  let dbPath = defaultDbPath;
  try {
    dbPath = explicitTextOrError(body.dbPath, "dbPath") ?? defaultDbPath;
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "dbPath cannot be blank" },
      { status: 400 }
    );
  }
  try {
    if (body.validateSource !== undefined) {
      return NextResponse.json(
        runAsipCli<Record<string, unknown>>([
          "resolver-validate",
          "--db",
          dbPath,
          "--id",
          id,
          "--source",
          body.validateSource
        ])
      );
    }
    const args = [
      "resolver-add",
      "--db",
      dbPath,
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
    if (inlineConfig) {
      args.push("--config-json", JSON.stringify(inlineConfig));
    }
    return NextResponse.json(runAsipCli<Record<string, unknown>>(args));
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "resolver profile operation failed" },
      { status: 500 }
    );
  }
}

type FunctionNormalizationInput = {
  enabled?: boolean;
  rules?: Array<{
    id?: string;
    enabled?: boolean;
    match?: string;
    canonical?: string;
    mergePolicy?: {
      mode?: string;
      warnRegisterOverlapBelow?: number | string;
      splitRegisterOverlapBelow?: number | string;
    };
    merge_policy?: {
      mode?: string;
      warn_register_overlap_below?: number | string;
      split_register_overlap_below?: number | string;
    };
  }>;
};

type NormalizedFunctionRule = {
  id: string;
  enabled: boolean;
  match: string;
  canonical: string;
  merge_policy: {
    mode: string;
    warn_register_overlap_below: number;
    split_register_overlap_below: number;
  };
};

function resolverProfileHasConfig(profile: { path?: string; config?: unknown }) {
  return resolverConfigExists(profile.path) || isObjectRecord(profile.config);
}

function buildResolverProfileConfig({
  id,
  language,
  wrappers,
  strategy,
  functionNormalization
}: {
  id: string;
  language: string;
  wrappers: string[];
  strategy: string;
  functionNormalization?: FunctionNormalizationInput;
}) {
  if (!functionNormalization) {
    return null;
  }
  const wrapperAccess = strategy && strategy !== "macro" ? strategy : "reference";
  const wrapperConfig = Object.fromEntries(
    wrappers.filter(Boolean).map((wrapper) => [wrapper, { symbol_arg: 0, access: wrapperAccess }])
  );
  const rules: NormalizedFunctionRule[] = [];
  for (const rule of functionNormalization.rules ?? []) {
    const idValue = rule.id?.trim();
    const match = rule.match?.trim();
    const canonical = rule.canonical?.trim();
    if (!idValue || !match || !canonical) {
      continue;
    }
    const mergePolicy = rule.merge_policy ?? {
      mode: rule.mergePolicy?.mode,
      warn_register_overlap_below: rule.mergePolicy?.warnRegisterOverlapBelow,
      split_register_overlap_below: rule.mergePolicy?.splitRegisterOverlapBelow
    };
    rules.push({
      id: idValue,
      enabled: rule.enabled ?? true,
      match,
      canonical,
      merge_policy: {
        mode: mergePolicy.mode ?? "concept_with_implementations",
        warn_register_overlap_below: numberOrDefault(mergePolicy.warn_register_overlap_below, 0.35),
        split_register_overlap_below: numberOrDefault(mergePolicy.split_register_overlap_below, 0.1)
      }
    });
  }
  return {
    id,
    language,
    wrappers: wrapperConfig,
    graph: {
      function_normalization: {
        enabled: functionNormalization.enabled === true,
        rules
      }
    }
  };
}

function numberOrDefault(value: number | string | undefined, fallback: number) {
  const parsed = Number(value ?? fallback);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function isObjectRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
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
