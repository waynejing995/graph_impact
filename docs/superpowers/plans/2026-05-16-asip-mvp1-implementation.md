# ASIP MVP-1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build ASIP MVP-1 as a register/symbol-centered hybrid evidence retrieval system over AMDGPU code, MxGPU code, register headers, repo docs, and text-based PDFs.

**Architecture:** The reusable Python core lives in `packages/core/src/asip`; `apps/api` and `apps/mcp` are thin application layers over that core. Storage is SQLite-first with FTS5 and `sqlite-vec`; NetworkX is an in-memory graph runtime loaded from SQLite edges. The Web UI is a Next.js + shadcn/ui evidence workbench that consumes FastAPI endpoints.

**Tech Stack:** Python 3.12, uv, FastAPI, pytest, SQLite, FTS5, sqlite-vec, NetworkX, MarkItDown-compatible PDF conversion, Ollama/OpenAI-compatible provider abstraction, MCP, Next.js, React, TypeScript, pnpm, shadcn/ui, Playwright, just.

---

## Source Documents

- Design spec: `docs/specs/2026-05-16-asip-mvp1-design.md`
- Decision log: `docs/brainstorming/2026-05-16-asip-decisions.md`
- Long-range technical spec: `docs/specs/2026-05-16-asip-full-technical-spec.md`

## Implementation Locks

- Python core package: `packages/core/src/asip`
- FastAPI app: `apps/api`
- MCP app: `apps/mcp`
- Web UI: `apps/web`
- Configs: `configs/corpora`, `configs/resolvers`, `configs/models`
- Local data: `data/`
- Default model profile: `configs/models/ollama-local.yaml`
- Vector implementation: `sqlite-vec` behind `asip.storage.vector.VectorStore`
- Graph persistence: SQLite tables
- Graph runtime: NetworkX loaded on demand from SQLite edges
- First graph UI: bounded right-inspector relationship panel, not a full canvas
- Browser QA: required through real browser control for the static design preview now and the real Next.js app during implementation.

## Local Ollama Model Policy

This machine was inspected on 2026-05-16:

```text
CPU: Apple M4
Memory: 24GB
Installed larger models: qwen3-embedding:4b, qwen3.5:4b
New low-memory defaults pulled and verified: nomic-embed-text, qwen2.5:1.5b
```

Model defaults:

- `configs/models/ollama-local.yaml` uses `nomic-embed-text` for embeddings.
- Embedding smoke verified: Ollama HTTP API returned a 768-dimensional vector for `GCVM_L2_CNTL register field evidence`.
- `qwen2.5:1.5b` is the optional semantic-edge JSON model.
- Semantic-edge extraction is disabled by default and enabled only for explicit extraction jobs or acceptance tests.
- `qwen2.5:1.5b` smoke verified through Ollama chat JSON mode with `format: json`, `num_ctx: 2048`, `temperature: 0`, and `keep_alive: 0s`.
- `qwen3-embedding:4b` and `qwen3.5:4b` remain optional high-capability profiles, not MVP defaults.
- Tests and runbooks must stop models after smoke checks and assert `ollama ps` is empty when the smoke is complete.

## Superpowers Execution Policy

- Before implementation begins, create or verify an isolated implementation worktree with `superpowers:using-git-worktrees`; implementation work must not start directly on `main`.
- Execute this plan with `superpowers:subagent-driven-development`.
- The controller dispatches one fresh implementer subagent per task. Do not run implementation subagents for different tasks in parallel because several tasks build on earlier committed interfaces.
- The controller gives each implementer the exact task text, source documents, current task dependencies, and touched file list. Implementers should not be asked to rediscover the whole plan.
- Each implementer must use `superpowers:test-driven-development`: write the test first, run it and confirm the expected failure, implement the minimal code, then run the test and confirm the pass.
- After each implementer finishes, dispatch a spec compliance reviewer subagent. Only after spec compliance is approved, dispatch a code quality reviewer subagent.
- If either reviewer finds an issue, send the same task back for a focused fix and rerun that reviewer gate.
- Mark a task complete only after implementation, TDD verification, spec review, code quality review, and the task commit are all complete.

## File Structure

```text
.
├── Justfile
├── package.json
├── pnpm-workspace.yaml
├── pyproject.toml
├── apps/
│   ├── api/
│   │   ├── pyproject.toml
│   │   ├── src/asip_api/main.py
│   │   └── tests/
│   ├── mcp/
│   │   ├── pyproject.toml
│   │   ├── src/asip_mcp/server.py
│   │   └── tests/
│   └── web/
│       ├── app/
│       ├── components/
│       ├── lib/
│       ├── tests/
│       └── package.json
├── configs/
│   ├── corpora/amd-mvp1.yaml
│   ├── models/ollama-local.yaml
│   ├── models/openai-compatible.yaml
│   └── resolvers/
│       ├── linux-amdgpu.yaml
│       ├── amd-mxgpu.yaml
│       └── toy-python.yaml
├── packages/core/
│   ├── pyproject.toml
│   ├── src/asip/
│   │   ├── ingestion/
│   │   ├── models/
│   │   ├── providers/
│   │   ├── resolver/
│   │   ├── retrieval/
│   │   ├── storage/
│   │   └── graph/
│   └── tests/
└── testdata/
    └── fixtures/
        ├── corpus/
        ├── docs/
        ├── pdf/
        ├── registers/
        └── resolver/
```

## Definition Of Done

- `just setup`, `just dev`, `just test`, `just lint`, `just api`, `just mcp`, and `just web` are defined.
- Unit tests cover register parsing, resolver profiles, PDF ingestion, model providers, SQLite/FTS/vector storage, and NetworkX graph loading.
- Integration tests index a deterministic fixture corpus without network access.
- Acceptance tests execute and assert behavior for all nine MVP-1 queries from the design spec.
- Web UI shows the evidence workbench as the first screen and passes Playwright smoke, responsive, and visual-constraint tests.
- MCP exposes search, explain, resolved-chain, graph expansion, resolver-profile, and acceptance-test tools.
- Real AMD corpus indexing can be run from config without changing code.
- Every production-code task has RED/GREEN evidence in the task notes or commit body, plus completed spec and quality review gates.

---

### Task 1: Workspace Scaffold And Commands

**Files:**
- Create: `pyproject.toml`
- Create: `package.json`
- Create: `pnpm-workspace.yaml`
- Create: `Justfile`
- Create: `packages/core/pyproject.toml`
- Create: `apps/api/pyproject.toml`
- Create: `apps/mcp/pyproject.toml`
- Create: `apps/web/package.json`
- Create: `apps/web/components.json`
- Create: `apps/web/next.config.ts`
- Create: `apps/web/playwright.config.ts`
- Create: `apps/web/postcss.config.mjs`
- Create: `apps/web/tsconfig.json`
- Test: `packages/core/tests/test_imports.py`

- [ ] **Step 1: Write the failing import test**

```python
# packages/core/tests/test_imports.py
def test_core_package_imports():
    import asip

    assert asip.__version__
```

- [ ] **Step 2: Run the failing test**

Run: `uv run pytest packages/core/tests/test_imports.py -q`
Expected: FAIL because `asip` is not importable.

- [ ] **Step 3: Create the Python workspace**

Create root `pyproject.toml`:

```toml
[project]
name = "graph-impact"
version = "0.1.0"
requires-python = ">=3.12"

[tool.uv.workspace]
members = ["packages/core", "apps/api", "apps/mcp"]

[tool.pytest.ini_options]
testpaths = ["packages/core/tests", "apps/api/tests", "apps/mcp/tests"]
pythonpath = ["packages/core/src", "apps/api/src", "apps/mcp/src"]
```

Create `packages/core/pyproject.toml`:

```toml
[project]
name = "asip-core"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "httpx>=0.27",
  "markitdown>=0.0.1",
  "networkx>=3.3",
  "pydantic>=2.8",
  "pyyaml>=6.0",
  "sqlite-vec>=0.1.1",
]

[dependency-groups]
dev = ["pytest>=8.2", "respx>=0.21"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

Create `apps/api/pyproject.toml`:

```toml
[project]
name = "asip-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "asip-core",
  "fastapi[standard]>=0.115",
  "httpx>=0.27",
]

[dependency-groups]
dev = ["pytest>=8.2"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.uv.sources]
asip-core = { workspace = true }
```

Create `apps/mcp/pyproject.toml`:

```toml
[project]
name = "asip-mcp"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "asip-core",
  "mcp>=1.9",
]

