import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  const payload = (await request.json().catch(() => ({}))) as {
    provider?: string;
    api_base_url?: string;
    api_path?: string;
    preferred?: string;
  };
  const model = payload.preferred || "unset";
  const provider = payload.provider || "unknown";

  if (model === "unset") {
    return NextResponse.json({ ok: false, error: "Provider smoke failed: edge model is unset" }, { status: 400 });
  }

  if (provider === "ollama") {
    const baseUrl = (payload.api_base_url || "http://localhost:11434").replace(/\/+$/, "");
    const requestedUrl = `${baseUrl}/api/tags`;
    try {
      const response = await fetch(requestedUrl, { cache: "no-store", signal: AbortSignal.timeout(5000) });
      const body = await response.json().catch(() => ({}));
      const models = Array.isArray(body.models) ? body.models.map((item: { name?: string }) => item.name).filter(Boolean) : [];
      const hasModel = models.includes(model);
      return NextResponse.json({
        ok: response.ok && hasModel,
        provider,
        model,
        requestedUrl,
        status: response.status,
        message: response.ok
          ? `Provider smoke ${hasModel ? "passed" : "reached Ollama but model was not listed"}: ${model}`
          : `Provider smoke failed: Ollama returned ${response.status}`,
        models
      }, { status: response.ok ? 200 : 502 });
    } catch (error) {
      return NextResponse.json(
        {
          ok: false,
          provider,
          model,
          requestedUrl,
          error: error instanceof Error ? error.message : "Ollama smoke failed"
        },
        { status: 502 }
      );
    }
  }

  const requestedUrl = `${(payload.api_base_url || "").replace(/\/+$/, "")}${payload.api_path || "/v1/chat/completions"}`;
  return NextResponse.json({
    ok: false,
    provider,
    model,
    requestedUrl,
    error: "OpenAI-compatible live smoke requires configured credentials; request shape is ready but no secret was sent."
  }, { status: 400 });
}
