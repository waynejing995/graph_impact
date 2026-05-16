import { NextResponse } from "next/server";
import { defaultConfigPath, defaultDbPath, runAsipCli } from "@/lib/asip-cli";

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as {
    configPath?: string;
    dbPath?: string;
    corpusIds?: string[];
  };
  const configPath = body.configPath ?? defaultConfigPath;
  const dbPath = body.dbPath ?? defaultDbPath;
  try {
    const args = ["index", "--config", configPath, "--db", dbPath];
    for (const corpusId of body.corpusIds ?? []) {
      args.push("--corpus-id", corpusId);
    }
    const summary = runAsipCli<{
      source: string;
      db_path: string;
      corpus_ids?: string[];
      documents: number;
      chunks: number;
      evidence: number;
      edges: number;
      files: number;
      job_id: number;
      provider_settings?: Record<string, unknown>;
    }>(args);
    return NextResponse.json({
      status: "indexed",
      source: summary.source,
      dbPath: summary.db_path === defaultDbPath ? "data/asip.db" : summary.db_path,
      corpusIds: summary.corpus_ids ?? body.corpusIds ?? [],
      documents: summary.documents,
      chunks: summary.chunks,
      evidence: summary.evidence,
      edges: summary.edges,
      files: summary.files,
      jobId: summary.job_id,
      providerSettings: summary.provider_settings ?? {}
    });
  } catch (error) {
    return NextResponse.json(
      {
        status: "failed",
        error: error instanceof Error ? error.message : "index job failed"
      },
      { status: 500 }
    );
  }
}