[dependency-groups]
dev = ["pytest>=8.2"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.uv.sources]
asip-core = { workspace = true }
```

Create `packages/core/src/asip/__init__.py`:

```python
__version__ = "0.1.0"
```

- [ ] **Step 4: Create top-level JavaScript workspace files**

Create `package.json`:

```json
{
  "name": "graph-impact",
  "private": true,
  "scripts": {
    "dev": "pnpm --filter @graph-impact/web dev",
    "web": "pnpm --filter @graph-impact/web dev",
    "test:web": "pnpm --filter @graph-impact/web test"
  },
  "packageManager": "pnpm@9.0.0"
}
```

Create `pnpm-workspace.yaml`:

```yaml
packages:
  - "apps/web"
```

Create `apps/web/package.json`:

```json
{
  "name": "@graph-impact/web",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "test": "playwright test",
    "test:ui": "playwright test --ui"
  },
  "dependencies": {
    "@radix-ui/react-dropdown-menu": "latest",
    "@radix-ui/react-dialog": "latest",
    "@radix-ui/react-select": "latest",
    "@radix-ui/react-scroll-area": "latest",
    "@radix-ui/react-separator": "latest",
    "@radix-ui/react-tabs": "latest",
    "@radix-ui/react-toggle-group": "latest",
    "@radix-ui/react-tooltip": "latest",
    "class-variance-authority": "latest",
    "clsx": "latest",
    "lucide-react": "latest",
    "next": "latest",
    "react": "latest",
    "react-dom": "latest",
    "tailwind-merge": "latest"
  },
  "devDependencies": {
    "@playwright/test": "latest",
    "@types/node": "latest",
    "@types/react": "latest",
    "@types/react-dom": "latest",
    "postcss": "latest",
    "tailwindcss": "latest",
    "typescript": "latest"
  }
}
```

Create shadcn metadata in `apps/web/components.json`:

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "new-york",
  "rsc": true,
  "tsx": true,
  "tailwind": {
    "config": "",
    "css": "app/globals.css",
    "baseColor": "neutral",
    "cssVariables": true,
    "prefix": ""
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  },
  "iconLibrary": "lucide"
}
```

The implementer must initialize shadcn in `apps/web` and commit generated UI primitives:

```bash
cd apps/web
pnpm dlx shadcn@latest init --yes
pnpm dlx shadcn@latest add button input select badge tabs table scroll-area separator tooltip toggle-group sheet dialog skeleton sidebar command
```

- [ ] **Step 5: Create command runner**

Create `Justfile`:

```make
setup:
    uv sync --all-packages
    pnpm install

dev:
    just api & just mcp & just web

api:
    uv run fastapi dev apps/api/src/asip_api/main.py

mcp:
    uv run python -m asip_mcp.server

web:
    pnpm --filter @graph-impact/web dev

index:
    uv run python -m asip.cli index --config configs/corpora/amd-mvp1.yaml

test:
    uv run pytest -q
    pnpm --filter @graph-impact/web test

lint:
    uv run python -m compileall packages/core/src apps/api/src apps/mcp/src
    pnpm --filter @graph-impact/web build
```

- [ ] **Step 6: Verify and commit**

Run: `uv run pytest packages/core/tests/test_imports.py -q`
Expected: PASS.

```bash
git add pyproject.toml package.json pnpm-workspace.yaml Justfile packages/core apps/api apps/mcp apps/web
git commit -m "chore: scaffold ASIP workspace"
```

---

### Task 2: Core Models And SQLite Schema

**Files:**
- Create: `packages/core/src/asip/models/evidence.py`
- Create: `packages/core/src/asip/storage/schema.sql`
- Create: `packages/core/src/asip/storage/db.py`
- Test: `packages/core/tests/storage/test_schema.py`

- [ ] **Step 1: Write schema tests**

```python
# packages/core/tests/storage/test_schema.py
from asip.storage.db import connect, migrate


def test_schema_creates_core_tables(tmp_path):
    db_path = tmp_path / "asip.db"
    conn = connect(db_path)
    migrate(conn)

    tables = {
        row[0]
        for row in conn.execute(
            "select name from sqlite_master where type in ('table', 'virtual table')"
        )
    }
    assert {"corpora", "documents", "chunks", "entities", "edges", "evidence_items"}.issubset(tables)


def test_fts_table_is_queryable(tmp_path):
    conn = connect(tmp_path / "asip.db")
    migrate(conn)
    conn.execute(
        "insert into evidence_fts(rowid, symbol, body) values (?, ?, ?)",
        (1, "GCVM_L2_CNTL", "WREG32_SOC15 writes GCVM_L2_CNTL"),
    )
    rows = conn.execute(
        "select symbol from evidence_fts where evidence_fts match ?",
        ("GCVM_L2_CNTL",),
    ).fetchall()
    assert rows == [("GCVM_L2_CNTL",)]
```

- [ ] **Step 2: Run the failing schema tests**

Run: `uv run pytest packages/core/tests/storage/test_schema.py -q`
Expected: FAIL because storage modules do not exist.

- [ ] **Step 3: Add evidence model**

```python
# packages/core/src/asip/models/evidence.py
from enum import StrEnum
from pydantic import BaseModel, Field


class SourceType(StrEnum):
    code = "code"
    doc = "doc"
    register = "register"
    pdf = "pdf"


class AccessType(StrEnum):
    read = "read"
    write = "write"
    read_modify_write = "read_modify_write"
    field_set = "field_set"
    field_get = "field_get"
    mention = "mention"


class EvidenceItem(BaseModel):
    id: str
    source_type: SourceType
    repo: str
    path: str
    line_start: int | None = None
    line_end: int | None = None
    page: int | None = None
    symbol: str
    entity_type: str
    ip_block: str | None = None
    asic_or_generation: str | None = None
    access_type: AccessType = AccessType.mention
    confidence: float = Field(ge=0.0, le=1.0)
    snippet: str
    resolved_chain: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Add schema and migration helper**

Create `packages/core/src/asip/storage/schema.sql`:

```sql
create table if not exists corpora (
  id text primary key,
  name text not null,
  config_path text not null,
  metadata text not null default '{}'
);

create table if not exists documents (
  id text primary key,
  corpus_id text references corpora(id),
  repo text not null,
  path text not null,
  source_type text not null check (source_type in ('code', 'doc', 'register', 'pdf')),
  metadata text not null default '{}'
);

create table if not exists chunks (
  id text primary key,
  document_id text not null references documents(id),
  section text,
  line_start integer,
  line_end integer,
  page integer,
  text text not null,
  metadata text not null default '{}'
);

create table if not exists entities (
  id text primary key,
  type text not null,
  name text not null,
  canonical_name text not null,
  repo text,
  metadata text not null default '{}'
);

create table if not exists evidence_items (
  id text primary key,
  source_type text not null check (source_type in ('code', 'doc', 'register', 'pdf')),
  repo text not null,
  path text not null,
  line_start integer,
  line_end integer,
  page integer,
  symbol text not null,
  entity_type text not null,
  ip_block text,
  asic_or_generation text,
  access_type text not null,
  confidence real not null,
  snippet text not null,
  resolved_chain text not null default '[]',
  chunk_id text references chunks(id),
  metadata text not null default '{}'
);

create table if not exists edges (
  id text primary key,
  src_entity_id text not null references entities(id),
  dst_entity_id text not null references entities(id),
  relation_type text not null,
  confidence real not null,
  evidence_id text references evidence_items(id),
  metadata text not null default '{}'
);

create table if not exists resolver_profiles (
  id text primary key,
  name text not null unique,
  language text not null,
  body text not null
);

create table if not exists provider_configs (
  id text primary key,
  name text not null unique,
  api_format text not null,
  base_url text not null,
  model text not null,
  enabled integer not null default 1,
  metadata text not null default '{}'
);

create table if not exists indexing_jobs (
  id text primary key,
  corpus_id text,
  status text not null,
  started_at text not null,
  finished_at text,
  error text
);

create table if not exists vector_items (
  item_id text primary key,
  embedding_model text not null,
  dimensions integer not null,
  metadata text not null default '{}'
);

create virtual table if not exists evidence_fts using fts5(
  symbol,
  body,
  content='',
  tokenize='unicode61'
);
```

Create `packages/core/src/asip/storage/db.py`:

```python
from pathlib import Path
import sqlite3


SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys = on")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text())
    conn.commit()
