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
    query: "",
    globalSymbol: "",
    workspaceLabel: "Evidence search workspace",
    composerIcon: GitBranch,
    filters: [
      { label: "Code", tone: "code", icon: Braces },
      { label: "Register", tone: "register", icon: Database },
      { label: "Doc", tone: "doc", icon: FileText },
      { label: "PDF", tone: "pdf", icon: FileText }
    ],
    metrics: [],
    rows: [],
    inspectorTitle: "Resolved Evidence",
    inspectorBadge: "live",
    chain: [],
    detailSections: [],
    relationshipLines: [],
    actionLabel: "Open resolver profile"
  },
  "graph-explorer": {
    id: "graph-explorer",
    navLabel: "Graph Explorer",
    route: "/graph",
    query: "",
    globalSymbol: "",
    workspaceLabel: "Graph relationship workspace",
    composerIcon: Network,
    filters: [
      { label: "1 hop", tone: "success", icon: Network },
      { label: "2 hops", tone: "code", icon: GitBranch },
      { label: "writes", tone: "register", icon: Braces },
      { label: "has_field", tone: "doc", icon: Database }
    ],
    metrics: [],
    rows: [],
    inspectorTitle: "Global Graph",
    inspectorBadge: "live",
    chain: [],
    detailSections: [],
    relationshipLines: [],
    actionLabel: "Generate semantic edges"
  },
  corpus: {
    id: "corpus",
    navLabel: "Corpus",
    route: "/corpus",
    query: "",
    globalSymbol: "",
    workspaceLabel: "Corpus management workspace",
    composerIcon: Database,
    filters: [
      { label: "code", tone: "code", icon: Braces },
      { label: "registers", tone: "register", icon: Database },
      { label: "docs", tone: "doc", icon: FileText },
      { label: "pdf", tone: "pdf", icon: FileText }
    ],
    metrics: [],
    rows: [],
    inspectorTitle: "Selected Corpus",
    inspectorBadge: "live",
    chain: [],
    detailSections: [],
    relationshipLines: [],
    actionLabel: "Run index"
  },
  "resolver-profiles": {
    id: "resolver-profiles",
    navLabel: "Resolver Profiles",
    route: "/resolver-profiles",
    query: "",
    globalSymbol: "",
    workspaceLabel: "Resolver profile workspace",
    composerIcon: SlidersHorizontal,
    filters: [
      { label: "cpp", tone: "code", icon: Braces },
      { label: "python", tone: "register", icon: Database },
      { label: "yaml", tone: "doc", icon: FileText },
      { label: "enabled", tone: "success", icon: CheckCircle2 }
    ],
    metrics: [],
    rows: [],
    inspectorTitle: "Resolved Wrapper Preview",
    inspectorBadge: "live",
    chain: [],
    detailSections: [],
    relationshipLines: [],
    actionLabel: "Validate profile"
  },
  "acceptance-tests": {
    id: "acceptance-tests",
    navLabel: "Acceptance Tests",
    route: "/acceptance",
    query: "",
    globalSymbol: "",
    workspaceLabel: "Acceptance test workspace",
    composerIcon: CheckCircle2,
    filters: [
      { label: "passed", tone: "success", icon: CheckCircle2 },
      { label: "failed", tone: "pdf", icon: XCircle },
      { label: "queries", tone: "code", icon: Activity },
      { label: "files", tone: "register", icon: Database }
    ],
    metrics: [],
    rows: [],
    inspectorTitle: "Acceptance Runs",
    inspectorBadge: "live",
    chain: [],
    detailSections: [],
    relationshipLines: [],
    actionLabel: "Open QA JSON"
  },
  settings: {
    id: "settings",
    navLabel: "Settings",
    route: "/settings",
    query: "",
    globalSymbol: "",
    workspaceLabel: "Settings workspace",
    composerIcon: Settings2,
    filters: [
      { label: "Ollama", tone: "success", icon: Activity },
      { label: "OpenAI compatible", tone: "doc", icon: Settings2 },
      { label: "sqlite-vec", tone: "register", icon: Database },
      { label: "NetworkX", tone: "code", icon: Network }
    ],
    metrics: [],
    rows: [],
    inspectorTitle: "Provider Validation",
    inspectorBadge: "live",
    chain: [],
    detailSections: [],
    relationshipLines: [],
    actionLabel: "Run provider smoke"
  }
};
