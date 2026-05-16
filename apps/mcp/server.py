"""ASIP MCP server entrypoint.

Install the optional `mcp` Python package, then run:

    PYTHONPATH=. python3 apps/mcp/server.py
"""

from __future__ import annotations

from .tools import (
    acceptance_runs,
    corpora_index,
    corpora_list,
    corpus_add,
    entity_explain,
    evidence_detail,
    graph_expand,
    ollama_models,
    provider_settings_save,
    provider_settings_show,
    resolver_inspect,
    resolver_profile_add,
    resolver_profile_validate,
    resolver_profiles_list,
    run_acceptance,
    search_evidence,
    semantic_edges_generate,
)


MCP_PRODUCT_TOOLS = [
    search_evidence,
    graph_expand,
    semantic_edges_generate,
    evidence_detail,
    entity_explain,
    corpora_list,
    corpus_add,
    corpora_index,
    resolver_inspect,
    resolver_profiles_list,
    resolver_profile_add,
    resolver_profile_validate,
    provider_settings_show,
    provider_settings_save,
    ollama_models,
    acceptance_runs,
    run_acceptance,
]


def build_server():
    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on optional package
        raise RuntimeError("Install the optional `mcp` package to run the ASIP MCP server.") from exc

    server = FastMCP("asip-workbench")
    for tool in MCP_PRODUCT_TOOLS:
        server.tool()(tool)
    return server


if __name__ == "__main__":
    build_server().run()