```

- [ ] **Step 5: Verify and commit**

Run: `uv run pytest packages/core/tests/storage/test_schema.py -q`
Expected: PASS.

```bash
git add packages/core/src/asip/models packages/core/src/asip/storage packages/core/tests/storage
git commit -m "feat: add ASIP core schema"
```

---

### Task 3: Fixture Corpus And Corpus Configs

**Files:**
- Create: `configs/corpora/amd-mvp1.yaml`
- Create: `testdata/fixtures/corpus/amdgpu/gmc_v11_0.c`
- Create: `testdata/fixtures/corpus/mxgpu/gfx_v11_0.c`
- Create: `testdata/fixtures/registers/gc_11_0_0_offset.h`
- Create: `testdata/fixtures/registers/gc_11_0_0_sh_mask.h`
- Create: `testdata/fixtures/docs/amdgpu.rst`
- Test: `packages/core/tests/ingestion/test_corpus_config.py`

- [ ] **Step 1: Write corpus config test**

```python
# packages/core/tests/ingestion/test_corpus_config.py
from pathlib import Path
from asip.ingestion.config import load_corpus_config


def test_load_fixture_corpus_config():
    config = load_corpus_config(Path("configs/corpora/amd-mvp1.yaml"))

    assert config.name == "amd-mvp1"
    assert any(source.kind == "code" for source in config.sources)
    assert any(source.kind == "register_headers" for source in config.sources)
    assert any(source.kind == "docs" for source in config.sources)
```

- [ ] **Step 2: Run the failing test**

Run: `uv run pytest packages/core/tests/ingestion/test_corpus_config.py -q`
Expected: FAIL because config loading is missing.

- [ ] **Step 3: Add deterministic fixture snippets**

`testdata/fixtures/corpus/amdgpu/gmc_v11_0.c` must include:

```c
void gmc_v11_0_init_golden_registers(struct amdgpu_device *adev)
{
    uint32_t tmp = RREG32_SOC15(GC, 0, regGCVM_L2_CNTL);
    tmp = REG_SET_FIELD(tmp, GCVM_L2_CNTL, ENABLE_L2_CACHE, 1);
    WREG32_SOC15(GC, 0, regGCVM_L2_CNTL, tmp);
}
```

`testdata/fixtures/corpus/mxgpu/gfx_v11_0.c` must include:

```c
void xgpu_ai_mailbox_set_l2(struct amd_adapter *adapt)
{
    uint32_t tmp = RREG32(adapt->reg_offset[GC_HWIP][0][regGCVM_L2_CNTL_BASE_IDX] + regGCVM_L2_CNTL);
    tmp = REG_SET_FIELD(tmp, GCVM_L2_CNTL, ENABLE_L2_CACHE, 1);
    WREG32(adapt->reg_offset[GC_HWIP][0][regGCVM_L2_CNTL_BASE_IDX] + regGCVM_L2_CNTL, tmp);
}
```

- [ ] **Step 4: Add corpus config loader**

```python
# packages/core/src/asip/ingestion/config.py
from pathlib import Path
from pydantic import BaseModel
import yaml


class CorpusSource(BaseModel):
    name: str
    kind: str
    path: str
    repo: str


class CorpusConfig(BaseModel):
    name: str
    sources: list[CorpusSource]


def load_corpus_config(path: Path) -> CorpusConfig:
    return CorpusConfig.model_validate(yaml.safe_load(path.read_text()))
```

- [ ] **Step 5: Verify and commit**

Run: `uv run pytest packages/core/tests/ingestion/test_corpus_config.py -q`
Expected: PASS.

```bash
git add configs/corpora testdata/fixtures packages/core/src/asip/ingestion packages/core/tests/ingestion
git commit -m "test: add ASIP fixture corpus"
```

---

### Task 4: Register Header Parser

**Files:**
- Create: `testdata/fixtures/registers/gc_11_0_0_d.h`
- Create: `testdata/fixtures/registers/gc_11_0_0_default.h`
- Create: `packages/core/src/asip/ingestion/register_headers.py`
- Test: `packages/core/tests/ingestion/test_register_headers.py`

- [ ] **Step 1: Write parser tests**

```python
# packages/core/tests/ingestion/test_register_headers.py
from pathlib import Path
from asip.ingestion.register_headers import parse_register_headers


def test_parse_offset_and_field_headers():
    records = parse_register_headers(Path("testdata/fixtures/registers"))
    by_name = {record.name: record for record in records}

    assert by_name["regGCVM_L2_CNTL"].offset == "0x00001400"
    assert by_name["mmGCVM_L2_CNTL"].offset == "0x00001400"
    assert by_name["regGCVM_L2_CNTL"].base_idx_symbol == "regGCVM_L2_CNTL_BASE_IDX"
    assert by_name["GCVM_L2_CNTL.ENABLE_L2_CACHE"].field_shift == 0
    assert by_name["GCVM_L2_CNTL.ENABLE_L2_CACHE"].field_mask == "0x00000001"
    assert by_name["regGCVM_L2_CNTL"].path.endswith("gc_11_0_0_offset.h")
    assert by_name["regGCVM_L2_CNTL"].line_start > 0
    assert by_name["regGCVM_L2_CNTL"].ip_block == "gc"
    assert by_name["regGCVM_L2_CNTL"].asic_or_generation == "11_0_0"


def test_parse_d_and_default_headers():
    records = parse_register_headers(Path("testdata/fixtures/registers"))
    by_name = {record.name: record for record in records}

    assert by_name["GCVM_L2_CNTL"].kind == "register_definition"
    assert by_name["GCVM_L2_CNTL"].default_value == "0x00000000"
```

- [ ] **Step 2: Run the failing parser test**

Run: `uv run pytest packages/core/tests/ingestion/test_register_headers.py -q`
Expected: FAIL because parser module does not exist.

- [ ] **Step 3: Implement parser contracts**

Create `RegisterRecord` with fields:

```python
name: str
kind: Literal["register", "register_definition", "field", "default"]
offset: str | None
base_idx_symbol: str | None
field_shift: int | None
field_mask: str | None
default_value: str | None
path: str
line_start: int
line_end: int
ip_block: str | None
asic_or_generation: str | None
```

Implement parsing rules:

- `#define regNAME 0x...` creates a register record.
- `#define mmNAME 0x...` creates a register record.
- `#define regNAME_BASE_IDX N` attaches `base_idx_symbol`.
- `#define NAME__DEFAULT 0x...` records default values from `*_default.h`.
- `#define NAME 0x...` in `*_d.h` records register definitions without losing aliases.
- `#define NAME__FIELD__SHIFT N` creates or updates field record `NAME.FIELD`.
- `#define NAME__FIELD_MASK 0x...` creates or updates field record `NAME.FIELD`.
- IP and ASIC hints are inferred from header paths such as `gc_11_0_0_offset.h`.

- [ ] **Step 4: Verify and commit**

Run: `uv run pytest packages/core/tests/ingestion/test_register_headers.py -q`
Expected: PASS.

```bash
git add packages/core/src/asip/ingestion/register_headers.py packages/core/tests/ingestion/test_register_headers.py
git commit -m "feat: parse AMD register headers"
```

---

### Task 5: Configurable Resolver Profiles

**Files:**
- Create: `configs/resolvers/linux-amdgpu.yaml`
- Create: `configs/resolvers/amd-mxgpu.yaml`
- Create: `configs/resolvers/toy-python.yaml`
- Create: `packages/core/src/asip/resolver/profile.py`
- Create: `packages/core/src/asip/resolver/engine.py`
- Test: `packages/core/tests/resolver/test_profiles.py`
- Test: `packages/core/tests/resolver/test_engine.py`

- [ ] **Step 1: Write profile and engine tests**

