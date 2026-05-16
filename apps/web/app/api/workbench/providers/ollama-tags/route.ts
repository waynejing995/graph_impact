import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const baseUrl = request.nextUrl.searchParams.get("baseUrl") ?? "http://localhost:11434";
  const endpoint = `${baseUrl.replace(/\/+$/, "")}/api/tags`;

  try {
    const response = await fetch(endpoint, { cache: "no-store" });
    if (!response.ok) {
      return NextResponse.json({ error: `Ollama returned ${response.status}` }, { status: response.status });
    }
    return NextResponse.json(await response.json());
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Ollama detection failed" },
      { status: 502 }
    );
  }
}
