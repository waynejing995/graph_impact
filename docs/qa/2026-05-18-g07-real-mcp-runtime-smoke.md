# G07 Real MCP Runtime Smoke

Date: 2026-05-18

## Scope

This QA closes the previous G07 optional MCP runtime smoke residual. The system
Python 3.9 runtime cannot install the current `mcp` package because `mcp>=1.2`
requires Python 3.10 or newer, so the real runtime smoke uses the bundled
Codex Python 3.12 runtime.

## Runtime

```bash
/Users/chenjingwen/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 --version
/Users/chenjingwen/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pip show mcp
```

Result:

```text
Python 3.12.13
mcp 1.27.1
```

The bundled runtime already had `mcp`; it needed the core graph dependency for
the MCP tool tests:

```bash
/Users/chenjingwen/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pip install --user -r packages/core/requirements.txt
```

## RED

Before installing core runtime dependencies in the Python 3.12 runtime, the
real MCP package test could build the server, but MCP tool tests failed when
query/graph paths imported NetworkX:

```text
ModuleNotFoundError: No module named 'networkx'
```

## GREEN

Targeted real runtime server smoke:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
  /Users/chenjingwen/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  -m unittest apps.mcp.tests.test_server.McpServerTests.test_builds_fastmcp_server_when_runtime_package_is_installed -v
```

Result:

```text
Ran 1 test in 0.343s
OK
```

Full MCP tools/server suite in the same real runtime:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
  /Users/chenjingwen/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  -m unittest apps.mcp.tests.test_tools apps.mcp.tests.test_server -v
```

Result:

```text
Ran 29 tests in 19.002s
OK
```

## Boundary

This is a local runtime smoke for the installed Python MCP SDK and the ASIP MCP
server/tool functions. It does not claim external client interoperability beyond
the FastMCP server construction and tool registration/execution tests.