```python
# packages/core/tests/resolver/test_engine.py
from pathlib import Path
from asip.resolver.profile import load_resolver_profile
from asip.resolver.engine import ResolverEngine


def test_resolve_soc15_wrapper_chain():
    profile = load_resolver_profile(Path("configs/resolvers/linux-amdgpu.yaml"))
    engine = ResolverEngine(profile)
    evidence = engine.resolve_line(
        "WREG32_SOC15(GC, 0, regGCVM_L2_CNTL, tmp);",
        repo="linux",
        path="drivers/gpu/drm/amd/amdgpu/gmc_v11_0.c",
        line_number=12,
    )

    assert evidence[0].symbol == "GCVM_L2_CNTL"
    assert evidence[0].access_type == "write"
    assert "regGCVM_L2_CNTL_BASE_IDX" in " ".join(evidence[0].resolved_chain)


def test_resolve_required_amdgpu_wrapper_matrix():
    profile = load_resolver_profile(Path("configs/resolvers/linux-amdgpu.yaml"))
    engine = ResolverEngine(profile)

    cases = [
        ("RREG32(regGCVM_L2_CNTL);", "read", "GCVM_L2_CNTL"),
        ("WREG32(regGCVM_L2_CNTL, tmp);", "write", "GCVM_L2_CNTL"),
        ("RREG32_SOC15(GC, 0, regGCVM_L2_CNTL);", "read", "GCVM_L2_CNTL"),
        ("RREG32_SOC15_OFFSET(GC, 0, regGCVM_L2_CNTL, 4);", "read", "GCVM_L2_CNTL"),
        ("WREG32_SOC15_OFFSET(GC, 0, regGCVM_L2_CNTL, 4, tmp);", "write", "GCVM_L2_CNTL"),
        ("SOC15_REG_OFFSET(GC, 0, regGCVM_L2_CNTL);", "mention", "GCVM_L2_CNTL"),
        ("SOC15_REG_ENTRY(GC, 0, regGCVM_L2_CNTL);", "mention", "GCVM_L2_CNTL"),
        ("WREG32_FIELD15(GC, 0, GCVM_L2_CNTL, ENABLE_L2_CACHE, 1);", "field_set", "GCVM_L2_CNTL.ENABLE_L2_CACHE"),
        ("REG_GET_FIELD(tmp, GCVM_L2_CNTL, ENABLE_L2_CACHE);", "field_get", "GCVM_L2_CNTL.ENABLE_L2_CACHE"),
    ]

    for line, access_type, symbol in cases:
        evidence = engine.resolve_line(line, "linux", "drivers/gpu/drm/amd/amdgpu/gmc_v11_0.c", 20)
        assert evidence[0].access_type == access_type
        assert evidence[0].symbol == symbol


def test_resolve_mxgpu_adapt_reg_offset_chain():
    profile = load_resolver_profile(Path("configs/resolvers/amd-mxgpu.yaml"))
    engine = ResolverEngine(profile)
    evidence = engine.resolve_line(
        "WREG32(adapt->reg_offset[GC_HWIP][0][regGCVM_L2_CNTL_BASE_IDX] + regGCVM_L2_CNTL, tmp);",
        "amd-mxgpu",
        "gim/gfx_v11_0.c",
        33,
    )

    assert evidence[0].symbol == "GCVM_L2_CNTL"
    assert evidence[0].access_type == "write"
    assert "adapt->reg_offset" in " ".join(evidence[0].resolved_chain)


def test_resolver_wrapper_rename_without_code_change(tmp_path):
    profile_path = tmp_path / "resolver.yaml"
    profile_path.write_text(
        """
name: custom
language: c
symbol_prefixes: ["reg", "mm"]
wrappers:
  - name: CUSTOM_WRITE
    access_type: write
    register_arg: 2
    value_arg: 3
    base_idx_suffix: "_BASE_IDX"
"""
    )
    engine = ResolverEngine(load_resolver_profile(profile_path))
    evidence = engine.resolve_line("CUSTOM_WRITE(GC, 0, regGCVM_L2_CNTL, tmp);", "repo", "file.c", 1)
    assert evidence[0].symbol == "GCVM_L2_CNTL"


def test_toy_python_profile_extracts_configured_call():
    profile = load_resolver_profile(Path("configs/resolvers/toy-python.yaml"))
    engine = ResolverEngine(profile)
    evidence = engine.resolve_line('emit_symbol("GCVM_L2_CNTL")', "toy", "example.py", 4)
    assert evidence[0].symbol == "GCVM_L2_CNTL"
```

- [ ] **Step 2: Run the failing resolver tests**

Run: `uv run pytest packages/core/tests/resolver -q`
Expected: FAIL because resolver modules and configs do not exist.

- [ ] **Step 3: Implement profile schema**

`ResolverProfile` must validate:

```python
name: str
language: str
symbol_prefixes: list[str]
wrappers: list[WrapperRule]
field_rules: list[FieldRule] = []
context_patterns: list[str] = []
string_symbol_calls: list[str] = []
```

`WrapperRule` must validate:

```python
name: str
access_type: str
register_arg: int
value_arg: int | None = None
base_idx_suffix: str = "_BASE_IDX"
```

- [ ] **Step 4: Implement line resolver**

Implement `ResolverEngine.resolve_line(...)` so it:

- Reads wrapper names from profile config.
- Splits simple C macro/function arguments with balanced parentheses.
- Normalizes `regGCVM_L2_CNTL` and `mmGCVM_L2_CNTL` to `GCVM_L2_CNTL`.
- Produces `EvidenceItem` with `resolved_chain`.
- Resolves `REG_SET_FIELD(tmp, GCVM_L2_CNTL, ENABLE_L2_CACHE, 1)` as `GCVM_L2_CNTL.ENABLE_L2_CACHE` with `field_set`.
- Resolves `REG_GET_FIELD(tmp, GCVM_L2_CNTL, ENABLE_L2_CACHE)` as `GCVM_L2_CNTL.ENABLE_L2_CACHE` with `field_get`.
- Covers every wrapper named in the confirmed MVP-1 matrix: `WREG32`, `RREG32`, `WREG32_SOC15`, `RREG32_SOC15`, `WREG32_SOC15_OFFSET`, `RREG32_SOC15_OFFSET`, `SOC15_REG_OFFSET`, `SOC15_REG_ENTRY`, `WREG32_FIELD15`, `REG_SET_FIELD`, and `REG_GET_FIELD`.
- Emits distinct resolved chains for Linux `adev->reg_offset[...]` and MxGPU `adapt->reg_offset[...]`.
- Resolves configured Python string calls such as `emit_symbol("GCVM_L2_CNTL")`.

- [ ] **Step 5: Verify and commit**

Run: `uv run pytest packages/core/tests/resolver -q`
Expected: PASS.

```bash
git add configs/resolvers packages/core/src/asip/resolver packages/core/tests/resolver
git commit -m "feat: add configurable resolver profiles"
```

---

### Task 6: Document And PDF Ingestion

**Files:**
- Create: `packages/core/src/asip/ingestion/documents.py`
- Create: `packages/core/src/asip/ingestion/pdf.py`
- Create: `testdata/fixtures/pdf/amd-sample.pdf`
- Test: `packages/core/tests/ingestion/test_documents.py`
- Test: `packages/core/tests/ingestion/test_pdf.py`

- [ ] **Step 1: Write document and PDF tests**

```python
# packages/core/tests/ingestion/test_pdf.py
from pathlib import Path
from asip.ingestion.pdf import convert_pdf


def test_pdf_conversion_preserves_pages():
    pages = convert_pdf(Path("testdata/fixtures/pdf/amd-sample.pdf"))

    assert pages[0].page == 1
    assert "GCVM_L2_CNTL" in pages[0].text
    assert pages[0].source_path.endswith("amd-sample.pdf")


def test_pdf_pages_chunk_into_pdf_evidence_sections():
    from asip.ingestion.documents import chunk_pdf_pages

    pages = convert_pdf(Path("testdata/fixtures/pdf/amd-sample.pdf"))
    chunks = chunk_pdf_pages(pages, repo="amd-docs")

    assert chunks[0].source_type == "pdf"
    assert chunks[0].page == 1
    assert chunks[0].section
    assert "GCVM_L2_CNTL" in chunks[0].text
```

```python
# packages/core/tests/ingestion/test_documents.py
from pathlib import Path
from asip.ingestion.documents import chunk_document


def test_rst_document_chunks_have_sections():
    chunks = chunk_document(Path("testdata/fixtures/docs/amdgpu.rst"), repo="linux")

    assert chunks[0].source_type == "doc"
    assert chunks[0].section
    assert "amdgpu" in chunks[0].path
```

- [ ] **Step 2: Run the failing ingestion tests**

Run: `uv run pytest packages/core/tests/ingestion/test_documents.py packages/core/tests/ingestion/test_pdf.py -q`
Expected: FAIL because ingestion modules are missing.

- [ ] **Step 3: Implement document chunking**

Implement deterministic chunking:

- Markdown headings and RST titles start new sections.
- Code fences stay with their surrounding section.
- Each chunk records `repo`, `path`, `source_type`, `section`, `text`, `line_start`, and `line_end`.
- `chunk_pdf_pages(...)` records `source_type="pdf"`, page number, section label, text, and source path.
- PDF chunks enter the same downstream document/evidence pipeline as Markdown and RST chunks.

- [ ] **Step 4: Implement PDF conversion adapter**

Implement `convert_pdf(path)` with:

- A MarkItDown-compatible conversion path when available.
- Page records containing `page`, `text`, and `source_path`.
- A test fixture path that always returns deterministic text for `testdata/fixtures/pdf/amd-sample.pdf`.

- [ ] **Step 5: Verify and commit**

Run: `uv run pytest packages/core/tests/ingestion/test_documents.py packages/core/tests/ingestion/test_pdf.py -q`
Expected: PASS.

