import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Braces,
  CheckCircle2,
  Database,
  FileText,
  GitBranch,
  Network,
  Settings2,
  SlidersHorizontal,
  XCircle
} from "lucide-react";

export type PageId =
  | "evidence-workbench"
  | "graph-explorer"
  | "corpus"
  | "resolver-profiles"
  | "acceptance-tests"
  | "settings";

export type SourceTone = "neutral" | "code" | "register" | "doc" | "pdf" | "success";

export type NavItem = {
  id: PageId;
  label: string;
  href: string;
};

export type Metric = {
  label: string;
  value: string;
  tone?: SourceTone;
};

export type EvidenceRow = {
  source: string;
  tone: SourceTone;
  symbol: string;
  relation: string;
  score: string;
  path: string;
  snippet?: string;
  resolved_chain?: string;
  source_type?: string;
  entity_type?: string;
  corpus_id?: string;
  line_start?: number;
  line_end?: number;
  page?: number;
};

export type PageConfig = {
  id: PageId;
  navLabel: string;
  route: string;
  query: string;
  globalSymbol: string;
  workspaceLabel: string;
  composerIcon: LucideIcon;
  filters: Array<{ label: string; tone: SourceTone; icon: LucideIcon }>;
  metrics: Metric[];
  rows: EvidenceRow[];
  inspectorTitle: string;
  inspectorBadge: string;
  chain: string[];
  detailSections: Array<{ title: string; body: string }>;
  relationshipLines: string[];
  actionLabel: string;
};

export const navItems: NavItem[] = [
  { id: "evidence-workbench", label: "Evidence Search", href: "/" },
  { id: "graph-explorer", label: "Graph Explorer", href: "/graph" },
  { id: "corpus", label: "Corpus", href: "/corpus" },
  { id: "resolver-profiles", label: "Resolver Profiles", href: "/resolver-profiles" },
  { id: "acceptance-tests", label: "Acceptance Tests", href: "/acceptance" },
  { id: "settings", label: "Settings", href: "/settings" }
];

