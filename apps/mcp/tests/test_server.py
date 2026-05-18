import importlib.util
import sys
import types
import unittest

from apps.mcp.server import build_server


class McpServerTests(unittest.TestCase):
    def test_build_server_registers_all_product_tools_with_fastmcp(self):
        registered = []

        class FakeFastMCP:
            def __init__(self, name):
                self.name = name

            def tool(self):
                def register(fn):
                    registered.append(fn.__name__)
                    return fn

                return register

        original_modules = {
            name: sys.modules.get(name)
            for name in ["mcp", "mcp.server", "mcp.server.fastmcp"]
        }
        mcp_module = types.ModuleType("mcp")
        server_module = types.ModuleType("mcp.server")
        fastmcp_module = types.ModuleType("mcp.server.fastmcp")
        fastmcp_module.FastMCP = FakeFastMCP
        mcp_module.server = server_module
        server_module.fastmcp = fastmcp_module
        sys.modules["mcp"] = mcp_module
        sys.modules["mcp.server"] = server_module
        sys.modules["mcp.server.fastmcp"] = fastmcp_module
        try:
            server = build_server()
        finally:
            for name, module in original_modules.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module

        self.assertEqual(server.name, "asip-workbench")
        self.assertEqual(
            sorted(registered),
            sorted(
                [
                    "acceptance_runs",
                    "corpora_index",
                    "corpora_list",
                    "corpus_add",
                    "entity_explain",
                    "evidence_detail",
                    "graph_expand",
                    "graph_rebuild",
                    "job_detail",
                    "jobs_list",
                    "ollama_models",
                    "provider_settings_save",
                    "provider_settings_show",
                    "resolver_inspect",
                    "resolver_profile_add",
                    "resolver_profile_validate",
                    "resolver_profiles_list",
                    "run_acceptance",
                    "search_evidence",
                    "semantic_edges_generate_batch",
                    "semantic_edges_generate",
                ]
            ),
        )

    def test_builds_fastmcp_server_when_runtime_package_is_installed(self):
        if importlib.util.find_spec("mcp") is None:
            self.skipTest("optional mcp package is not installed in this Python runtime")

        server = build_server()

        self.assertIsNotNone(server)


if __name__ == "__main__":
    unittest.main()