```bash
git add packages/core/src/asip/ingestion/documents.py packages/core/src/asip/ingestion/pdf.py packages/core/tests/ingestion testdata/fixtures/pdf
git commit -m "feat: ingest docs and text PDFs"
```

---

### Task 7: Provider Abstraction And Vector Store

**Files:**
- Create: `configs/models/ollama-local.yaml`
- Create: `configs/models/openai-compatible.yaml`
- Create: `packages/core/src/asip/providers/config.py`
- Create: `packages/core/src/asip/providers/embeddings.py`
- Create: `packages/core/src/asip/providers/semantic_edges.py`
- Create: `packages/core/src/asip/storage/vector.py`
- Test: `packages/core/tests/providers/test_embeddings.py`
- Test: `packages/core/tests/providers/test_semantic_edges.py`
- Test: `packages/core/tests/storage/test_vector.py`

- [ ] **Step 1: Write provider tests**

```python
# packages/core/tests/providers/test_embeddings.py
from asip.providers.embeddings import EmbeddingProvider


def test_ollama_embedding_response_is_normalized(respx_mock):
    respx_mock.post("http://localhost:11434/api/embeddings").respond(
        json={"embedding": [0.1, 0.2, 0.3]}
    )
    provider = EmbeddingProvider(
        name="ollama-local",
        base_url="http://localhost:11434",
        model="nomic-embed-text",
        api_format="ollama",
    )

    assert provider.embed(["GCVM_L2_CNTL"]) == [[0.1, 0.2, 0.3]]


def test_openai_compatible_embedding_response_is_normalized(respx_mock):
    respx_mock.post("http://example.test/v1/embeddings").respond(
        json={"data": [{"embedding": [0.4, 0.5, 0.6]}]}
    )
    provider = EmbeddingProvider(
        name="openai-compatible",
        base_url="http://example.test/v1",
        model="text-embedding-3-small",
        api_format="openai",
        api_key="test-key",
    )

    assert provider.embed(["GCVM_L2_CNTL"]) == [[0.4, 0.5, 0.6]]
```

```python
# packages/core/tests/providers/test_semantic_edges.py
from asip.providers.semantic_edges import SemanticEdgeProvider


def test_semantic_edge_provider_uses_openai_compatible_chat_shape(respx_mock):
    respx_mock.post("http://example.test/v1/chat/completions").respond(
        json={
            "choices": [
                {
                    "message": {
                        "content": '{"edges":[{"src":"GCVM_L2_CNTL","dst":"ENABLE_L2_CACHE","relation":"has_field","confidence":0.9}]}'
                    }
                }
            ]
        }
    )
    provider = SemanticEdgeProvider(
        name="openai-compatible",
        base_url="http://example.test/v1",
        model="small-local-compatible",
        api_format="openai",
        api_key="test-key",
    )

    result = provider.extract_edges("GCVM_L2_CNTL has field ENABLE_L2_CACHE")
    assert result[0].relation == "has_field"
    assert result[0].confidence == 0.9
```

- [ ] **Step 2: Run failing provider tests**

Run: `uv run pytest packages/core/tests/providers/test_embeddings.py packages/core/tests/providers/test_semantic_edges.py -q`
Expected: FAIL because providers are missing.

- [ ] **Step 3: Implement provider config and embedding client**

Create `configs/models/ollama-local.yaml`:

```yaml
name: ollama-local
api_format: ollama
base_url: http://localhost:11434
embedding:
  model: nomic-embed-text
  dimensions: 768
  keep_alive: 30s
semantic_edge:
  enabled: false
  model: qwen2.5:1.5b
  format: json
  num_ctx: 2048
  temperature: 0
  keep_alive: 0s
memory_policy:
  default_profile: low-memory
  unload_after_smoke: true
  optional_larger_embedding_model: qwen3-embedding:4b
  optional_larger_chat_model: qwen3.5:4b
```

Create `configs/models/openai-compatible.yaml`:

```yaml
name: openai-compatible
api_format: openai
base_url: ${OPENAI_COMPATIBLE_BASE_URL}
api_key_env: OPENAI_COMPATIBLE_API_KEY
embedding:
  model: text-embedding-3-small
semantic_edge:
  enabled: false
  model: ${OPENAI_COMPATIBLE_SMALL_MODEL}
```

`EmbeddingProvider.embed(texts: list[str]) -> list[list[float]]` must:

- Use Ollama `/api/embeddings` for `api_format: ollama`.
- Use OpenAI-compatible `/embeddings` for `api_format: openai`.
- Return the same normalized vector shape to retrieval code.

`SemanticEdgeProvider.extract_edges(text: str)` is optional in MVP retrieval but the provider abstraction must exist. It must:

- Use Ollama chat for `api_format: ollama`.
- Use OpenAI-compatible chat completions for `api_format: openai`.
- Return normalized edge candidates with `src`, `dst`, `relation`, and `confidence`.
- Be disabled by default unless a config profile enables semantic-edge extraction.

- [ ] **Step 4: Implement vector adapter contract**

`VectorStore` must expose:

```python
class VectorStore:
    def add(self, item_id: str, embedding: list[float]) -> None: ...
    def search(self, embedding: list[float], limit: int) -> list[tuple[str, float]]: ...
```

The first implementation uses `sqlite-vec`; tests may use a deterministic in-memory adapter that shares the same public contract.

Add one integration smoke test marked `requires_sqlite_vec` that instantiates the sqlite-vec-backed adapter against a temp SQLite database, inserts two vectors, and verifies nearest-neighbor ordering. If the extension is unavailable, the test must skip with a clear message instead of silently falling back to in-memory behavior.

- [ ] **Step 5: Verify and commit**

Run: `uv run pytest packages/core/tests/providers packages/core/tests/storage/test_vector.py -q`
Expected: PASS.

```bash
git add configs/models packages/core/src/asip/providers packages/core/src/asip/storage/vector.py packages/core/tests/providers packages/core/tests/storage/test_vector.py
git commit -m "feat: add model providers and vector adapter"
```

---

### Task 8: Indexing Pipeline And Hybrid Retrieval

**Files:**
- Create: `packages/core/src/asip/indexing/pipeline.py`
- Create: `packages/core/src/asip/retrieval/search.py`
- Create: `packages/core/src/asip/retrieval/ranking.py`
- Test: `packages/core/tests/integration/test_fixture_indexing.py`
- Test: `packages/core/tests/retrieval/test_hybrid_search.py`

- [ ] **Step 1: Write integration test**

```python
# packages/core/tests/integration/test_fixture_indexing.py
from pathlib import Path
from asip.indexing.pipeline import index_corpus
from asip.retrieval.search import HybridSearch
from asip.storage.db import connect, migrate


def test_fixture_corpus_indexes_and_searches(tmp_path):
    conn = connect(tmp_path / "asip.db")
    migrate(conn)
    index_corpus(conn, Path("configs/corpora/amd-mvp1.yaml"))

    results = HybridSearch(conn).search("regGCVM_L2_CNTL", limit=5)

    assert results
    assert results[0].symbol in {"GCVM_L2_CNTL", "regGCVM_L2_CNTL"}
    assert results[0].resolved_chain


def test_pdf_chunks_enter_same_evidence_pipeline(tmp_path):
    conn = connect(tmp_path / "asip.db")
    migrate(conn)
    index_corpus(conn, Path("configs/corpora/amd-mvp1.yaml"))

    rows = conn.execute(
        "select source_type, page, symbol from evidence_items where source_type = 'pdf'"
    ).fetchall()

    assert rows
    assert rows[0]["page"] == 1
    assert "GCVM_L2_CNTL" in rows[0]["symbol"]
```

- [ ] **Step 2: Run failing indexing test**

Run: `uv run pytest packages/core/tests/integration/test_fixture_indexing.py -q`
Expected: FAIL because indexing and retrieval modules are missing.

- [ ] **Step 3: Implement indexing**

`index_corpus(conn, config_path)` must:

- Load corpus config.
- Ingest fixture code, docs, PDF pages, and register headers.
- Run resolver profiles configured per source.
- Insert documents, chunks, entities, edges, evidence items, FTS rows, and vector rows.
- Preserve PDF `source_type`, page, section, and evidence linkage in the same tables used for docs/code/register evidence.
- Record indexing job status as `completed` or `failed`.

- [ ] **Step 4: Implement hybrid retrieval**

`HybridSearch.search(query, limit)` must merge:

- Exact symbol match.
- FTS5 match.
- VectorStore match.
- 1-hop graph expansion.

Ranking order:

```text
exact symbol hit + resolved evidence > field/register edge > FTS match > vector-only match
```

- [ ] **Step 5: Verify and commit**

Run: `uv run pytest packages/core/tests/integration/test_fixture_indexing.py packages/core/tests/retrieval -q`
Expected: PASS.