export const pageConfigs: Record<PageId, PageConfig> = {
  "evidence-workbench": {
    id: "evidence-workbench",
    navLabel: "Evidence Search",
    route: "/",
    query: "Who writes regGCVM_L2_CNTL?",
    globalSymbol: "GCVM_L2_CNTL",
    workspaceLabel: "Evidence search workspace",
    composerIcon: GitBranch,
    filters: [
      { label: "Code", tone: "code", icon: Braces },
      { label: "Register", tone: "register", icon: Database },
      { label: "Doc", tone: "doc", icon: FileText },
      { label: "PDF", tone: "pdf", icon: FileText }
    ],
    metrics: [
      { label: "corpora", value: "2" },
      { label: "evidence", value: "3" },
      { label: "provider", value: "ollama", tone: "success" }
    ],
    rows: [
      {
        source: "code",
        tone: "code",
        symbol: "GCVM_L2_CNTL",
        relation: "write",
        score: "0.94",
        path: "drivers/gpu/drm/amd/amdgpu/gmc_v11_0.c:122"
      },
      {
        source: "register",
        tone: "register",
        symbol: "ENABLE_L2_CACHE",
        relation: "field_set",
        score: "0.91",
        path: "gc_11_0_0_sh_mask.h:44"
      },
      {
        source: "pdf",
        tone: "pdf",
        symbol: "GC VM",
        relation: "mention",
        score: "0.72",
        path: "amd-instinct-mi300-cdna3.pdf#page=1"
      }
    ],
    inspectorTitle: "Resolved Chain",
    inspectorBadge: "run 1",
    chain: [
      "WREG32_SOC15(GC, 0, regGCVM_L2_CNTL, tmp)",
      "adev->reg_offset[GC_HWIP][0][regGCVM_L2_CNTL_BASE_IDX] + regGCVM_L2_CNTL",
      "register GCVM_L2_CNTL"
    ],
    detailSections: [
      { title: "Register Fields", body: "GCVM_L2_CNTL.ENABLE_L2_CACHE" },
      { title: "Source Preview", body: "tmp = REG_SET_FIELD(tmp, GCVM_L2_CNTL, ENABLE_L2_CACHE, 1)" }
    ],
    relationshipLines: [
      "GCVM_L2_CNTL has_field ENABLE_L2_CACHE",
      "gmc_v11_0_init_golden_registers writes GCVM_L2_CNTL"
    ],
    actionLabel: "Open resolver profile"
  },
  "graph-explorer": {
    id: "graph-explorer",
    navLabel: "Graph Explorer",
    route: "/graph",
    query: "Expand GCVM_L2_CNTL by 2 hops",
    globalSymbol: "GCVM_L2_CNTL",
    workspaceLabel: "Graph relationship workspace",
    composerIcon: Network,
    filters: [
      { label: "1 hop", tone: "success", icon: Network },
      { label: "2 hops", tone: "code", icon: GitBranch },
      { label: "writes", tone: "register", icon: Braces },
      { label: "has_field", tone: "doc", icon: Database }
    ],
    metrics: [
      { label: "nodes", value: "87" },
      { label: "edges", value: "214" },
      { label: "threshold", value: "0.70" }
    ],
    rows: [
      {
        source: "edge",
        tone: "code",
        symbol: "gmc_v11_0_init_golden_registers",
        relation: "writes",
        score: "0.94",
        path: "gmc_v11_0.c:122"
      },
      {
        source: "edge",
        tone: "register",
        symbol: "GCVM_L2_CNTL",
        relation: "has_field",
        score: "0.91",
        path: "gc_11_0_0_sh_mask.h:44"
      },
      {
        source: "edge",
        tone: "doc",
        symbol: "GC IP",
        relation: "documents",
        score: "0.68",
        path: "Documentation/gpu/amdgpu.rst"
      }
    ],
    inspectorTitle: "Neighborhood: GCVM_L2_CNTL",
    inspectorBadge: "2 hops",
    chain: ["GCVM_L2_CNTL", "ENABLE_L2_CACHE", "gmc_v11_0_init_golden_registers", "GC HWIP"],
    detailSections: [
      { title: "Shortest Path", body: "gmc_v11_0_init_golden_registers -> GCVM_L2_CNTL -> ENABLE_L2_CACHE" },
      { title: "Provenance", body: "Every edge is backed by one source snippet or register header row." }
    ],
    relationshipLines: [
      "GCVM_L2_CNTL connects code, field, doc, and PDF evidence",
      "Weighted global graph emphasizes stronger evidence links"
    ],
    actionLabel: "Generate semantic edges"
  },
  corpus: {
    id: "corpus",
    navLabel: "Corpus",
    route: "/corpus",
    query: "Index AMD MVP-1 corpora",
    globalSymbol: "amd-mvp1",
    workspaceLabel: "Corpus management workspace",
    composerIcon: Database,
    filters: [
      { label: "code", tone: "code", icon: Braces },
      { label: "registers", tone: "register", icon: Database },
      { label: "docs", tone: "doc", icon: FileText },
      { label: "pdf", tone: "pdf", icon: FileText }
    ],
    metrics: [
      { label: "MxGPU files", value: "703", tone: "code" },
      { label: "amdgpu files", value: "625", tone: "code" },
      { label: "status", value: "ready", tone: "success" }
    ],
    rows: [
      {
        source: "code",
        tone: "code",
        symbol: "amd/MxGPU-Virtualization",
        relation: "commit",
        score: "f603f87",
        path: "/tmp/asip-mxgpu"
      },
      {
        source: "code",
        tone: "code",
        symbol: "linux amdgpu subtree",
        relation: "commit",
        score: "6916d57",
        path: "drivers/gpu/drm/amd/amdgpu"
      },
      {
        source: "pdf",
        tone: "pdf",
        symbol: "AMD MI300 CDNA3 ISA",
        relation: "candidate",
        score: "text",
        path: "amd-instinct-mi300-cdna3.pdf"
      }
    ],
    inspectorTitle: "Selected Corpus",
    inspectorBadge: "1328 files",
    chain: ["configs/corpora/amd-mvp1.yaml", "source roots", "SQLite FTS5", "sqlite-vec"],
    detailSections: [
      { title: "Include Patterns", body: "**/*.c, **/*.h, **/*.md, **/*.rst, **/*.pdf" },
      { title: "Index State", body: "Code scanned; PDF conversion is required before final MVP QA." }
    ],
    relationshipLines: ["MxGPU and Linux amdgpu feed the same evidence schema", "PDF text feeds documentation chunks"],
    actionLabel: "Run index"
  },
  "resolver-profiles": {
    id: "resolver-profiles",
    navLabel: "Resolver Profiles",
    route: "/resolver-profiles",
    query: "Show SOC15 wrapper expansion",
    globalSymbol: "WREG32_SOC15",
    workspaceLabel: "Resolver profile workspace",
    composerIcon: SlidersHorizontal,
    filters: [
      { label: "linux-amdgpu", tone: "code", icon: Braces },
      { label: "amd-mxgpu", tone: "register", icon: Database },
      { label: "toy-python", tone: "doc", icon: FileText },
      { label: "enabled", tone: "success", icon: CheckCircle2 }
    ],
    metrics: [
      { label: "profiles", value: "3" },
      { label: "wrappers", value: "config" },
      { label: "macro", value: "strategy" }
    ],
    rows: [
      {
        source: "profile",
        tone: "code",
        symbol: "WREG32_SOC15",
        relation: "wrapper",
        score: "linux",
        path: "configs/resolvers/linux-amdgpu.yaml"
      },
      {
        source: "profile",
        tone: "register",
        symbol: "adapt->reg_offset",
        relation: "base_expr",
        score: "mxgpu",
        path: "configs/resolvers/amd-mxgpu.yaml"
      },
      {
        source: "profile",
        tone: "doc",
        symbol: "decorator",
        relation: "future_rule",
        score: "python",
        path: "configs/resolvers/toy-python.yaml"
      }
    ],
    inspectorTitle: "Resolved Wrapper Preview",
    inspectorBadge: "config-only",
    chain: [
      "WREG32_SOC15(GC, 0, regGCVM_L2_CNTL, tmp)",
      "SOC15_REG_OFFSET(GC, 0, regGCVM_L2_CNTL)",
      "canonical register GCVM_L2_CNTL"
    ],
    detailSections: [
      { title: "Editable Rules", body: "Wrapper names, argument positions, prefixes, and device context vars are config-driven." },
      { title: "Non-Macro Future", body: "Profiles can describe Python calls, decorators, config keys, and schema references." }
    ],
    relationshipLines: ["linux-amdgpu and amd-mxgpu share resolver engine", "Strategy is selected by profile language"],
    actionLabel: "Validate profile"
  },
  "acceptance-tests": {
    id: "acceptance-tests",
    navLabel: "Acceptance Tests",
    route: "/acceptance",
    query: "Run qwen3.5 full-corpus semantic edge QA",
    globalSymbol: "qwen3.5 full-corpus",
    workspaceLabel: "Acceptance test workspace",
    composerIcon: CheckCircle2,
    filters: [
      { label: "passed 7", tone: "success", icon: CheckCircle2 },
      { label: "failed 2", tone: "pdf", icon: XCircle },
      { label: "queries 9", tone: "code", icon: Activity },
      { label: "files 1328", tone: "register", icon: Database }
    ],
    metrics: [
      { label: "passed", value: "7", tone: "success" },
      { label: "failed", value: "2", tone: "pdf" },
      { label: "duration", value: "95s" }
    ],
    rows: [
      {
        source: "pass",
        tone: "success",
        symbol: "mxgpu_gcvm_l2_cntl_fields",
        relation: "pass",
        score: "3 edges",
        path: "gfx_v11_0.c:322-330"
      },
      {
        source: "fail",
        tone: "pdf",
        symbol: "mxgpu_reg_offset_gc_base",
        relation: "missing",
        score: "0 edges",
        path: "mi200_reg_init.c:37-45"
      },
      {
        source: "pass",
        tone: "success",
        symbol: "linux_cp_int_cntl_ring0_fields",
        relation: "pass",
        score: "3 edges",
        path: "gfx_v10_0.c:5433-5441"
      }
    ],
    inspectorTitle: "qwen3.5 Edge Run",
    inspectorBadge: "7/9 pass",
    chain: ["full-corpus-qwen35.json", "MxGPU f603f87 + Linux 6916d57", "1328 C/H files", "9 real queries"],
    detailSections: [
      { title: "Failed Query Detail", body: "mxgpu_reg_offset_gc_base missed adapt->reg_offset, GC_HWIP, and GC_BASE." },
      { title: "Evidence File", body: "docs/qa/2026-05-16-full-corpus-edge-generation-qwen35.json" }
    ],
    relationshipLines: ["Generated edges are grounded in source snippets", "QA threshold requires more than five passing queries"],
    actionLabel: "Open QA JSON"
  },
  settings: {
    id: "settings",
    navLabel: "Settings",
    route: "/settings",
    query: "Validate provider settings",
    globalSymbol: "ollama-local",
    workspaceLabel: "Settings workspace",
    composerIcon: Settings2,
    filters: [
      { label: "Ollama", tone: "success", icon: Activity },
      { label: "OpenAI compatible", tone: "doc", icon: Settings2 },
      { label: "sqlite-vec", tone: "register", icon: Database },
      { label: "NetworkX", tone: "code", icon: Network }
    ],
    metrics: [
      { label: "edge model", value: "qwen3.5" },
      { label: "think", value: "off", tone: "success" },
      { label: "timeout", value: "900s" }
    ],
    rows: [
      {
        source: "provider",
        tone: "success",
        symbol: "qwen3.5:4b",
        relation: "semantic_edges",
        score: "local",
        path: "http://localhost:11434"
      },
      {
        source: "provider",
        tone: "register",
        symbol: "nomic-embed-text",
        relation: "embedding",
        score: "768d",
        path: "configs/models/ollama-local.yaml"
      },
      {
        source: "storage",
        tone: "code",
        symbol: "SQLite FTS5 + sqlite-vec",
        relation: "index",
        score: "local",
        path: "data/asip.db"
      }
    ],
    inspectorTitle: "Provider Validation",
    inspectorBadge: "ready",
    chain: ["Ollama API", "qwen3.5:4b", "think=false", "num_ctx=2048", "num_predict=1024"],
    detailSections: [
      { title: "Vector Backend", body: "sqlite-vec is the configured vector adapter behind SQLite storage." },
      { title: "Graph Runtime", body: "NetworkX loads persisted SQLite edges on demand for traversal." }
    ],
    relationshipLines: ["OpenAI-compatible providers share request shape", "Local models remain first-class defaults"],
    actionLabel: "Run provider smoke"
  }
};