```bash
git add packages/core/src/asip/indexing packages/core/src/asip/retrieval packages/core/tests/integration packages/core/tests/retrieval
git commit -m "feat: index fixtures and run hybrid retrieval"
```

---

### Task 9: Graph Store And NetworkX Runtime

**Files:**
- Create: `packages/core/src/asip/graph/store.py`
- Create: `packages/core/src/asip/graph/runtime.py`
- Test: `packages/core/tests/graph/test_graph_runtime.py`

- [ ] **Step 1: Write graph runtime test**

```python
# packages/core/tests/graph/test_graph_runtime.py
from asip.graph.runtime import load_graph, neighborhood
from asip.storage.db import connect, migrate


def test_networkx_neighborhood_from_sqlite(tmp_path):
    conn = connect(tmp_path / "asip.db")
    migrate(conn)
    conn.execute("insert into entities(id, type, name, canonical_name, repo, metadata) values ('r1', 'register', 'GCVM_L2_CNTL', 'GCVM_L2_CNTL', 'linux', '{}')")
    conn.execute("insert into entities(id, type, name, canonical_name, repo, metadata) values ('f1', 'field', 'ENABLE_L2_CACHE', 'GCVM_L2_CNTL.ENABLE_L2_CACHE', 'linux', '{}')")
    conn.execute("insert into edges(id, src_entity_id, dst_entity_id, relation_type, confidence, evidence_id, metadata) values ('e1', 'r1', 'f1', 'has_field', 1.0, null, '{}')")
    conn.commit()

    graph = load_graph(conn)
    result = neighborhood(graph, "r1", hops=1)

    assert result.nodes["r1"]["type"] == "register"
    assert ("r1", "f1") in result.edges
```

- [ ] **Step 2: Run failing graph test**

Run: `uv run pytest packages/core/tests/graph/test_graph_runtime.py -q`
Expected: FAIL because graph modules are missing.

- [ ] **Step 3: Implement SQLite graph loading**

`load_graph(conn)` must:

- Read `entities` into NetworkX nodes.
- Read `edges` into directed NetworkX edges.
- Preserve `relation_type`, `confidence`, `evidence_id`, and metadata.

- [ ] **Step 4: Implement bounded neighborhood**

`neighborhood(graph, entity_id, hops)` must return a directed subgraph containing nodes reachable within the requested hop count.

- [ ] **Step 5: Verify and commit**

Run: `uv run pytest packages/core/tests/graph/test_graph_runtime.py -q`
Expected: PASS.

```bash
git add packages/core/src/asip/graph packages/core/tests/graph
git commit -m "feat: load ASIP graph with networkx"
```

---

### Task 10: FastAPI Service

**Files:**
- Create: `apps/api/src/asip_api/main.py`
- Create: `apps/api/tests/test_api.py`
- Modify: `apps/api/pyproject.toml`

- [ ] **Step 1: Write API tests**

```python
# apps/api/tests/test_api.py
from fastapi.testclient import TestClient
from asip_api.main import app


def test_query_endpoint_returns_evidence_schema():
    client = TestClient(app)
    response = client.post("/query", json={"query": "regGCVM_L2_CNTL", "limit": 5})

    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert {"symbol", "source_type", "snippet", "resolved_chain"}.issubset(body["items"][0])


def test_provider_status_endpoint():
    client = TestClient(app)
    response = client.get("/providers/status")

    assert response.status_code == 200
    assert response.json()["default_profile"] == "ollama-local"
```

- [ ] **Step 2: Run failing API tests**

Run: `uv run pytest apps/api/tests/test_api.py -q`
Expected: FAIL because API app is missing.

- [ ] **Step 3: Implement API routes**

Implement:

- `POST /corpora/index`
- `POST /query`
- `GET /evidence/{evidence_id}`
- `GET /entities/{entity_id}`
- `GET /graph/neighborhood`
- `POST /resolver/validate`
- `GET /providers/status`
- `POST /acceptance/run`

Each route must call `packages/core` functions rather than duplicating core logic.

- [ ] **Step 4: Verify and commit**

Run: `uv run pytest apps/api/tests/test_api.py -q`
Expected: PASS.

```bash
git add apps/api
git commit -m "feat: expose ASIP FastAPI endpoints"
```

---

### Task 11: MCP Server

**Files:**
- Create: `apps/mcp/src/asip_mcp/server.py`
- Create: `apps/mcp/tests/test_mcp_tools.py`
- Modify: `apps/mcp/pyproject.toml`

- [ ] **Step 1: Write MCP tool tests**

```python
# apps/mcp/tests/test_mcp_tools.py
from asip_mcp.server import tool_names


def test_mcp_exposes_required_tools():
    assert {
        "search_evidence",
        "explain_symbol",
        "get_resolved_chain",
        "expand_graph_neighborhood",
        "inspect_resolver_profile",
        "run_acceptance_query",
    }.issubset(set(tool_names()))
```

- [ ] **Step 2: Run failing MCP tests**

Run: `uv run pytest apps/mcp/tests/test_mcp_tools.py -q`
Expected: FAIL because MCP server is missing.

- [ ] **Step 3: Implement MCP tools**

Each tool must return structured JSON-compatible values:

- `search_evidence(query, limit)`
- `explain_symbol(symbol)`
- `get_resolved_chain(evidence_id)`
- `expand_graph_neighborhood(entity_id, hops)`
- `inspect_resolver_profile(profile_name)`
- `run_acceptance_query(query_id)`

- [ ] **Step 4: Verify and commit**

Run: `uv run pytest apps/mcp/tests/test_mcp_tools.py -q`
Expected: PASS.

```bash
git add apps/mcp
git commit -m "feat: expose ASIP MCP tools"
```

---

### Task 12: Web UI Shell, Theme, And shadcn Components

**Files:**
- Create: `apps/web/app/layout.tsx`
- Create: `apps/web/app/page.tsx`
- Create: `apps/web/app/globals.css`
- Create: `apps/web/components/workbench-shell.tsx`
- Create: `apps/web/components/evidence-list.tsx`
- Create: `apps/web/components/evidence-inspector.tsx`
- Create: `apps/web/components/top-status-bar.tsx`
- Create: `apps/web/components/left-rail.tsx`
- Create: `apps/web/components/ui/*` through the shadcn CLI
- Test: `apps/web/tests/workbench.spec.ts`
- Test: `apps/web/tests/responsive.spec.ts`
- Test: `apps/web/tests/visual-constraints.spec.ts`

- [ ] **Step 1: Write Playwright smoke test**

```ts
// apps/web/tests/workbench.spec.ts
import { test, expect } from "@playwright/test";

test("first screen is the evidence workbench", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("navigation", { name: "ASIP sections" })).toBeVisible();
  await expect(page.getByRole("searchbox", { name: "Global symbol search" })).toBeVisible();
  await expect(page.getByText("Evidence Search")).toBeVisible();
  await expect(page.getByText("Resolved Chain")).toBeVisible();
});
```

```ts
// apps/web/tests/responsive.spec.ts
import { test, expect } from "@playwright/test";

test("workbench remains usable on laptop and narrow widths", async ({ page }) => {
  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport);
    await page.goto("/");
    await expect(page.getByRole("searchbox", { name: "Global symbol search" })).toBeVisible();
    await expect(page.getByText("Evidence Search")).toBeVisible();
    await expect(page.getByText("Resolved Chain")).toBeVisible();
  }
});
```

```ts
// apps/web/tests/visual-constraints.spec.ts
import { test, expect } from "@playwright/test";

test("visual rules stay evidence-workbench focused", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("[data-testid='marketing-hero']")).toHaveCount(0);
  await expect(page.locator("[data-testid='source-code-indicator']").first()).toBeVisible();
  await expect(page.locator("[data-testid='source-register-indicator']").first()).toBeVisible();
  await expect(page.locator("[data-testid='relationship-panel']")).toBeVisible();
  await expect(page.locator("[data-testid='graph-canvas']")).toHaveCount(0);
});
```

- [ ] **Step 2: Run failing UI smoke test**

Run: `pnpm --filter @graph-impact/web test`
Expected: FAIL because the app shell is missing.

- [ ] **Step 3: Add shadcn-compatible theme tokens**

Initialize shadcn in `apps/web` and generate the required primitives:

```bash
cd apps/web
pnpm dlx shadcn@latest init --yes
pnpm dlx shadcn@latest add button input select badge tabs table scroll-area separator tooltip toggle-group sheet dialog skeleton sidebar command
```

Map ASIP colors to CSS variables in `apps/web/app/globals.css`. Components must use semantic variables such as `background`, `foreground`, `border`, `primary`, `muted`, and local source-type token variables.

```css
:root {
  --background: #080a0b;
  --foreground: #f3f7f8;
  --card: #0f1214;
  --card-foreground: #f3f7f8;
  --popover: #151a1d;
  --popover-foreground: #f3f7f8;
  --primary: #39d98a;
  --primary-foreground: #080a0b;
  --secondary: #151a1d;
  --secondary-foreground: #f3f7f8;
  --muted: #1b2226;
  --muted-foreground: #aab6bc;
  --accent: #10b981;
  --accent-foreground: #080a0b;
  --destructive: #ef4444;
  --destructive-foreground: #f3f7f8;
  --border: #263036;
  --input: #39464d;
  --ring: #39d98a;
  --source-code: #7dd3fc;
  --source-register: #facc15;
  --source-doc: #c084fc;
  --source-pdf: #fb7185;
  --graph-edge: #60a5fa;
}
```

UI implementation rules:

- Use shadcn `Sidebar` for the left rail, `Command` or `Input` for search, `Select` for corpus selection, `Badge` for source/access/provider status, `ToggleGroup` for filters, `Table` for evidence rows, `ScrollArea` for long panes, `Tabs` for inspector subviews, `Sheet` or `Dialog` for focused source preview, `Tooltip` for icon-only controls, and `Separator` for dense panel boundaries.
- Use lucide icons inside icon buttons.
- Use `gap-*` spacing utilities rather than `space-*`.
- Do not use raw Tailwind color classes such as `bg-green-500`; use semantic tokens or the ASIP source variables.
- Do not create custom badge/span primitives when a shadcn component exists.
- Do not create a marketing hero, large gradient, decorative blob, large source-type fill, or full graph canvas for MVP-1.
- Source colors are only small indicators: dots, thin borders, or compact badges.

- [ ] **Step 4: Build the workbench shell**

The first page must render:

- Top bar with corpus selector, global search, provider status, and indexing status.
- Left rail with Evidence Search, Graph Explorer, Corpus, Resolver Profiles, Acceptance Tests, and Settings.
- Center pane with query composer, filters, and grouped evidence rows.
- Right inspector with selected evidence detail, resolved chain, fields, related entities, source preview, and relationship panel.

The relationship panel must be bounded inside the right inspector with `data-testid="relationship-panel"`. A full graph canvas with `data-testid="graph-canvas"` must not be present in MVP-1.

- [ ] **Step 5: Verify and commit**

Run: `pnpm --filter @graph-impact/web test`
Expected: PASS.

```bash
git add apps/web
git commit -m "feat: add ASIP web workbench shell"
```

---

### Task 13: Web UI Data Flow And Interaction States

**Files:**
- Create: `apps/web/lib/api.ts`
- Create: `apps/web/lib/mock-data.ts`
- Modify: `apps/web/components/evidence-list.tsx`
- Modify: `apps/web/components/evidence-inspector.tsx`
- Modify: `apps/web/components/workbench-shell.tsx`
- Test: `apps/web/tests/evidence-flow.spec.ts`

- [ ] **Step 1: Write interaction test**

```ts
// apps/web/tests/evidence-flow.spec.ts
import { test, expect } from "@playwright/test";

test("selecting evidence updates inspector", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("searchbox", { name: "Global symbol search" }).fill("GCVM_L2_CNTL");
  await page.getByRole("button", { name: "Run query" }).click();
  await page.getByRole("row", { name: /GCVM_L2_CNTL/ }).first().click();

  await expect(page.getByText("WREG32_SOC15")).toBeVisible();
  await expect(page.getByText("ENABLE_L2_CACHE")).toBeVisible();
});
```

- [ ] **Step 2: Run failing interaction test**

Run: `pnpm --filter @graph-impact/web test apps/web/tests/evidence-flow.spec.ts`
Expected: FAIL because interaction state is missing.

- [ ] **Step 3: Implement API client and mock fallback**

`apps/web/lib/api.ts` must expose:

```ts
export async function searchEvidence(query: string): Promise<EvidenceItem[]>;
export async function getEvidence(id: string): Promise<EvidenceItem>;
export async function getGraphNeighborhood(entityId: string): Promise<GraphNeighborhood>;
export async function getProviderStatus(): Promise<ProviderStatus>;
```

Use `apps/web/lib/mock-data.ts` when `NEXT_PUBLIC_ASIP_API_BASE_URL` is not set.

- [ ] **Step 4: Wire interaction state**

The workbench must keep:

- Current query.
- Source type filters.
- Selected evidence item.
- Provider/indexing status.
- Relationship panel data.

- [ ] **Step 5: Verify and commit**

Run: `pnpm --filter @graph-impact/web test apps/web/tests/evidence-flow.spec.ts`
Expected: PASS.

```bash
git add apps/web
git commit -m "feat: connect ASIP web evidence flow"
```

---

### Task 14: Acceptance Runner

**Files:**
- Create: `packages/core/src/asip/acceptance/queries.py`
- Create: `packages/core/src/asip/acceptance/runner.py`
- Create: `packages/core/tests/acceptance/test_queries.py`
- Modify: `apps/api/src/asip_api/main.py`
- Modify: `apps/mcp/src/asip_mcp/server.py`

- [ ] **Step 1: Write acceptance tests**

```python
# packages/core/tests/acceptance/test_queries.py
import pytest
from asip.acceptance.queries import ACCEPTANCE_QUERIES
from asip.acceptance.runner import run_acceptance_query


def test_acceptance_query_set_has_nine_items():
    assert len(ACCEPTANCE_QUERIES) == 9


@pytest.mark.parametrize(
    ("query_id", "required_symbol", "required_message"),
    [
        ("reads-writes-gcvm-l2-cntl", "GCVM_L2_CNTL", "read/write evidence"),
        ("mxgpu-gcvm-l2-fields", "GCVM_L2_CNTL.ENABLE_L2_CACHE", "MxGPU field evidence"),
        ("ih-rb-cntl-fields", "IH_RB_CNTL", "field modification evidence"),
        ("sdma-queue-rb-cntl", "SDMA0_QUEUE0_RB_CNTL", "SDMA queue evidence"),
        ("amdgpu-doc-source-link", "amdgpu", "doc/source link evidence"),
        ("soc15-resolved-chain", "GCVM_L2_CNTL", "resolved chain evidence"),
        ("resolver-wrapper-config-change", "GCVM_L2_CNTL", "config-only wrapper evidence"),
        ("toy-python-profile", "GCVM_L2_CNTL", "non-macro resolver evidence"),
        ("provider-switching", "ollama-local", "provider switching evidence"),
    ],
)
def test_each_acceptance_query_asserts_behavior(fixture_index, query_id, required_symbol, required_message):
    result = run_acceptance_query(fixture_index.conn, query_id)

    assert result.passed
    assert required_message in result.message
    assert any(required_symbol in item.symbol or required_symbol in item.snippet for item in result.evidence)


def test_resolved_chain_acceptance_has_macro_expansion(fixture_index):
    result = run_acceptance_query(fixture_index.conn, "soc15-resolved-chain")

    assert any("WREG32_SOC15" in " ".join(item.resolved_chain) for item in result.evidence)
    assert any("regGCVM_L2_CNTL_BASE_IDX" in " ".join(item.resolved_chain) for item in result.evidence)
```

- [ ] **Step 2: Run failing acceptance tests**

Run: `uv run pytest packages/core/tests/acceptance/test_queries.py -q`
Expected: FAIL because acceptance runner is missing.

- [ ] **Step 3: Add nine acceptance query definitions**

Use these stable IDs:

```text
reads-writes-gcvm-l2-cntl
mxgpu-gcvm-l2-fields
ih-rb-cntl-fields
sdma-queue-rb-cntl
amdgpu-doc-source-link
soc15-resolved-chain
resolver-wrapper-config-change
toy-python-profile
provider-switching
```

- [ ] **Step 4: Expose acceptance runner through API and MCP**

FastAPI route: `POST /acceptance/run`

MCP tool: `run_acceptance_query`

Both return:

```json
{
  "query_id": "reads-writes-gcvm-l2-cntl",
  "passed": true,
  "evidence": [],
  "message": "matched register evidence with resolved chain"
}
```

- [ ] **Step 5: Verify and commit**

Run: `uv run pytest packages/core/tests/acceptance apps/api/tests apps/mcp/tests -q`
Expected: PASS.

```bash
git add packages/core/src/asip/acceptance packages/core/tests/acceptance apps/api apps/mcp
git commit -m "feat: add ASIP acceptance runner"
```

---

### Task 15: Real Corpus Smoke Path

**Files:**
- Create: `configs/corpora/amd-real-smoke.yaml`
- Create: `packages/core/src/asip/cli.py`
- Create: `docs/runbooks/asip-real-corpus-smoke.md`
- Test: `packages/core/tests/integration/test_cli_index.py`

- [ ] **Step 1: Write CLI smoke test**

```python
# packages/core/tests/integration/test_cli_index.py
from pathlib import Path
from asip.cli import main


def test_cli_indexes_fixture_corpus(tmp_path):
    db_path = tmp_path / "asip.db"
    exit_code = main([
        "index",
        "--config",
        "configs/corpora/amd-mvp1.yaml",
        "--db",
        str(db_path),
    ])

    assert exit_code == 0
    assert db_path.exists()
```

- [ ] **Step 2: Run failing CLI test**

Run: `uv run pytest packages/core/tests/integration/test_cli_index.py -q`
Expected: FAIL because CLI is missing.

- [ ] **Step 3: Implement CLI**

`asip.cli` must support:

```text
asip index --config configs/corpora/amd-mvp1.yaml --db data/asip.db
asip query --db data/asip.db --query regGCVM_L2_CNTL --limit 5
asip acceptance --db data/asip.db --query-id reads-writes-gcvm-l2-cntl
```

- [ ] **Step 4: Add real corpus config and runbook**

`configs/corpora/amd-real-smoke.yaml` must point to local checkout paths supplied by the developer:

```yaml
name: amd-real-smoke
sources:
  - name: linux-amdgpu
    kind: code
    repo: linux
    path: data/corpora/linux/drivers/gpu/drm/amd/amdgpu
  - name: mxgpu
    kind: code
    repo: amd-mxgpu
    path: data/corpora/MxGPU-Virtualization
  - name: linux-amdgpu-doc
    kind: docs
    repo: linux
    path: data/corpora/linux/Documentation/gpu/amdgpu.rst
  - name: mxgpu-docs
    kind: docs
    repo: amd-mxgpu
    path: data/corpora/MxGPU-Virtualization
    include:
      - README.md
      - docs/**/*.md
  - name: linux-amdgpu-register-headers
    kind: register_headers
    repo: linux
    path: data/corpora/linux/drivers/gpu/drm/amd/include/asic_reg
    include:
      - "**/*_offset.h"
      - "**/*_d.h"
      - "**/*_sh_mask.h"
      - "**/*_default.h"
  - name: amd-pdf
    kind: pdf
    repo: amd-docs
    path: data/corpora/docs/amd-instinct-mi300-cdna3-instruction-set-architecture.pdf
```

Runbook commands:

```bash
mkdir -p data/corpora/docs
git clone --depth 1 https://github.com/torvalds/linux data/corpora/linux
git clone --depth 1 https://github.com/amd/MxGPU-Virtualization data/corpora/MxGPU-Virtualization
curl -L -o data/corpora/docs/amd-instinct-mi300-cdna3-instruction-set-architecture.pdf https://www.amd.com/content/dam/amd/en/documents/instinct-tech-docs/instruction-set-architectures/amd-instinct-mi300-cdna3-instruction-set-architecture.pdf
uv run python -m asip.cli index --config configs/corpora/amd-real-smoke.yaml --db data/asip-real-smoke.db
```

- [ ] **Step 5: Verify and commit**

Run: `uv run pytest packages/core/tests/integration/test_cli_index.py -q`
Expected: PASS.

```bash
git add configs/corpora/amd-real-smoke.yaml packages/core/src/asip/cli.py packages/core/tests/integration/test_cli_index.py docs/runbooks/asip-real-corpus-smoke.md
git commit -m "feat: document real AMD corpus smoke path"
```

---

### Task 16: Browser-Controlled QA And Ollama Smoke Verification

**Files:**
- Create: `docs/qa/asip-workbench-design-preview.html`
- Create: `docs/qa/2026-05-16-asip-browser-and-ollama-qa.md`
- Create: `apps/web/tests/browser-real-qa.spec.ts`
- Test: `apps/web/tests/browser-real-qa.spec.ts`

- [ ] **Step 1: Write browser QA test before implementation**

```ts
// apps/web/tests/browser-real-qa.spec.ts
import { test, expect } from "@playwright/test";

test("real browser QA validates workbench layout and constraints", async ({ page }) => {
  await page.goto("/");
  await page.setViewportSize({ width: 1440, height: 900 });
  await expect(page.getByRole("navigation", { name: "ASIP sections" })).toBeVisible();
  await expect(page.getByRole("searchbox", { name: "Global symbol search" })).toBeVisible();
  await expect(page.locator("[data-testid='relationship-panel']")).toBeVisible();
  await expect(page.locator("[data-testid='marketing-hero']")).toHaveCount(0);

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("searchbox", { name: "Global symbol search" })).toBeVisible();
  await expect(page.getByText("Resolved Chain")).toBeVisible();
});
```

- [ ] **Step 2: Run the failing browser QA test**

Run: `pnpm --filter @graph-impact/web test apps/web/tests/browser-real-qa.spec.ts`
Expected: FAIL until the real Next.js workbench is implemented.

- [ ] **Step 3: Verify local Ollama low-memory models**

Run:

```bash
ollama pull nomic-embed-text
ollama pull qwen2.5:1.5b
curl -s http://localhost:11434/api/embeddings \
  -d '{"model":"nomic-embed-text","prompt":"GCVM_L2_CNTL register field evidence"}'
curl -s http://localhost:11434/api/chat \
  -d '{"model":"qwen2.5:1.5b","stream":false,"format":"json","keep_alive":"0s","options":{"num_ctx":2048,"temperature":0},"messages":[{"role":"system","content":"Return only valid JSON. Schema: {\"edges\":[{\"src\":string,\"dst\":string,\"relation\":string,\"confidence\":number}]}"},{"role":"user","content":"Extract one semantic edge from: GCVM_L2_CNTL has field ENABLE_L2_CACHE."}]}'
ollama stop nomic-embed-text || true
ollama stop qwen2.5:1.5b || true
ollama ps
```

Expected:

```text
nomic-embed-text returns a 768-dimensional embedding.
qwen2.5:1.5b returns valid JSON with one edge.
ollama ps is empty after stop commands.
```

- [ ] **Step 4: Run real browser-controlled QA**

After the app exists, run browser control against the real local app:

```bash
just web
```

Open the local app in a controlled browser and verify:

- Desktop viewport `1440x900`.
- Narrow viewport `390x844`.
- Workbench first screen, not landing page.
- Left rail, global search, evidence rows, right inspector, relationship panel.
- Provider/index status visible.
- Source-type colors are small indicators.
- No text overflow in evidence rows or compact buttons.

Save QA notes in `docs/qa/YYYY-MM-DD-asip-browser-qa.md`.

- [ ] **Step 5: Verify and commit**

Run: `pnpm --filter @graph-impact/web test apps/web/tests/browser-real-qa.spec.ts`
Expected: PASS after Task 12 and Task 13 are implemented.

```bash
git add docs/qa apps/web/tests/browser-real-qa.spec.ts
git commit -m "test: add browser-controlled ASIP QA"
```

---

## Final Verification

Run:

```bash
just setup
just test
just lint
```

Expected:

```text
Python tests pass.
Playwright tests pass.
Next.js build passes.
Python compile check passes.
```

Run fixture acceptance:

```bash
for query_id in \
  reads-writes-gcvm-l2-cntl \
  mxgpu-gcvm-l2-fields \
  ih-rb-cntl-fields \
  sdma-queue-rb-cntl \
  amdgpu-doc-source-link \
  soc15-resolved-chain \
  resolver-wrapper-config-change \
  toy-python-profile \
  provider-switching
do
  uv run python -m asip.cli acceptance --db data/asip.db --query-id "$query_id"
done
```

Expected:

```text
Each acceptance query reports passed=true and includes its required evidence or provider-switching proof.
```

## Spec Coverage Checklist

- Real AMDGPU and MxGPU corpus support: Tasks 3, 8, 15
- Repo docs and PDF ingestion: Tasks 3, 6, 15
- Generated register headers: Task 4
- Configurable macro-aware resolver: Task 5
- Non-macro Python resolver proof: Task 5
- Evidence schema and resolved chains: Tasks 2, 5, 8
- SQLite, FTS5, sqlite-vec: Tasks 2, 7, 8
- NetworkX graph runtime: Task 9
- Ollama and OpenAI-compatible providers: Task 7
- FastAPI surface: Task 10
- MCP surface: Task 11
- Next.js + shadcn evidence workbench: Tasks 12, 13
- Nine acceptance tests: Task 14
- Real-corpus smoke path: Task 15
