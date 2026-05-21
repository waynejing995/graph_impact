"use client";

import Image from "next/image";
import Link from "next/link";
import { Activity, Moon, Search, Sun } from "lucide-react";
import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ComponentProps,
  type CSSProperties,
  type FormEvent
} from "react";
import { WeightedForceGraph, type WeightedGraphNode, type WeightedGraphPayload } from "@/components/weighted-force-graph";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldGroup,
  FieldLabel
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { navItems, pageConfigs, type EvidenceRow, type Metric, type PageId, type SourceTone } from "@/lib/page-data";
import { cn } from "@/lib/utils";

type WorkbenchPageProps = {
  pageId: PageId;
};

const providerSettingsStorageKey = "asip-provider-settings";
const themeStorageKey = "asip-theme";
const defaultTheme = "dark";
const sourceFilterTypes = ["code", "register", "doc", "pdf"] as const;
const graphHopMin = 1;
const graphHopMax = 10;
const defaultGraphHopLevel = 3;
const defaultConceptRuleId = "custom-ip-versioned-functions";
const defaultConceptMatch = "^(?P<ip_block>gfxhub)_v(?P<ip_version>\\d+(?:_\\d+){0,2})_(?P<operation>.+)$";
const defaultConceptCanonical = "{ip_block}_{operation}";

type Theme = "dark" | "light";
type ProviderVerificationState = "unverified" | "verified" | "failed";

type ProviderSettings = {
  provider: "ollama" | "openai-compatible";
  apiBaseUrl: string;
  apiPath: string;
  edgeModel: string;
  fallbackModel: string;
  embeddingProvider: "ollama" | "openai-compatible";
  embeddingApiBaseUrl: string;
  embeddingApiPath: string;
  embeddingModel: string;
  embeddingExtraHeaders: Record<string, string>;
  timeoutSeconds: string;
  numCtx: string;
  numPredict: string;
  temperature: string;
  think: boolean;
  extraHeaders: Record<string, string>;
};

type ProviderSettingsDraft = Omit<ProviderSettings, "extraHeaders" | "embeddingExtraHeaders"> & {
  extraHeadersJson: string;
  embeddingExtraHeadersJson: string;
};

type RuntimeEdgeModelConfig = {
  provider: ProviderSettings["provider"];
  api_base_url: string;
  api_path: string;
  preferred: string;
  fallback: string;
  embedding_provider: ProviderSettings["embeddingProvider"];
  embedding_api_base_url: string;
  embedding_api_path: string;
  embedding_model: string;
  embedding_extra_headers: Record<string, string>;
  extra_headers: Record<string, string>;
  format: "json";
  num_ctx: number;
  num_predict: number;
  temperature: number;
  think: boolean;
  timeout_seconds: number;
};

type ProviderAcceptanceCheck = {
  status?: string;
  provider?: string;
  model?: string;
  message?: string;
};

type ProviderAcceptanceRun = {
  error?: string;
  queries?: Array<{
    id?: string;
    status?: string;
    provider_checks?: {
      embedding?: ProviderAcceptanceCheck;
      semantic_edge?: ProviderAcceptanceCheck;
    };
  }>;
};

type AcceptanceSurface = "CLI" | "API" | "Web" | "MCP";

type AcceptanceRunnerDraft = {
  dbPath: string;
  queryIds: string;
  surfaces: Record<AcceptanceSurface, boolean>;
  outputJson: string;
  outputMd: string;
};

type AcceptanceRunPayload = {
  source?: string;
  summary?: {
    total?: number;
    passed?: number;
    partial?: number;
    failed?: number;
  };
  surfaces_checked?: string[];
  queries?: Array<Partial<AcceptanceDetail> & Record<string, unknown>>;
  database_health?: Record<string, unknown>;
  output_json?: string;
  output_md?: string;
};

type BackendProviderSettings = {
  edge?: {
    provider?: string;
    base_url?: string;
    api_base_url?: string;
    api_path?: string;
    model?: string;
    preferred?: string;
    fallback_model?: string;
    fallback?: string;
    extra_headers?: Record<string, string>;
    think?: boolean;
    timeout_seconds?: number | string;
    num_ctx?: number | string;
    num_predict?: number | string;
    temperature?: number | string;
  };
  embedding?: {
    provider?: string;
    base_url?: string;
    api_base_url?: string;
    api_path?: string;
    model?: string;
    embedding_model?: string;
    extra_headers?: Record<string, string>;
  };
};

const defaultProviderSettings: ProviderSettings = {
  provider: "ollama",
  apiBaseUrl: "http://localhost:11434",
  apiPath: "/api/chat",
  edgeModel: "gemma4:e4b",
  fallbackModel: "",
  embeddingProvider: "ollama",
  embeddingApiBaseUrl: "http://localhost:11434",
  embeddingApiPath: "/api/embeddings",
  embeddingModel: "nomic-embed-text:latest",
  embeddingExtraHeaders: {},
  timeoutSeconds: "900",
  numCtx: "2048",
  numPredict: "1024",
  temperature: "0",
  think: false,
  extraHeaders: {}
};

const defaultAcceptanceRunnerDraft: AcceptanceRunnerDraft = {
  dbPath: "",
  queryIds: "AQ01, AQ09",
  surfaces: {
    CLI: true,
    API: true,
    Web: false,
    MCP: true
  },
  outputJson: "",
  outputMd: ""
};

type CorpusEntry = {
  id: string;
  repo: string;
  sourceRoot: string;
  include: string;
  subfolders: string;
  fileCount: string;
  status?: string;
};

type ApiCorpusEntry = {
  id: string;
  repo?: string;
  sourceRoot?: string;
  source_root?: string;
  include?: string[] | string;
  metadata?: Record<string, unknown>;
  fileCount?: number | string;
  file_count?: number | string;
  status?: string;
};

type ResolverProfile = {
  id: string;
  wrapper: string;
  wrappers: string[];
  strategy: string;
  path: string;
  enabled: boolean;
  functionNormalizationEnabled: boolean;
  conceptRuleId: string;
  conceptMatch: string;
  conceptCanonical: string;
};

type ApiResolverProfile = {
  id: string;
  language?: string;
  wrappers?: string[];
  path?: string;
  enabled?: boolean;
  config?: {
    graph?: {
      function_normalization?: {
        enabled?: boolean;
        rules?: Array<{
          id?: string;
          enabled?: boolean;
          match?: string;
          canonical?: string;
        }>;
      };
    };
  };
};

type AcceptanceRun = {
  id: string;
  model: string;
  passed: number;
  partial?: number;
  failed: number;
  queryCount: number;
  artifactPath: string;
  details?: AcceptanceDetail[];
  databaseHealth?: AcceptanceDetail[];
};

type AcceptanceDetail = {
  id: string;
  status: string;
  query?: string;
  failureReasons: string[];
  missing: string[];
  missingSurfaces: string[];
  sourcePaths: string[];
  sourceTypes: string[];
  rowCount?: number;
  graphEdgeCount?: number;
  edgeCount?: number;
  sourceHitCount?: number;
  retrievalSources?: string[];
  surfaceResults?: AcceptanceSurfaceResult[];
  providerChecks?: {
    embedding?: ProviderAcceptanceCheck;
    semanticEdge?: ProviderAcceptanceCheck;
  };
};

type AcceptanceSurfaceResult = {
  surface: string;
  transport: string;
  status: string;
  dbPath?: string;
  rowCount?: number;
  graphNodeCount?: number;
  graphEdgeCount?: number;
  message?: string;
};

type JobRun = {
  id: number;
  kind: string;
  status: string;
  message?: string;
  metadata?: Record<string, unknown>;
  events?: Array<{
    status?: string;
    message?: string;
    created_at?: string;
  }>;
};

type GraphPayload = WeightedGraphPayload;
type GraphFunctionView = "concept" | "implementation";
type GraphFilterGroup = "relation" | "stage" | "source";
type GraphFilterOption = {
  value: string;
  count: number;
};
type InspectorDetailSection = {
  title: string;
  body?: string;
  lines?: string[];
};

type WorkbenchLimits = {
  graph?: {
    edgeBudget?: number;
    maxEdgeBudget?: number;
    visibleNodeBudget?: number;
    visibleEdgeBudget?: number;
    minimumEdgeWeight?: number;
    evidenceRowCap?: number;
    inspectorEdgePreviewLimit?: number;
    accessibilitySummaryLimit?: number;
  };
  semantic?: {
    queryLimit?: number;
    batchCandidateLimit?: number;
    batchSize?: number;
  };
};

type ApiQueryResponse = {
  rows?: EvidenceRow[];
  graph?: GraphPayload;
  empty_state?: string;
  error?: string;
};

export function WorkbenchPage({ pageId }: WorkbenchPageProps) {
  const config = pageConfigs[pageId];
  const [query, setQuery] = useState(config.query);
  const queryValueRef = useRef(config.query);
  const [ipFilter, setIpFilter] = useState("");
  const [asicFilter, setAsicFilter] = useState("");
  const [runCount, setRunCount] = useState(1);
  const [theme, setTheme] = useState<Theme>(defaultTheme);
  const [themeReady, setThemeReady] = useState(false);
  const [providerSettings, setProviderSettings] = useState<ProviderSettings>(defaultProviderSettings);
  const [providerVerification, setProviderVerification] = useState<ProviderVerificationState>("unverified");
  const [workbenchLimits, setWorkbenchLimits] = useState<WorkbenchLimits>({});
  const [limitsReady, setLimitsReady] = useState(false);
  const [graphEdgeBudget, setGraphEdgeBudget] = useState<number | null>(null);
  const [graphHopLevel, setGraphHopLevel] = useState(defaultGraphHopLevel);
  const [graphFunctionView, setGraphFunctionView] = useState<GraphFunctionView>("concept");
  const providerSettingsDirtyRef = useRef(false);
  const initialSearchHandledRef = useRef(false);
  const graphQueryActiveRef = useRef(false);
  const queryInputRef = useRef<HTMLInputElement | null>(null);
  const queryRequestSeqRef = useRef(0);
  const [settingsDraft, setSettingsDraft] = useState<ProviderSettingsDraft>(
    settingsToDraft(defaultProviderSettings)
  );
  const [settingsMessage, setSettingsMessage] = useState("");
  const [settingsError, setSettingsError] = useState("");
  const [semanticLimitDraft, setSemanticLimitDraft] = useState("");
  const [semanticBatchSizeDraft, setSemanticBatchSizeDraft] = useState("");
  const [workbenchDbPath, setWorkbenchDbPath] = useState("");
  const [workbenchDbPathExplicit, setWorkbenchDbPathExplicit] = useState(false);
  const [workbenchDbPathReady, setWorkbenchDbPathReady] = useState(false);
  const [acceptanceDbPath, setAcceptanceDbPath] = useState("");
  const [acceptanceDbPathExplicit, setAcceptanceDbPathExplicit] = useState(false);
  const [acceptanceRunnerDraft, setAcceptanceRunnerDraft] = useState<AcceptanceRunnerDraft>(
    defaultAcceptanceRunnerDraft
  );
  const [acceptanceRunnerDbPathExplicit, setAcceptanceRunnerDbPathExplicit] = useState(false);
  const [corpora, setCorpora] = useState<CorpusEntry[]>([]);
  const [selectedCorpusIds, setSelectedCorpusIds] = useState<string[]>([]);
  const [corpusDraft, setCorpusDraft] = useState<CorpusEntry>({
    id: "",
    repo: "",
    sourceRoot: "",
    include: "**/*.c, **/*.h",
    subfolders: "",
    fileCount: "user"
  });
  const [corpusMessage, setCorpusMessage] = useState("");
  const [globalQuery, setGlobalQuery] = useState("");
  const [selectedSourceTypes, setSelectedSourceTypes] = useState<string[]>([...sourceFilterTypes]);
  const [resolverProfiles, setResolverProfiles] = useState<ResolverProfile[]>([]);
  const [selectedResolverProfileIds, setSelectedResolverProfileIds] = useState<string[]>([]);
  const resolverProfileSelectionTouchedRef = useRef(false);
  const [resolverDraft, setResolverDraft] = useState<ResolverProfile>({
    id: "initial",
    wrapper: "RREG32",
    wrappers: ["RREG32"],
    strategy: "macro",
    path: "configs/resolvers/initial.yaml",
    enabled: true,
    functionNormalizationEnabled: false,
    conceptRuleId: defaultConceptRuleId,
    conceptMatch: defaultConceptMatch,
    conceptCanonical: defaultConceptCanonical
  });
  const [resolverValidateSource, setResolverValidateSource] = useState("RREG32(mmASIP_INITIAL_STATUS);");
  const [resolverMessage, setResolverMessage] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [selectedEvidenceKey, setSelectedEvidenceKey] = useState("");
  const [apiQueryRows, setApiQueryRows] = useState<EvidenceRow[] | null>(
    config.id === "evidence-workbench" ? [] : null
  );
  const [apiGraph, setApiGraph] = useState<GraphPayload | null>(
    config.id === "evidence-workbench" || config.id === "graph-explorer" ? { nodes: [], edges: [] } : null
  );
  const [selectedGraphNodeId, setSelectedGraphNodeId] = useState("");
  const [graphEmptyMessage, setGraphEmptyMessage] = useState("");
  const [queryEmptyMessage, setQueryEmptyMessage] = useState(
    config.id === "evidence-workbench" ? "Enter a query to search live evidence." : ""
  );
  const [acceptanceRuns, setAcceptanceRuns] = useState<AcceptanceRun[]>([]);
  const [jobRuns, setJobRuns] = useState<JobRun[]>([]);

  useEffect(() => {
    const storedTheme = readStoredTheme();
    setTheme(storedTheme);
    document.documentElement.dataset.theme = storedTheme;
    setThemeReady(true);
  }, []);

  useEffect(() => {
    if (!themeReady) {
      return;
    }
    document.documentElement.dataset.theme = theme;
    writeStoredTheme(theme);
  }, [theme, themeReady]);

  useEffect(() => {
    setActionMessage("");
  }, [config.actionLabel]);

  useEffect(() => {
    const searchParams = new URLSearchParams(window.location.search);
    const dbPath = searchParams.get("dbPath") ?? "";
    const hasDbPath = searchParams.has("dbPath");
    setWorkbenchDbPathExplicit(hasDbPath);
    setWorkbenchDbPath(dbPath);
    const trimmedDbPath = dbPath.trim();
    if (hasDbPath) {
      setAcceptanceDbPathExplicit(true);
      setAcceptanceRunnerDbPathExplicit(true);
      setAcceptanceDbPath((current) => current || trimmedDbPath || dbPath);
      setAcceptanceRunnerDraft((draft) => (draft.dbPath ? draft : { ...draft, dbPath: trimmedDbPath || dbPath }));
    }
    setWorkbenchDbPathReady(true);
  }, []);

  useEffect(() => {
    if (!workbenchDbPathReady || config.id !== "evidence-workbench" || initialSearchHandledRef.current) {
      return;
    }
    const storedGlobalQuery = window.sessionStorage.getItem("asip-global-query")?.trim() ?? "";
    const initialQuery = new URLSearchParams(window.location.search).get("q")?.trim() || storedGlobalQuery;
    if (!initialQuery) {
      return;
    }
    initialSearchHandledRef.current = true;
    window.sessionStorage.removeItem("asip-global-query");
    setGlobalQuery(initialQuery);
    void runQuery(initialQuery);
  }, [config.id, workbenchDbPath, workbenchDbPathReady]);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/workbench/limits")
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Limits API returned ${response.status}`);
        }
        return response.json() as Promise<WorkbenchLimits>;
      })
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setWorkbenchLimits(payload);
        setGraphEdgeBudget((current) => current ?? payload.graph?.edgeBudget ?? null);
        setLimitsReady(true);
      })
      .catch(() => {
        if (!cancelled) {
          setLimitsReady(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (config.id !== "corpus" || !workbenchDbPathReady) {
      return;
    }
    let cancelled = false;
    fetchJobRuns().then((runs) => {
      if (!cancelled) {
        setJobRuns(runs);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [config.id, workbenchDbPath, workbenchDbPathReady]);

  useLayoutEffect(() => {
    if (!workbenchDbPathReady) {
      return;
    }
    const supportsInitialQuery = config.id === "evidence-workbench" || config.id === "graph-explorer";
    if (supportsInitialQuery && !initialSearchHandledRef.current) {
      const storedGlobalQuery = window.sessionStorage.getItem("asip-global-query")?.trim() ?? "";
      const initialQuery = new URLSearchParams(window.location.search).get("q")?.trim() || storedGlobalQuery;
      if (initialQuery) {
        initialSearchHandledRef.current = true;
        window.sessionStorage.removeItem("asip-global-query");
        setGlobalQuery(initialQuery);
        updateQuery(initialQuery);
        setQueryEmptyMessage("");
        void executeQuery(initialQuery, { announce: true, incrementRun: true });
        return;
      }
    }
    if (config.id === "evidence-workbench" && queryValueRef.current.trim()) {
      setQueryEmptyMessage("");
      return;
    }
    updateQuery(config.query);
    setQueryEmptyMessage(config.id === "evidence-workbench" ? "Enter a query to search live evidence." : "");
  }, [config.id, config.query, workbenchDbPath, workbenchDbPathReady]);

  useEffect(() => {
    if (!workbenchDbPathReady || config.id !== "evidence-workbench") {
      return;
    }
    if (config.query.trim()) {
      void executeQuery(config.query, { announce: false, incrementRun: false });
    }
  }, [config.id, config.query, workbenchDbPath, workbenchDbPathReady]);

  useEffect(() => {
    if (config.id !== "graph-explorer") {
      setApiGraph(null);
      return;
    }
    if (graphQueryActiveRef.current || queryValueRef.current.trim()) {
      return;
    }

    let cancelled = false;
    setGraphEmptyMessage("");
    if (!limitsReady || !workbenchDbPathReady) {
      return;
    }

    const params = new URLSearchParams();
    if (graphEdgeBudget !== null) {
      params.set("limit", String(graphEdgeBudget));
    }
    appendWorkbenchDbPath(params);
    params.set("hops", String(graphHopLevel));
    params.set("functionView", graphFunctionView);
    const queryString = params.toString();
    fetch(`/api/workbench/graph${queryString ? `?${queryString}` : ""}`)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Graph API returned ${response.status}`);
        }
        return response.json() as Promise<GraphPayload>;
      })
      .then((payload) => {
        if (!cancelled && !graphQueryActiveRef.current && !queryValueRef.current.trim()) {
          const graphPayload = sanitizeGraphPayload(payload) ?? { nodes: [], edges: [] };
          setApiGraph(graphPayload);
          setGraphEmptyMessage(graphPayload.nodes.length || graphPayload.edges.length ? "" : "No graph data returned.");
        }
      })
      .catch((error) => {
        if (!cancelled && !graphQueryActiveRef.current && !queryValueRef.current.trim()) {
          setApiGraph({ nodes: [], edges: [] });
          setGraphEmptyMessage(error instanceof Error ? error.message : "Graph failed");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [config.id, graphEdgeBudget, graphFunctionView, graphHopLevel, limitsReady, workbenchDbPath, workbenchDbPathExplicit, workbenchDbPathReady]);

  useEffect(() => {
    if (!workbenchDbPathReady) {
      return;
    }
    let cancelled = false;
    const applySettings = (next: ProviderSettings) => {
      if (cancelled) {
        return;
      }
      setProviderSettings(next);
      setSettingsDraft(settingsToDraft(next));
      setProviderVerification("unverified");
    };

    const params = new URLSearchParams();
    appendWorkbenchDbPath(params);
    fetch(`/api/workbench/providers/settings${params.toString() ? `?${params.toString()}` : ""}`)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Provider settings API returned ${response.status}`);
        }
        return response.json() as Promise<BackendProviderSettings>;
      })
      .then((payload) => {
        const backendSettings = providerSettingsFromBackend(payload);
        if (backendSettings && !cancelled && !providerSettingsDirtyRef.current) {
          applySettings(backendSettings);
          window.localStorage.setItem(providerSettingsStorageKey, JSON.stringify(backendSettings));
          setSettingsError("");
        }
      })
      .catch(() => {
        const stored = window.localStorage.getItem(providerSettingsStorageKey);
        if (!stored || cancelled) {
          return;
        }
        try {
          const parsed = JSON.parse(stored) as Partial<ProviderSettings>;
          applySettings(normalizeProviderSettings(parsed));
        } catch {
          setSettingsError("Stored provider settings are invalid JSON.");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [workbenchDbPath, workbenchDbPathExplicit, workbenchDbPathReady]);

  useEffect(() => {
    if (!workbenchDbPathReady) {
      return;
    }
    let cancelled = false;

    const params = new URLSearchParams();
    appendWorkbenchDbPath(params);
    fetch(`/api/workbench/resolver-profiles${params.toString() ? `?${params.toString()}` : ""}`)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Resolver API returned ${response.status}`);
        }
        return response.json() as Promise<{ profiles?: ApiResolverProfile[] }>;
      })
      .then((payload) => {
        if (!cancelled) {
          const apiProfiles = (payload.profiles ?? []).map(normalizeApiResolverProfile);
          setResolverProfiles((current) => mergeResolverProfiles(apiProfiles, current));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setResolverProfiles((current) => current);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [workbenchDbPath, workbenchDbPathExplicit, workbenchDbPathReady]);

  useEffect(() => {
    if (!workbenchDbPathReady) {
      return;
    }
    let cancelled = false;

    const params = new URLSearchParams();
    appendWorkbenchDbPath(params);
    fetch(`/api/workbench/corpora${params.toString() ? `?${params.toString()}` : ""}`)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Corpus API returned ${response.status}`);
        }
        return response.json() as Promise<{ corpora?: ApiCorpusEntry[] }>;
      })
      .then((payload) => {
        if (cancelled) {
          return;
        }
        const apiCorpora = (payload.corpora ?? []).map(normalizeApiCorpus);
        setCorpora(apiCorpora);
        setSelectedCorpusIds(apiCorpora.map((corpus) => corpus.id));
      })
      .catch(() => {
        if (!cancelled) {
          setCorpora([]);
          setSelectedCorpusIds([]);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [workbenchDbPath, workbenchDbPathExplicit, workbenchDbPathReady]);

  useEffect(() => {
    const enabledIds = resolverProfiles.filter((profile) => profile.enabled).map((profile) => profile.id);
    setSelectedResolverProfileIds((current) => {
      if (!resolverProfileSelectionTouchedRef.current) {
        return enabledIds;
      }
      return current.filter((id) => enabledIds.includes(id));
    });
  }, [resolverProfiles]);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/workbench/acceptance")
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Acceptance API returned ${response.status}`);
        }
        return response.json() as Promise<{ runs?: AcceptanceRun[] }>;
      })
      .then((payload) => {
        if (!cancelled) {
          setAcceptanceRuns((payload.runs ?? []).map(normalizeAcceptanceRun));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAcceptanceRuns([]);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const graphRouteHasAuthoritativeEmptyGraph =
    config.id === "graph-explorer" && apiGraph !== null && apiGraph.nodes.length === 0 && apiGraph.edges.length === 0;
  const queryEvidenceRows = useMemo(() => {
    if (apiQueryRows !== null) {
      return apiQueryRows;
    }
    if (graphRouteHasAuthoritativeEmptyGraph) {
      return [];
    }
    return [];
  }, [apiQueryRows, graphRouteHasAuthoritativeEmptyGraph]);
  const selectedEvidence = useMemo(() => {
    if (config.id !== "evidence-workbench" || !queryEvidenceRows.length) {
      return null;
    }
    return queryEvidenceRows.find((row) => evidenceRowKey(row) === selectedEvidenceKey) ?? queryEvidenceRows[0];
  }, [config.id, queryEvidenceRows, selectedEvidenceKey]);
  const selectedGraphNode = useMemo(() => {
    if (!apiGraph || !selectedGraphNodeId) {
      return null;
    }
    return apiGraph.nodes.find((node) => node.id === selectedGraphNodeId) ?? null;
  }, [apiGraph, selectedGraphNodeId]);
  useEffect(() => {
    if (!selectedGraphNodeId || !apiGraph) {
      return;
    }
    if (!apiGraph.nodes.some((node) => node.id === selectedGraphNodeId)) {
      setSelectedGraphNodeId("");
    }
  }, [apiGraph, selectedGraphNodeId]);
  const inspectorTitle = useMemo(() => {
    if (selectedGraphNode) {
      return `Graph Node: ${selectedGraphNode.label ?? selectedGraphNode.id}`;
    }
    if (selectedEvidence) {
      return `Resolved Evidence: ${selectedEvidence.symbol}`;
    }
    return config.inspectorTitle;
  }, [config.inspectorTitle, selectedEvidence, selectedGraphNode]);
  const inspectorChain = useMemo(
    () => {
      if (selectedGraphNode) {
        return buildGraphNodeInspectorChain(selectedGraphNode);
      }
      return selectedEvidence ? buildLiveInspectorChain(selectedEvidence) : [];
    },
    [selectedEvidence, selectedGraphNode]
  );
  const inspectorDetailSections = useMemo(
    () => {
      if (selectedGraphNode) {
        return buildGraphNodeInspectorSections(selectedGraphNode);
      }
      return selectedEvidence ? buildLiveInspectorSections(selectedEvidence) : [];
    },
    [selectedEvidence, selectedGraphNode]
  );
  const inspectorRelationshipLines = useMemo(
    () => {
      if (selectedGraphNode && apiGraph) {
        return buildSelectedNodeRelationshipLines(selectedGraphNode, apiGraph, workbenchLimits.graph?.inspectorEdgePreviewLimit);
      }
      if (selectedEvidence) {
        return buildLiveRelationshipLines(selectedEvidence, apiGraph);
      }
      if (config.id === "graph-explorer" && apiGraph) {
        return buildGraphRelationshipLines(apiGraph, graphEmptyMessage, workbenchLimits.graph?.inspectorEdgePreviewLimit);
      }
      return ["No relationship data returned from API."];
    },
    [apiGraph, config.id, graphEmptyMessage, selectedEvidence, selectedGraphNode, workbenchLimits.graph?.inspectorEdgePreviewLimit]
  );

  const providerLabel = providerSettings.provider === "ollama" ? "Ollama" : "OpenAI-compatible";
  const runtimeConfig = useMemo(() => buildRuntimeEdgeModelConfig(providerSettings), [providerSettings]);
  const indexStatusLabel = useMemo(() => buildIndexStatusLabel(corpora), [corpora]);
  const pageMetrics = useMemo(
    () =>
      buildPageMetrics(
        config.id,
        config.metrics,
        providerSettings,
        corpora,
        resolverProfiles,
        queryEvidenceRows,
        apiGraph,
        acceptanceRuns,
        providerVerification
      ),
    [config.id, config.metrics, providerSettings, corpora, resolverProfiles, queryEvidenceRows, apiGraph, acceptanceRuns, providerVerification]
  );
  const evidenceRows = useMemo(
    () =>
      buildPageRows(
        config.id,
        config.rows,
        providerSettings,
        corpora,
        resolverProfiles,
        queryEvidenceRows,
        acceptanceRuns
      ),
    [config.id, config.rows, providerSettings, corpora, resolverProfiles, queryEvidenceRows, acceptanceRuns]
  );

  async function runQuery(queryOverride?: string) {
    const nextQuery = (queryOverride ?? queryInputRef.current?.value ?? query).trim() || config.query;
    if (!nextQuery.trim()) {
      if (config.id === "graph-explorer") {
        graphQueryActiveRef.current = false;
      }
      setApiQueryRows([]);
      setSelectedEvidenceKey("");
      setApiGraph(config.id === "graph-explorer" ? apiGraph : { nodes: [], edges: [] });
      setQueryEmptyMessage("Enter a query to search live evidence.");
      if (config.id !== "graph-explorer") {
        setGraphEmptyMessage("");
      }
      return;
    }
    if (config.id === "graph-explorer") {
      graphQueryActiveRef.current = true;
    }
    updateQuery(nextQuery);
    await executeQuery(nextQuery, { announce: true, incrementRun: true });
  }

  function workbenchDbPathForRequest() {
    const trimmed = workbenchDbPath.trim();
    if (trimmed) {
      return trimmed;
    }
    return workbenchDbPathExplicit ? workbenchDbPath : undefined;
  }

  function workbenchDbPathPayload() {
    const dbPath = workbenchDbPathForRequest();
    return dbPath === undefined ? {} : { dbPath };
  }

  function dbPathInputPayload(value: string, explicit = false) {
    if (!value && !explicit) {
      return {};
    }
    const trimmed = value.trim();
    return { dbPath: trimmed || value };
  }

  function appendWorkbenchDbPath(params: URLSearchParams) {
    const dbPath = workbenchDbPathForRequest();
    if (dbPath !== undefined) {
      params.set("dbPath", dbPath);
    }
  }

  function updateQuery(nextQuery: string) {
    queryValueRef.current = nextQuery;
    setQuery(nextQuery);
  }

  function handleQuerySubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    void runQuery(String(formData.get("query") ?? ""));
  }

  function handleGlobalSearchSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextQuery = globalQuery.trim();
    if (!nextQuery) {
      return;
    }
    if (config.id === "evidence-workbench" || config.id === "graph-explorer") {
      void runQuery(nextQuery);
      return;
    }
    window.sessionStorage.setItem("asip-global-query", nextQuery);
    const params = new URLSearchParams({ q: nextQuery });
    appendWorkbenchDbPath(params);
    window.location.assign(`/?${params.toString()}`);
  }

  async function executeQuery(
    nextQuery: string,
    options: { announce: boolean; incrementRun: boolean }
  ) {
    const requestSeq = queryRequestSeqRef.current + 1;
    queryRequestSeqRef.current = requestSeq;
    if (options.incrementRun) {
      setRunCount((count) => count + 1);
    }
    setApiQueryRows([]);
    setSelectedEvidenceKey("");
    setApiGraph({ nodes: [], edges: [] });
    setGraphEmptyMessage("");
    setQueryEmptyMessage(`Loading live evidence for: ${nextQuery}`);
    try {
      const params = new URLSearchParams({ q: nextQuery });
      if (ipFilter.trim()) {
        params.set("ipBlock", ipFilter.trim());
      }
      if (asicFilter.trim()) {
        params.set("asic", asicFilter.trim());
      }
      if (selectedSourceTypes.length !== sourceFilterTypes.length) {
        params.set("sourceTypes", selectedSourceTypes.length ? selectedSourceTypes.join(",") : "__none__");
      }
      appendWorkbenchDbPath(params);
      params.set("hops", String(graphHopLevel));
      params.set("functionView", graphFunctionView);
      const response = await fetch(`/api/workbench/query?${params.toString()}`);
      if (!response.ok) {
        throw new Error(`Query API returned ${response.status}`);
      }
      const payload = (await response.json()) as ApiQueryResponse;
      if (queryRequestSeqRef.current !== requestSeq) {
        return;
      }
      if (Array.isArray(payload.rows)) {
        const normalizedRows = payload.rows.map(normalizeApiEvidenceRow);
        const graphPayload = sanitizeGraphPayload(payload.graph);
        setApiQueryRows(normalizedRows);
        setSelectedEvidenceKey(normalizedRows[0] ? evidenceRowKey(normalizedRows[0]) : "");
        setApiGraph(graphPayload);
        setQueryEmptyMessage(payload.rows.length ? "" : payload.empty_state ?? `No evidence matched query: ${nextQuery}`);
      } else {
        setApiQueryRows([]);
        setSelectedEvidenceKey("");
        setApiGraph({ nodes: [], edges: [] });
        setGraphEmptyMessage(payload.error ?? `No graph data returned for ${nextQuery}`);
        setQueryEmptyMessage(payload.error ?? `No evidence matched query: ${nextQuery}`);
      }
      if (options.announce) {
        setActionMessage(`Query ran: ${nextQuery}`);
      }
    } catch (error) {
      if (queryRequestSeqRef.current !== requestSeq) {
        return;
      }
      const errorMessage = error instanceof Error ? error.message : `Query failed: ${nextQuery}`;
      setApiQueryRows([]);
      setSelectedEvidenceKey("");
      setApiGraph({ nodes: [], edges: [] });
      setGraphEmptyMessage(errorMessage);
      setQueryEmptyMessage(errorMessage);
      if (options.announce) {
        setActionMessage(`Query failed: ${errorMessage}`);
      }
    }
  }

  async function runPageAction(options: { semanticMode?: "query" | "batch" | "doc-nodes" } = {}) {
    if (config.id === "corpus") {
      const selectedIds = selectedCorpusIds.filter((id) => corpora.some((corpus) => corpus.id === id));
      const enabledResolverIds = resolverProfiles.filter((profile) => profile.enabled).map((profile) => profile.id);
      const selectedResolverIds = selectedResolverProfileIds.filter((id) => enabledResolverIds.includes(id));
      if (selectedIds.length === 0) {
        setActionMessage("Select at least one corpus to index.");
        return;
      }
      if (enabledResolverIds.length > 0 && selectedResolverIds.length === 0) {
        setActionMessage("Select at least one resolver profile to index.");
        return;
      }
      setActionMessage("Running index job...");
      try {
        const response = await fetch("/api/workbench/index", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            corpusIds: selectedIds,
            resolverProfileIds: selectedResolverIds,
            ...workbenchDbPathPayload()
          })
        });
        const payload = (await response.json()) as {
          status?: string;
          corpusIds?: string[];
          resolverProfileIds?: string[];
          dbPath?: string;
          documents?: number;
          chunks?: number;
          edges?: number;
          jobId?: number;
          jobStatus?: string;
          error?: string;
        };
        if (!response.ok) {
          const failedIds = payload.corpusIds?.length ? payload.corpusIds : selectedIds;
          setCorpora((current) =>
            current.map((corpus) =>
              failedIds.includes(corpus.id)
                ? {
                    ...corpus,
                    status: payload.status ?? "failed"
                  }
                : corpus
            )
          );
          throw new Error(payload.error ?? `Index returned ${response.status}`);
        }
        const indexedIds = payload.corpusIds?.length ? payload.corpusIds : selectedIds;
        const indexedStatus = payload.status ?? "indexed";
        setCorpora((current) =>
          current.map((corpus) =>
            indexedIds.includes(corpus.id)
              ? {
                  ...corpus,
                  status: indexedStatus,
                  fileCount: payload.documents === undefined ? corpus.fileCount : String(payload.documents)
                }
              : corpus
          )
        );
        const corpusLabel = payload.corpusIds?.length ? ` for ${payload.corpusIds.join(", ")}` : "";
        const resolverLabel = payload.resolverProfileIds?.length
          ? ` using ${payload.resolverProfileIds.join(", ")}`
          : selectedResolverIds.length
            ? ` using ${selectedResolverIds.join(", ")}`
            : "";
        const jobLabel = payload.jobId ? ` job ${payload.jobId} ${payload.jobStatus ?? "succeeded"}` : "";
        setActionMessage(
          `Index built${corpusLabel}${jobLabel}: ${payload.documents ?? 0} documents, ${payload.chunks ?? 0} chunks, ${
            payload.edges ?? 0
          } edges -> ${payload.dbPath ?? "data/asip.db"}${resolverLabel}`
        );
        setJobRuns(await fetchJobRuns());
      } catch (error) {
        setActionMessage(error instanceof Error ? error.message : "Index job failed");
      }
      return;
    }

    if (config.id !== "settings") {
      if (config.id === "graph-explorer") {
        if (options.semanticMode === "doc-nodes") {
          setActionMessage("Extracting document graph nodes...");
          try {
            const docNodePayload = {
              mode: "doc-nodes",
              ...workbenchDbPathPayload(),
              ...semanticGenerationLimits("doc-nodes")
            };
            const response = await fetch("/api/workbench/semantic-edges", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(docNodePayload)
            });
            const payload = (await response.json()) as {
              candidate_count?: number;
              box_count?: number;
              edge_count?: number;
              graph?: GraphPayload;
              error?: string;
            };
            if (!response.ok) {
              throw new Error(payload.error ?? `Doc node API returned ${response.status}`);
            }
            if (payload.graph) {
              const graphPayload = sanitizeGraphPayload(payload.graph) ?? { nodes: [], edges: [] };
              setApiGraph(graphPayload);
              setGraphEmptyMessage(
                graphPayload.nodes.length || graphPayload.edges.length
                  ? ""
                  : "Document node job returned no graph data"
              );
            }
            setActionMessage(
              `Document nodes extracted: ${payload.box_count ?? 0} boxes, ${payload.edge_count ?? 0} edges from ${
                payload.candidate_count ?? 0
              } candidates`
            );
          } catch (error) {
            setActionMessage(error instanceof Error ? error.message : "document node extraction failed");
          }
          return;
        }
        if (options.semanticMode === "batch") {
          setActionMessage("Generating batch semantic edges...");
          try {
            const semanticPayload = {
              mode: "batch",
              ...workbenchDbPathPayload(),
              ...semanticGenerationLimits("batch")
            };
            const response = await fetch("/api/workbench/semantic-edges", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(semanticPayload)
            });
            const payload = (await response.json()) as {
              candidate_count?: number;
              edge_count?: number;
              graph?: GraphPayload;
              error?: string;
            };
            if (!response.ok) {
              throw new Error(payload.error ?? `Semantic edge API returned ${response.status}`);
            }
            if (payload.graph) {
              const graphPayload = sanitizeGraphPayload(payload.graph) ?? { nodes: [], edges: [] };
              setApiGraph(graphPayload);
              setGraphEmptyMessage(
                graphPayload.nodes.length || graphPayload.edges.length
                  ? ""
                  : "Batch semantic edge job returned no graph data"
              );
            }
            setActionMessage(
              `Batch semantic edges generated: ${payload.edge_count ?? 0} from ${
                payload.candidate_count ?? 0
              } candidates`
            );
          } catch (error) {
            setActionMessage(error instanceof Error ? error.message : "batch semantic edge generation failed");
          }
          return;
        }
        const semanticEdgeQuery = query.trim() || config.query;
        if (!semanticEdgeQuery.trim()) {
          setActionMessage("Enter a query before generating semantic edges.");
          return;
        }
        setActionMessage("Generating semantic edges...");
        try {
          const limits = semanticGenerationLimits("query");
          const response = await fetch("/api/workbench/semantic-edges", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              q: semanticEdgeQuery,
              ...workbenchDbPathPayload(),
              ...(limits.limit !== undefined ? { limit: limits.limit } : {})
            })
          });
          const payload = (await response.json()) as { edge_count?: number; graph?: GraphPayload; error?: string };
          if (!response.ok) {
            throw new Error(payload.error ?? `Semantic edge API returned ${response.status}`);
          }
          if (payload.graph) {
            const graphPayload = sanitizeGraphPayload(payload.graph) ?? { nodes: [], edges: [] };
            setApiGraph(graphPayload);
            setGraphEmptyMessage(graphPayload.nodes.length || graphPayload.edges.length ? "" : "Semantic edge job returned no graph data");
          }
          setActionMessage(`Semantic edges generated: ${payload.edge_count ?? 0}`);
        } catch (error) {
          setActionMessage(error instanceof Error ? error.message : "semantic edge generation failed");
        }
        return;
      }
      setActionMessage(`${config.actionLabel} queued`);
      return;
    }

    setActionMessage("Running provider smoke...");
    providerSettingsDirtyRef.current = true;
    try {
      const response = await fetch("/api/workbench/providers/smoke", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(runtimeConfig)
      });
      const payload = (await response.json()) as { ok?: boolean; message?: string; error?: string };
      setActionMessage(payload.message ?? payload.error ?? `Provider smoke returned ${response.status}`);
      setProviderVerification(response.ok && payload.ok !== false ? "verified" : "failed");
    } catch (error) {
      setProviderVerification("failed");
      setActionMessage(error instanceof Error ? error.message : "Provider smoke failed");
    }
  }

  async function saveProviderSettings() {
    try {
      providerSettingsDirtyRef.current = true;
      const next = buildProviderSettingsFromDraft(settingsDraft);
      await persistProviderSettings(next, workbenchDbPathForRequest());
      setProviderSettings(next);
      setProviderVerification("unverified");
      setSettingsDraft(settingsToDraft(next));
      setSettingsError("");
      setSettingsMessage("Provider settings saved");
    } catch (error) {
      setSettingsMessage("");
      setSettingsError(error instanceof Error ? error.message : "Provider settings are invalid.");
    }
  }

  async function runProviderAcceptance() {
    try {
      providerSettingsDirtyRef.current = true;
      const next = buildProviderSettingsFromDraft(settingsDraft);
      await persistProviderSettings(next, workbenchDbPathForRequest());
      setProviderSettings(next);
      setProviderVerification("unverified");
      setSettingsDraft(settingsToDraft(next));
      setSettingsError("");
      setActionMessage("Running AQ09 provider acceptance...");
      const response = await fetch("/api/workbench/acceptance/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          queryIds: ["AQ09"],
          surfaces: ["CLI", "API", "MCP"],
          ...dbPathInputPayload(acceptanceDbPath, acceptanceDbPathExplicit)
        })
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { error?: string };
        throw new Error(payload.error ?? `AQ09 acceptance returned ${response.status}`);
      }
      const payload = (await response.json()) as ProviderAcceptanceRun;
      setActionMessage(formatProviderAcceptanceMessage(payload));
      setProviderVerification(providerAcceptancePassed(payload) ? "verified" : "failed");
    } catch (error) {
      setProviderVerification("failed");
      setActionMessage(error instanceof Error ? error.message : "AQ09 provider acceptance failed");
    }
  }

  async function runAcceptanceFromPage() {
    const queryIds = parseCsvList(acceptanceRunnerDraft.queryIds);
    const surfaces = acceptanceSurfacesFromDraft(acceptanceRunnerDraft);
    setActionMessage("Running acceptance...");
    try {
      const response = await fetch("/api/workbench/acceptance/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...dbPathInputPayload(acceptanceRunnerDraft.dbPath, acceptanceRunnerDbPathExplicit),
          ...(queryIds.length ? { queryIds } : {}),
          surfaces,
          ...(acceptanceRunnerDraft.outputJson.trim() ? { outputJson: acceptanceRunnerDraft.outputJson.trim() } : {}),
          ...(acceptanceRunnerDraft.outputMd.trim() ? { outputMd: acceptanceRunnerDraft.outputMd.trim() } : {})
        })
      });
      const payload = (await response.json()) as AcceptanceRunPayload & { error?: string };
      if (!response.ok) {
        throw new Error(payload.error ?? `Acceptance API returned ${response.status}`);
      }
      const run = acceptanceRunFromPayload(payload);
      setAcceptanceRuns((runs) => [run, ...runs.filter((existing) => existing.id !== run.id)]);
      setActionMessage(formatAcceptanceRunMessage(run));
    } catch (error) {
      setActionMessage(error instanceof Error ? error.message : "acceptance run failed");
    }
  }

  async function detectOllamaModels() {
    providerSettingsDirtyRef.current = true;
    const ollamaBaseUrl = settingsDraft.apiBaseUrl.trim() || defaultProviderSettings.apiBaseUrl;
    setSettingsError("");
    setSettingsMessage("Detecting Ollama models...");
    try {
      const response = await fetch(
        `/api/workbench/providers/ollama-tags?baseUrl=${encodeURIComponent(ollamaBaseUrl)}`
      );
      if (!response.ok) {
        throw new Error(`Ollama returned ${response.status}`);
      }
      const data = (await response.json()) as { models?: Array<{ name?: string }> };
      const modelNames = (data.models ?? []).map((model) => model.name ?? "").filter(Boolean);
      if (modelNames.length === 0) {
        throw new Error("No Ollama models found.");
      }
      const embeddingModel = chooseEmbeddingModel(modelNames);
      const edgeModel = chooseEdgeModel(modelNames, embeddingModel);
      setSettingsDraft((current) => ({
        ...current,
        provider: "ollama",
        apiBaseUrl: ollamaBaseUrl,
        apiPath: "/api/chat",
        edgeModel,
        fallbackModel: "",
        embeddingProvider: "ollama",
        embeddingApiBaseUrl: ollamaBaseUrl,
        embeddingApiPath: "/api/embeddings",
        embeddingModel
      }));
      setProviderVerification("unverified");
      setSettingsMessage(`Detected ${modelNames.length} Ollama models`);
    } catch (error) {
      setSettingsMessage("");
      setSettingsError(error instanceof Error ? error.message : "Ollama detection failed.");
    }
  }

  async function addCorpus() {
    const id = corpusDraft.id.trim();
    if (!id) {
      setCorpusMessage("Corpus id is required");
      return;
    }
    const next: CorpusEntry = {
      id,
      repo: corpusDraft.repo.trim() || "local",
      sourceRoot: corpusDraft.sourceRoot.trim() || id,
      include: corpusDraft.include.trim() || "**/*",
      subfolders: corpusDraft.subfolders.trim(),
      fileCount: corpusDraft.fileCount.trim() || "user"
    };
    try {
      const response = await fetch("/api/workbench/corpora", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: next.id,
          repo: next.repo,
          sourceRoot: next.sourceRoot,
          include: next.include.split(",").map((item) => item.trim()).filter(Boolean),
          subfolders: parseSubfolderFilters(next.subfolders),
          type: next.include.includes("pdf") ? "doc" : "code",
          ...workbenchDbPathPayload()
        })
      });
      const payload = (await response.json()) as ApiCorpusEntry & { error?: string };
      if (!response.ok) {
        throw new Error(payload.error ?? `Corpus API returned ${response.status}`);
      }
      const persisted = normalizeApiCorpus(payload);
      const nextCorpora = [...corpora.filter((corpus) => corpus.id !== persisted.id), persisted];
      setCorpora(nextCorpora);
      setSelectedCorpusIds((current) => Array.from(new Set([...current, persisted.id])));
      setCorpusDraft({ id: "", repo: "", sourceRoot: "", include: "**/*.c, **/*.h", subfolders: "", fileCount: "user" });
      setCorpusMessage(`Corpus ${persisted.id} added`);
    } catch (error) {
      setCorpusMessage(error instanceof Error ? error.message : "Corpus add failed");
    }
  }

  async function addResolverProfile() {
    const id = resolverDraft.id.trim();
    const wrapper = resolverDraft.wrapper.trim();
    if (!id || !wrapper) {
      setResolverMessage("Profile id and wrapper symbol are required");
      return;
    }
    const next: ResolverProfile = {
      id,
      wrapper,
      wrappers: [wrapper],
      strategy: resolverDraft.strategy.trim() || "macro",
      path: resolverDraft.path.trim() || `configs/resolvers/${id}.yaml`,
      enabled: resolverDraft.enabled,
      functionNormalizationEnabled: resolverDraft.functionNormalizationEnabled,
      conceptRuleId: resolverDraft.conceptRuleId.trim(),
      conceptMatch: resolverDraft.conceptMatch.trim(),
      conceptCanonical: resolverDraft.conceptCanonical.trim()
    };
    try {
      const response = await fetch("/api/workbench/resolver-profiles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: next.id,
          language: next.strategy.includes("python") ? "python" : "cpp",
          wrappers: [next.wrapper],
          strategy: next.strategy,
          path: next.path,
          enabled: next.enabled,
          functionNormalization: {
            enabled: next.functionNormalizationEnabled,
            rules:
              next.functionNormalizationEnabled && next.conceptRuleId && next.conceptMatch && next.conceptCanonical
                ? [
                    {
                      id: next.conceptRuleId,
                      enabled: true,
                      match: next.conceptMatch,
                      canonical: next.conceptCanonical
                    }
                  ]
                : []
          },
          ...workbenchDbPathPayload()
        })
      });
      const payload = (await response.json()) as ApiResolverProfile & { error?: string };
      if (!response.ok) {
        throw new Error(payload.error ?? `Resolver API returned ${response.status}`);
      }
      const persisted = normalizeApiResolverProfile(payload);
      const nextProfiles = [...resolverProfiles.filter((profile) => profile.id !== persisted.id), persisted];
      setResolverProfiles(nextProfiles);
      setResolverDraft({
        id: "initial",
        wrapper: "RREG32",
        wrappers: ["RREG32"],
        strategy: "macro",
        path: "configs/resolvers/initial.yaml",
        enabled: true,
        functionNormalizationEnabled: false,
        conceptRuleId: defaultConceptRuleId,
        conceptMatch: defaultConceptMatch,
        conceptCanonical: defaultConceptCanonical
      });
      setResolverMessage(`Resolver profile ${persisted.id} saved`);
    } catch (error) {
      setResolverMessage(error instanceof Error ? error.message : "Resolver profile add failed");
    }
  }

  async function validateResolverProfile() {
    const id = resolverDraft.id.trim();
    if (!id) {
      setResolverMessage("Profile id is required for validation");
      return;
    }
    try {
      const response = await fetch("/api/workbench/resolver-profiles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id,
          validateSource: resolverValidateSource,
          ...workbenchDbPathPayload()
        })
      });
      const payload = (await response.json()) as {
        valid?: boolean;
        symbols?: Array<{ symbol?: string }>;
        error?: string;
      };
      if (!response.ok) {
        throw new Error(payload.error ?? `Resolver validation returned ${response.status}`);
      }
      const symbols = (payload.symbols ?? []).map((symbol) => symbol.symbol).filter(Boolean);
      setResolverMessage(
        payload.valid && symbols.length
          ? `Resolver profile ${id} validated ${symbols.join(", ")}`
          : `Resolver profile ${id} validation failed`
      );
    } catch (error) {
      setResolverMessage(error instanceof Error ? error.message : "Resolver profile validation failed");
    }
  }

  function toggleCorpusSelection(corpusId: string, selected: boolean) {
    setSelectedCorpusIds((current) => {
      if (selected) {
        return current.includes(corpusId) ? current : [...current, corpusId];
      }
      return current.filter((id) => id !== corpusId);
    });
  }

  function toggleResolverProfileSelection(profileId: string, selected: boolean) {
    resolverProfileSelectionTouchedRef.current = true;
    setSelectedResolverProfileIds((current) => {
      if (selected) {
        return current.includes(profileId) ? current : [...current, profileId];
      }
      return current.filter((id) => id !== profileId);
    });
  }

  function toggleSourceType(sourceType: string) {
    setSelectedSourceTypes((current) =>
      current.includes(sourceType)
        ? current.filter((item) => item !== sourceType)
        : [...current, sourceType].sort((left, right) => sourceFilterTypes.indexOf(left as typeof sourceFilterTypes[number]) - sourceFilterTypes.indexOf(right as typeof sourceFilterTypes[number]))
    );
  }

  function semanticGenerationLimits(mode: "query" | "batch" | "doc-nodes") {
    const parsedLimit = Number(semanticLimitDraft);
    const parsedBatchSize = Number(semanticBatchSizeDraft);
    const configuredLimit =
      mode === "query"
        ? workbenchLimits.semantic?.queryLimit
        : workbenchLimits.semantic?.batchCandidateLimit;
    return {
      ...(Number.isFinite(parsedLimit) && parsedLimit > 0
        ? { limit: parsedLimit }
        : configuredLimit !== undefined
          ? { limit: configuredLimit }
          : {}),
      ...(Number.isFinite(parsedBatchSize) && parsedBatchSize > 0
        ? { batchSize: parsedBatchSize }
        : workbenchLimits.semantic?.batchSize !== undefined
          ? { batchSize: workbenchLimits.semantic.batchSize }
          : {})
    };
  }

  async function fetchJobRuns() {
    try {
      const params = new URLSearchParams({ limit: "8" });
      appendWorkbenchDbPath(params);
      const response = await fetch(`/api/workbench/jobs?${params.toString()}`);
      if (!response.ok) {
        return [];
      }
      const payload = (await response.json()) as { jobs?: JobRun[] };
      return (payload.jobs ?? []).map(normalizeJobRun);
    } catch {
      return [];
    }
  }

  return (
    <div className="workbench-shell" data-page-id={config.id} data-testid="asip-workbench">
      <header className="topbar" role="banner">
        <div className="brand">
          <Image alt="" className="brand-logo" height={32} priority src="/brand/asip-logo.png" width={32} />
          <span>ASIP Evidence Workbench</span>
        </div>
        <form className="global-search" onSubmit={handleGlobalSearchSubmit}>
          <Search aria-hidden="true" size={15} />
          <Input
            aria-label="Global symbol search"
            onChange={(event) => setGlobalQuery(event.target.value)}
            placeholder="Search indexed symbols"
            value={globalQuery}
          />
        </form>
        <div className="status-row" aria-label="Workbench status">
          <ToneBadge tone={providerVerification === "verified" ? "success" : "neutral"}>
            <span className="status-dot" />
            Provider: {providerVerification}
          </ToneBadge>
          <Badge>Edge: {providerLabel} / {providerSettings.edgeModel || "unset"}</Badge>
          <Badge>Index: {indexStatusLabel}</Badge>
        </div>
        <Button
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
          onClick={() => setTheme((current) => (current === "dark" ? "light" : "dark"))}
          type="button"
          variant="secondary"
        >
          {theme === "dark" ? <Sun aria-hidden="true" size={14} /> : <Moon aria-hidden="true" size={14} />}
          {theme === "dark" ? "Light" : "Dark"}
        </Button>
      </header>

      <main className="workbench-grid">
        <nav className="sidebar" aria-label="ASIP sections">
          {navItems.map((item) => (
            <Link
              aria-current={item.id === config.id ? "page" : undefined}
              className="nav-item"
              href={item.href}
              key={item.id}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <section className="center-pane" aria-label={config.workspaceLabel}>
          <form className="composer" onSubmit={handleQuerySubmit}>
            <label className="query-input">
              <Search aria-hidden="true" size={16} />
              <Input
                aria-label="Evidence query"
                name="query"
                onChange={(event) => updateQuery(event.target.value)}
                placeholder="Query live evidence"
                ref={queryInputRef}
                value={query}
              />
            </label>
            <label className="metadata-filter-input">
              <Input
                aria-label="IP block filter"
                onChange={(event) => setIpFilter(event.target.value)}
                placeholder="IP"
                value={ipFilter}
              />
            </label>
            <label className="metadata-filter-input">
              <Input
                aria-label="ASIC or generation filter"
                onChange={(event) => setAsicFilter(event.target.value)}
                placeholder="ASIC"
                value={asicFilter}
              />
            </label>
            <Button type="submit">
              Run query
            </Button>
          </form>

          <div className="metric-row" aria-label="Page metrics">
            {pageMetrics.map((metric) => (
              <ToneBadge key={metric.label} tone={metric.tone ?? "neutral"}>
                {metric.label}: {metric.value}
              </ToneBadge>
            ))}
          </div>

          {config.id === "graph-explorer" || config.id === "evidence-workbench" ? (
            <ImpactHopControl level={graphHopLevel} onChange={(value) => setGraphHopLevel(clampGraphHopLevel(value))} />
          ) : null}

          {config.filters.length ? (
            <div className="filter-row" aria-label="Evidence source filters">
              {config.filters.map(({ icon: Icon, label }) => (
                <Button
                  aria-label={`Source filter ${label}`}
                  aria-pressed={selectedSourceTypes.includes(label.toLowerCase())}
                  key={label}
                  onClick={() => toggleSourceType(label.toLowerCase())}
                  type="button"
                  variant={selectedSourceTypes.includes(label.toLowerCase()) ? "secondary" : "ghost"}
                >
                  <Icon aria-hidden="true" size={14} />
                  {label}
                </Button>
              ))}
            </div>
          ) : null}

          {config.id === "settings" ? (
            <ProviderSettingsPanel
              draft={settingsDraft}
              onDetectOllama={detectOllamaModels}
              error={settingsError}
              message={settingsMessage}
              acceptanceDbPath={acceptanceDbPath}
              onChange={(draft) => {
                providerSettingsDirtyRef.current = true;
                setProviderVerification("unverified");
                setSettingsDraft(draft);
              }}
              onAcceptanceDbPathChange={(value) => {
                setAcceptanceDbPathExplicit(Boolean(value));
                setAcceptanceDbPath(value);
              }}
              onSave={saveProviderSettings}
              onRunAcceptance={runProviderAcceptance}
              runtimeConfig={runtimeConfig}
            />
          ) : null}

          {config.id === "corpus" ? (
            <>
              <CorpusEditor
                draft={corpusDraft}
                message={corpusMessage}
                onAdd={addCorpus}
                onChange={setCorpusDraft}
              />
              <ResolverProfileSelector
                onToggle={toggleResolverProfileSelection}
                profiles={resolverProfiles}
                selectedIds={selectedResolverProfileIds}
              />
            </>
          ) : null}

          {config.id === "resolver-profiles" ? (
            <ResolverProfileEditor
              draft={resolverDraft}
              message={resolverMessage}
              onAdd={addResolverProfile}
              onChange={setResolverDraft}
              onValidate={validateResolverProfile}
              onValidateSourceChange={setResolverValidateSource}
              profiles={resolverProfiles}
              validateSource={resolverValidateSource}
            />
          ) : null}

          {config.id === "graph-explorer" || config.id === "evidence-workbench" ? (
            <GlobalNetworkGraph
              emptyMessage={graphEmptyMessage || queryEmptyMessage}
              graph={apiGraph}
              impactLevel={graphHopLevel}
              functionView={graphFunctionView}
              limits={workbenchLimits}
              loadedEdgeBudget={graphEdgeBudget}
              onFunctionViewChange={setGraphFunctionView}
              onLoadedEdgeBudgetChange={setGraphEdgeBudget}
              onNodeSelect={(node) => setSelectedGraphNodeId(node.id)}
              selectedNodeId={selectedGraphNodeId}
              testId={config.id === "graph-explorer" ? "global-network-graph" : "query-network-graph"}
            />
          ) : null}

          {config.id === "acceptance-tests" ? (
            <>
              <AcceptanceRunnerPanel
                draft={acceptanceRunnerDraft}
                onChange={(draft) => {
                  setAcceptanceRunnerDbPathExplicit(Boolean(draft.dbPath));
                  setAcceptanceRunnerDraft(draft);
                }}
                onRun={runAcceptanceFromPage}
              />
              <AcceptanceRunsPanel runs={acceptanceRuns} />
            </>
          ) : null}

          <EvidenceResultsTable
            emptyMessage={queryEmptyMessage || "No evidence matched this query."}
            isCorpus={config.id === "corpus"}
            isInteractive={config.id === "evidence-workbench"}
            onSelectRow={(row) => setSelectedEvidenceKey(evidenceRowKey(row))}
            onToggleCorpus={toggleCorpusSelection}
            rows={evidenceRows}
            selectedCorpusIds={selectedCorpusIds}
          />
        </section>

        <aside className="details-pane">
          <div className="details-heading">
            <h2>{inspectorTitle}</h2>
            <Badge>
              <Activity aria-hidden="true" size={13} />
              {config.inspectorBadge} / run {runCount}
            </Badge>
          </div>
          <div className="chain">
            {inspectorChain.map((item, index) => (
              <p className={index > 0 ? "edge" : undefined} key={item}>
                <code>{item}</code>
              </p>
            ))}
          </div>
          {inspectorDetailSections.map((section) => (
            <section className="inspector-section" key={section.title}>
              <h3>{section.title}</h3>
              {section.lines?.length ? (
                <ul className="node-detail-list">
                  {section.lines.map((line) => (
                    <li key={line}>
                      <code>{line}</code>
                    </li>
                  ))}
                </ul>
              ) : (
                <p>
                  <code>{section.body}</code>
                </p>
              )}
            </section>
          ))}
          <h3>Relationship Panel</h3>
          <div className="chain" data-testid="relationship-panel">
            {inspectorRelationshipLines.map((line) => (
              <p key={line}>
                <code>{line}</code>
              </p>
            ))}
          </div>
          <Button
            className="settings-button"
            onClick={() => void runPageAction()}
            type="button"
            variant="secondary"
          >
            {config.actionLabel}
          </Button>
          {config.id === "graph-explorer" ? (
            <>
              <Button
                className="settings-button"
                onClick={() => void runPageAction({ semanticMode: "batch" })}
                type="button"
                variant="secondary"
              >
                Generate batch semantic edges
              </Button>
              <Button
                className="settings-button"
                onClick={() => void runPageAction({ semanticMode: "doc-nodes" })}
                type="button"
                variant="secondary"
              >
                Extract document nodes
              </Button>
            </>
          ) : null}
          {actionMessage ? (
            <p className="action-feedback" data-testid="action-feedback">
              {actionMessage}
            </p>
          ) : null}
          {config.id === "corpus" ? <JobRunsPanel jobs={jobRuns} /> : null}
          {config.id === "graph-explorer" ? (
            <div className="semantic-limit-controls" aria-label="Semantic generation controls">
              <label>
                <span>Semantic candidate limit</span>
                <Input
                  aria-label="Semantic candidate limit"
                  min={1}
                  onChange={(event) => setSemanticLimitDraft(event.target.value)}
                  placeholder={String(workbenchLimits.semantic?.batchCandidateLimit ?? "")}
                  type="number"
                  value={semanticLimitDraft}
                />
              </label>
              <label>
                <span>Semantic batch size</span>
                <Input
                  aria-label="Semantic batch size"
                  min={1}
                  onChange={(event) => setSemanticBatchSizeDraft(event.target.value)}
                  placeholder={String(workbenchLimits.semantic?.batchSize ?? "")}
                  type="number"
                  value={semanticBatchSizeDraft}
                />
              </label>
            </div>
          ) : null}
        </aside>
      </main>
    </div>
  );
}

type ToneBadgeProps = ComponentProps<typeof Badge> & {
  tone?: SourceTone | "field";
};

function ToneBadge({ className, tone = "neutral", variant, ...props }: ToneBadgeProps) {
  return (
    <Badge
      className={cn("tone-badge", `tone-badge--${tone}`, className)}
      variant={variant ?? badgeVariantForTone(tone)}
      {...props}
    />
  );
}

function badgeVariantForTone(tone: SourceTone | "field"): ComponentProps<typeof Badge>["variant"] {
  if (tone === "pdf") {
    return "destructive";
  }
  if (tone === "success") {
    return "default";
  }
  if (tone === "neutral") {
    return "secondary";
  }
  return "outline";
}

function EvidenceResultsTable({
  emptyMessage,
  isCorpus,
  isInteractive,
  onSelectRow,
  onToggleCorpus,
  rows,
  selectedCorpusIds
}: {
  emptyMessage: string;
  isCorpus: boolean;
  isInteractive: boolean;
  onSelectRow: (row: EvidenceRow) => void;
  onToggleCorpus: (corpusId: string, selected: boolean) => void;
  rows: EvidenceRow[];
  selectedCorpusIds: string[];
}) {
  return (
    <Card className="results-card">
      <CardContent className="p-0">
        <Table aria-label="Evidence results">
          <TableHeader>
            <TableRow>
              <TableHead className="w-8">Type</TableHead>
              {isCorpus ? <TableHead className="w-10">Index</TableHead> : null}
              <TableHead>Symbol</TableHead>
              <TableHead>Source</TableHead>
              <TableHead>Relation</TableHead>
              <TableHead>Score</TableHead>
              <TableHead>Location</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length ? (
              rows.map((item) => {
                const rowKey = evidenceRowKey(item);
                return (
                  <TableRow
                    className={cn(isInteractive && "cursor-pointer")}
                    key={rowKey}
                    onClick={isInteractive ? () => onSelectRow(item) : undefined}
                    onKeyDown={
                      isInteractive
                        ? (event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              onSelectRow(item);
                            }
                          }
                        : undefined
                    }
                    tabIndex={isInteractive ? 0 : undefined}
                  >
                    <TableCell>
                      <span className={`source-dot source-dot--${item.tone}`} />
                    </TableCell>
                    {isCorpus ? (
                      <TableCell>
                        <Checkbox
                          aria-label={`Index ${item.symbol}`}
                          checked={selectedCorpusIds.includes(item.symbol)}
                          onCheckedChange={(checked) => onToggleCorpus(item.symbol, checked === true)}
                        />
                      </TableCell>
                    ) : null}
                    <TableCell>
                      <code>{formatEvidenceSymbol(item)}</code>
                    </TableCell>
                    <TableCell>
                      <ToneBadge className="source-type-badge" tone={sourceToneForRow(item)}>
                        {sourceLabelForRow(item)}
                      </ToneBadge>
                    </TableCell>
                    <TableCell>
                      <ToneBadge tone={item.tone}>{item.relation}</ToneBadge>
                    </TableCell>
                    <TableCell className="score">{item.score}</TableCell>
                    <TableCell className="path">{formatEvidenceLocation(item)}</TableCell>
                  </TableRow>
                );
              })
            ) : (
              <TableRow>
                <TableCell>
                  <span className="source-dot source-dot--neutral" />
                </TableCell>
                {isCorpus ? <TableCell /> : null}
                <TableCell>
                  <code>{emptyMessage}</code>
                </TableCell>
                <TableCell>
                  <Badge variant="secondary">empty</Badge>
                </TableCell>
                <TableCell>
                  <Badge variant="secondary">empty</Badge>
                </TableCell>
                <TableCell className="score">0</TableCell>
                <TableCell className="path">live SQLite query returned no rows</TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function AcceptanceRunnerPanel({
  draft,
  onChange,
  onRun
}: {
  draft: AcceptanceRunnerDraft;
  onChange: (draft: AcceptanceRunnerDraft) => void;
  onRun: () => void;
}) {
  const update = <Key extends keyof AcceptanceRunnerDraft>(key: Key, value: AcceptanceRunnerDraft[Key]) => {
    onChange({ ...draft, [key]: value });
  };
  const toggleSurface = (surface: AcceptanceSurface, checked: boolean) => {
    onChange({ ...draft, surfaces: { ...draft.surfaces, [surface]: checked } });
  };

  return (
    <Card className="acceptance-runner-card" aria-label="Acceptance runner">
      <CardHeader>
        <CardTitle>Acceptance Runner</CardTitle>
        <CardDescription>Run selected QA queries against any indexed DB and capture output artifacts.</CardDescription>
      </CardHeader>
      <CardContent>
        <FieldGroup className="acceptance-runner-grid">
          <Field>
            <FieldLabel>Acceptance query IDs</FieldLabel>
            <Input
              aria-label="Acceptance query IDs"
              onChange={(event) => update("queryIds", event.target.value)}
              value={draft.queryIds}
            />
          </Field>
          <Field>
            <FieldLabel>Acceptance DB path</FieldLabel>
            <Input
              aria-label="Acceptance DB path"
              onChange={(event) => update("dbPath", event.target.value)}
              value={draft.dbPath}
            />
          </Field>
          <Field>
            <FieldLabel>Acceptance output JSON</FieldLabel>
            <Input
              aria-label="Acceptance output JSON"
              onChange={(event) => update("outputJson", event.target.value)}
              value={draft.outputJson}
            />
          </Field>
          <Field>
            <FieldLabel>Acceptance output Markdown</FieldLabel>
            <Input
              aria-label="Acceptance output Markdown"
              onChange={(event) => update("outputMd", event.target.value)}
              value={draft.outputMd}
            />
          </Field>
        </FieldGroup>
        <div className="acceptance-surface-row" aria-label="Acceptance surfaces">
          {(Object.keys(draft.surfaces) as AcceptanceSurface[]).map((surface) => (
            <label className="checkbox-inline" key={surface}>
              <Checkbox
                aria-label={`${surface} surface`}
                checked={draft.surfaces[surface]}
                onCheckedChange={(checked) => toggleSurface(surface, checked === true)}
              />
              <span>{surface}</span>
            </label>
          ))}
        </div>
        <Button onClick={onRun} type="button">
          Run acceptance
        </Button>
      </CardContent>
    </Card>
  );
}

function AcceptanceRunsPanel({ runs }: { runs: AcceptanceRun[] }) {
  if (runs.length === 0) {
    return null;
  }
  return (
    <Card className="acceptance-runs-card">
      <CardHeader>
        <CardTitle>Acceptance run details</CardTitle>
        <CardDescription>Expand a run to inspect query-level failures, missing surfaces, and source evidence.</CardDescription>
      </CardHeader>
      <CardContent>
        <Accordion className="acceptance-accordion" collapsible type="single">
          {runs.map((run) => {
            const details = run.details ?? [];
            return (
              <AccordionItem key={run.id} value={run.id}>
                <AccordionTrigger>
                  <span className="acceptance-run-trigger">
                    <code>{run.id}</code>
                    <ToneBadge tone={run.failed ? "pdf" : "success"}>{run.passed}/{run.queryCount}</ToneBadge>
                    <ToneBadge tone={run.partial ? "doc" : "neutral"}>partial {run.partial ?? 0}</ToneBadge>
                    <ToneBadge tone={run.failed ? "pdf" : "success"}>failed {run.failed}</ToneBadge>
                    <span>{run.model}</span>
                  </span>
                </AccordionTrigger>
                <AccordionContent>
                  <div className="acceptance-run-meta">
                    <span>artifact</span>
                    <code>{run.artifactPath}</code>
                  </div>
                  {details.length ? (
                    <Table aria-label={`Acceptance details for ${run.id}`}>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Query</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Reason</TableHead>
                          <TableHead>Sources</TableHead>
                          <TableHead>Counts</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {details.map((detail) => (
                          <TableRow key={`${run.id}-${detail.id}`}>
                            <TableCell>
                              <code>{detail.id}</code>
                              {detail.query ? <p>{detail.query}</p> : null}
                            </TableCell>
                            <TableCell>
                              <ToneBadge tone={detail.status === "pass" ? "success" : detail.status === "partial" ? "doc" : "pdf"}>
                                {detail.status}
                              </ToneBadge>
                            </TableCell>
                            <TableCell>
                              <AcceptanceDetailText detail={detail} />
                            </TableCell>
                            <TableCell>
                              <AcceptanceSourceText detail={detail} />
                            </TableCell>
                            <TableCell>
                              rows {detail.rowCount ?? 0} / graph edges {detail.graphEdgeCount ?? detail.edgeCount ?? 0}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  ) : (
                    <p>No query-level detail was returned for this run.</p>
                  )}
                </AccordionContent>
              </AccordionItem>
            );
          })}
        </Accordion>
      </CardContent>
    </Card>
  );
}

function AcceptanceDetailText({ detail }: { detail: AcceptanceDetail }) {
  const lines = [
    ...detail.failureReasons,
    detail.missingSurfaces.length ? `missing surfaces: ${detail.missingSurfaces.join(", ")}` : "",
    detail.missing.length ? `missing terms: ${detail.missing.join(", ")}` : "",
    ...formatAcceptanceSurfaceResults(detail.surfaceResults),
    ...formatAcceptanceProviderChecks(detail.providerChecks)
  ].filter(Boolean);
  return lines.length ? (
    <div className="acceptance-detail-stack">
      {lines.map((line) => (
        <span key={line}>{line}</span>
      ))}
    </div>
  ) : (
    <span>No failure reason recorded.</span>
  );
}

function AcceptanceSourceText({ detail }: { detail: AcceptanceDetail }) {
  const paths = detail.sourcePaths.slice(0, 3);
  return (
    <div className="acceptance-detail-stack">
      <span>{detail.sourceTypes.length ? detail.sourceTypes.join(", ") : "no source type"}</span>
      {paths.map((sourcePath) => (
        <code key={sourcePath}>{sourcePath}</code>
      ))}
    </div>
  );
}

function formatAcceptanceProviderChecks(checks: AcceptanceDetail["providerChecks"]): string[] {
  if (!checks) {
    return [];
  }
  return [
    formatAcceptanceProviderCheck("embedding", checks.embedding),
    formatAcceptanceProviderCheck("semantic edge", checks.semanticEdge)
  ].filter(Boolean) as string[];
}

function formatAcceptanceSurfaceResults(results: AcceptanceSurfaceResult[] | undefined): string[] {
  if (!results?.length) {
    return [];
  }
  return results.map((result) => {
    const graphText =
      result.graphNodeCount !== undefined || result.graphEdgeCount !== undefined
        ? `, graph ${result.graphNodeCount ?? 0} nodes / ${result.graphEdgeCount ?? 0} edges`
        : "";
    const rowText = result.rowCount !== undefined ? `: rows ${result.rowCount}${graphText}` : "";
    const message = result.message && result.message !== "ok" ? `: ${result.message}` : rowText;
    return `${result.surface} ${result.transport} ${result.status}${message}`;
  });
}

function formatAcceptanceProviderCheck(label: string, check: ProviderAcceptanceCheck | undefined): string {
  if (!check) {
    return "";
  }
  const status = check.status || "unknown";
  const provider = check.provider || "unknown-provider";
  const model = check.model || "unknown-model";
  const message = check.message ? `: ${check.message}` : "";
  return `${label} ${status}: ${provider} / ${model}${message}`;
}

function parseCsvList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function acceptanceSurfacesFromDraft(draft: AcceptanceRunnerDraft): AcceptanceSurface[] {
  const selected = (Object.keys(draft.surfaces) as AcceptanceSurface[]).filter((surface) => draft.surfaces[surface]);
  return selected.length ? selected : ["CLI", "API", "MCP"];
}

function acceptanceRunFromPayload(payload: AcceptanceRunPayload): AcceptanceRun {
  const summary = payload.summary ?? {};
  const runId = `acceptance-live-${Date.now()}`;
  return normalizeAcceptanceRun({
    id: runId,
    model: payload.source ?? "asip.acceptance",
    passed: Number(summary.passed ?? 0),
    partial: Number(summary.partial ?? 0),
    failed: Number(summary.failed ?? 0),
    queryCount: Number(summary.total ?? payload.queries?.length ?? 0),
    artifactPath: payload.output_json ?? payload.output_md ?? "live acceptance run",
    details: (payload.queries ?? []).map((query) => normalizeAcceptanceDetail(query))
  });
}

function formatAcceptanceRunMessage(run: AcceptanceRun): string {
  const status = run.failed ? "failed" : run.partial ? "partial" : "passed";
  return `Acceptance run ${status}: ${run.passed}/${run.queryCount}`;
}

function settingsToDraft(settings: ProviderSettings): ProviderSettingsDraft {
  return {
    ...settings,
    extraHeadersJson: JSON.stringify(settings.extraHeaders, null, 2),
    embeddingExtraHeadersJson: JSON.stringify(settings.embeddingExtraHeaders, null, 2)
  };
}

function normalizeProviderSettings(settings: Partial<ProviderSettings>): ProviderSettings {
  return {
    ...defaultProviderSettings,
    ...settings,
    embeddingProvider: settings.embeddingProvider ?? settings.provider ?? defaultProviderSettings.embeddingProvider,
    embeddingApiBaseUrl:
      settings.embeddingApiBaseUrl ?? settings.apiBaseUrl ?? defaultProviderSettings.embeddingApiBaseUrl,
    embeddingApiPath: settings.embeddingApiPath ?? defaultProviderSettings.embeddingApiPath,
    extraHeaders: settings.extraHeaders ?? {},
    embeddingExtraHeaders: settings.embeddingExtraHeaders ?? {}
  };
}

function providerSettingsFromBackend(payload: BackendProviderSettings): ProviderSettings | null {
  if (!payload.edge && !payload.embedding) {
    return null;
  }
  const edge = payload.edge ?? {};
  const embedding = payload.embedding ?? {};
  return normalizeProviderSettings({
    provider: normalizeProviderName(edge.provider, defaultProviderSettings.provider),
    apiBaseUrl: edge.base_url ?? edge.api_base_url ?? defaultProviderSettings.apiBaseUrl,
    apiPath: edge.api_path ?? defaultProviderSettings.apiPath,
    edgeModel: edge.model ?? edge.preferred ?? defaultProviderSettings.edgeModel,
    fallbackModel: edge.fallback_model ?? edge.fallback ?? defaultProviderSettings.fallbackModel,
    embeddingProvider: normalizeProviderName(embedding.provider, defaultProviderSettings.embeddingProvider),
    embeddingApiBaseUrl:
      embedding.base_url ?? embedding.api_base_url ?? defaultProviderSettings.embeddingApiBaseUrl,
    embeddingApiPath: embedding.api_path ?? defaultProviderSettings.embeddingApiPath,
    embeddingModel: embedding.model ?? embedding.embedding_model ?? defaultProviderSettings.embeddingModel,
    timeoutSeconds: String(edge.timeout_seconds ?? defaultProviderSettings.timeoutSeconds),
    numCtx: String(edge.num_ctx ?? defaultProviderSettings.numCtx),
    numPredict: String(edge.num_predict ?? defaultProviderSettings.numPredict),
    temperature: String(edge.temperature ?? defaultProviderSettings.temperature),
    think: Boolean(edge.think),
    extraHeaders: edge.extra_headers ?? {},
    embeddingExtraHeaders: embedding.extra_headers ?? {}
  });
}

function normalizeProviderName<Provider extends ProviderSettings["provider"] | ProviderSettings["embeddingProvider"]>(
  provider: string | undefined,
  fallback: Provider
): Provider {
  return provider === "ollama" || provider === "openai-compatible" ? (provider as Provider) : fallback;
}

function parseExtraHeaders(value: string): Record<string, string> {
  if (!value.trim()) {
    return {};
  }
  const parsed = JSON.parse(value) as unknown;
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
    throw new Error("Extra headers JSON must be an object.");
  }
  return Object.fromEntries(
    Object.entries(parsed).map(([key, headerValue]) => [key, String(headerValue)])
  );
}

function buildProviderSettingsFromDraft(settingsDraft: ProviderSettingsDraft): ProviderSettings {
  return {
    provider: settingsDraft.provider,
    apiBaseUrl: settingsDraft.apiBaseUrl.trim(),
    apiPath: settingsDraft.apiPath.trim() || "/api/chat",
    edgeModel: settingsDraft.edgeModel.trim(),
    fallbackModel: settingsDraft.fallbackModel.trim(),
    embeddingProvider: settingsDraft.embeddingProvider,
    embeddingApiBaseUrl: settingsDraft.embeddingApiBaseUrl.trim(),
    embeddingApiPath: settingsDraft.embeddingApiPath.trim() || defaultProviderSettings.embeddingApiPath,
    embeddingModel: settingsDraft.embeddingModel.trim(),
    embeddingExtraHeaders: parseExtraHeaders(settingsDraft.embeddingExtraHeadersJson),
    timeoutSeconds: settingsDraft.timeoutSeconds.trim(),
    numCtx: settingsDraft.numCtx.trim(),
    numPredict: settingsDraft.numPredict.trim(),
    temperature: settingsDraft.temperature.trim(),
    think: settingsDraft.think,
    extraHeaders: parseExtraHeaders(settingsDraft.extraHeadersJson)
  };
}

async function persistProviderSettings(next: ProviderSettings, dbPath?: string) {
  const response = await fetch("/api/workbench/providers/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...providerSettingsToBackend(next),
      ...(dbPath === undefined ? {} : { dbPath })
    })
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as { error?: string };
    throw new Error(payload.error ?? `Provider settings API returned ${response.status}`);
  }
  window.localStorage.setItem(providerSettingsStorageKey, JSON.stringify(next));
}

function formatProviderAcceptanceMessage(payload: ProviderAcceptanceRun): string {
  if (payload.error) {
    return payload.error;
  }
  const aq09 = (payload.queries ?? []).find((query) => query.id === "AQ09");
  if (!aq09) {
    return "AQ09 provider acceptance returned no AQ09 result";
  }
  const embedding = formatProviderAcceptanceCheck(aq09.provider_checks?.embedding);
  const semanticEdge = formatProviderAcceptanceCheck(aq09.provider_checks?.semantic_edge);
  return `AQ09 provider acceptance ${aq09.status ?? "unknown"}: embedding ${embedding}, semantic edge ${semanticEdge}`;
}

function providerAcceptancePassed(payload: ProviderAcceptanceRun): boolean {
  const aq09 = (payload.queries ?? []).find((query) => query.id === "AQ09");
  return Boolean(
    aq09 &&
      aq09.status === "pass" &&
      aq09.provider_checks?.embedding?.status === "pass" &&
      aq09.provider_checks?.semantic_edge?.status === "pass"
  );
}

function formatProviderAcceptanceCheck(check: ProviderAcceptanceCheck | undefined): string {
  if (!check) {
    return "missing";
  }
  const provider = check.provider || "unknown-provider";
  const model = check.model || "unknown-model";
  return `${provider}/${model}`;
}

function buildRuntimeEdgeModelConfig(settings: ProviderSettings): RuntimeEdgeModelConfig {
  return {
    provider: settings.provider,
    api_base_url: settings.apiBaseUrl,
    api_path: settings.apiPath,
    preferred: settings.edgeModel,
    fallback: settings.fallbackModel,
    embedding_provider: settings.embeddingProvider,
    embedding_api_base_url: settings.embeddingApiBaseUrl,
    embedding_api_path: settings.embeddingApiPath,
    embedding_model: settings.embeddingModel,
    embedding_extra_headers: settings.embeddingExtraHeaders,
    extra_headers: settings.extraHeaders,
    format: "json",
    num_ctx: numberFromDraft(settings.numCtx, defaultProviderSettings.numCtx),
    num_predict: numberFromDraft(settings.numPredict, defaultProviderSettings.numPredict),
    temperature: numberFromDraft(settings.temperature, defaultProviderSettings.temperature),
    think: settings.think,
    timeout_seconds: numberFromDraft(settings.timeoutSeconds, defaultProviderSettings.timeoutSeconds)
  };
}

function providerSettingsToBackend(settings: ProviderSettings) {
  return {
    edge: {
      provider: settings.provider,
      base_url: settings.apiBaseUrl,
      api_path: settings.apiPath,
      model: settings.edgeModel,
      fallback_model: settings.fallbackModel,
      extra_headers: settings.extraHeaders,
      think: settings.think,
      timeout_seconds: numberFromDraft(settings.timeoutSeconds, defaultProviderSettings.timeoutSeconds),
      num_ctx: numberFromDraft(settings.numCtx, defaultProviderSettings.numCtx),
      num_predict: numberFromDraft(settings.numPredict, defaultProviderSettings.numPredict),
      temperature: numberFromDraft(settings.temperature, defaultProviderSettings.temperature)
    },
    embedding: {
      provider: settings.embeddingProvider,
      base_url: settings.embeddingApiBaseUrl,
      api_path: settings.embeddingApiPath,
      model: settings.embeddingModel,
      extra_headers: settings.embeddingExtraHeaders,
      timeout_seconds: numberFromDraft(settings.timeoutSeconds, defaultProviderSettings.timeoutSeconds)
    }
  };
}

function buildIndexStatusLabel(corpora: CorpusEntry[]) {
  if (!corpora.length) {
    return "empty";
  }
  if (corpora.some((corpus) => corpus.status === "failed")) {
    return "failed";
  }
  if (corpora.some((corpus) => corpus.status === "indexing" || corpus.status === "queued")) {
    return "indexing";
  }
  if (corpora.some((corpus) => corpus.status === "indexed")) {
    return "ready";
  }
  return "not indexed";
}

function buildPageMetrics(
  pageId: PageId,
  fallbackMetrics: Metric[],
  settings: ProviderSettings,
  corpora: CorpusEntry[],
  resolverProfiles: ResolverProfile[],
  queryRows: EvidenceRow[],
  graph: GraphPayload | null,
  acceptanceRuns: AcceptanceRun[],
  providerVerification: ProviderVerificationState
): Metric[] {
  if (pageId === "settings") {
    return buildSettingsMetrics(settings, providerVerification);
  }
  if (pageId === "corpus") {
    return [
      { label: "corpora", value: String(corpora.length), tone: "success" },
      { label: "files", value: sumFileCounts(corpora) },
      { label: "status", value: "editable", tone: "code" }
    ];
  }
  if (pageId === "resolver-profiles") {
    return [
      { label: "profiles", value: String(resolverProfiles.length) },
      { label: "enabled", value: String(resolverProfiles.filter((profile) => profile.enabled).length), tone: "success" },
      { label: "strategy", value: "config" }
    ];
  }
  if (pageId === "evidence-workbench" || pageId === "graph-explorer") {
    return [
      { label: "matches", value: String(queryRows.length), tone: "success" },
      { label: "graph edges", value: graph ? String(graph.edges.length) : "not returned" },
      { label: "query", value: "live", tone: "code" }
    ];
  }
  if (pageId === "acceptance-tests" && acceptanceRuns.length) {
    const activeRun = acceptanceRuns[0];
    return [
      { label: "passed", value: String(activeRun.passed), tone: "success" },
      { label: "partial", value: String(activeRun.partial ?? 0), tone: activeRun.partial ? "doc" : "neutral" },
      { label: "failed", value: String(activeRun.failed), tone: activeRun.failed ? "pdf" : "success" },
      { label: "queries", value: String(activeRun.queryCount), tone: "code" }
    ];
  }
  if (pageId === "acceptance-tests") {
    return [
      { label: "runs", value: "0" },
      { label: "passed", value: "0", tone: "neutral" },
      { label: "failed", value: "0", tone: "neutral" }
    ];
  }
  return fallbackMetrics;
}

function buildPageRows(
  pageId: PageId,
  fallbackRows: EvidenceRow[],
  settings: ProviderSettings,
  corpora: CorpusEntry[],
  resolverProfiles: ResolverProfile[],
  queryRows: EvidenceRow[],
  acceptanceRuns: AcceptanceRun[]
): EvidenceRow[] {
  if (pageId === "settings") {
    return buildSettingsEvidenceRows(settings);
  }
  if (pageId === "corpus") {
    return corpora.map((corpus) => ({
      source: "corpus",
      tone: corpus.id.includes("pdf") || corpus.include.includes("pdf") ? "pdf" : "code",
      symbol: corpus.id,
      relation: corpus.status ?? "not_indexed",
      score: corpus.fileCount,
      path: corpus.sourceRoot
    }));
  }
  if (pageId === "resolver-profiles") {
    return resolverProfiles.map((profile) => ({
      source: "profile",
      tone: profile.enabled ? "success" : "neutral",
      symbol: profile.id,
      relation: profile.enabled ? profile.strategy : "disabled",
      score: `${profile.wrappers.length} operator${profile.wrappers.length === 1 ? "" : "s"}`,
      path: profile.path
    }));
  }
  if (pageId === "evidence-workbench" || pageId === "graph-explorer") {
    return queryRows;
  }
  if (pageId === "acceptance-tests" && acceptanceRuns.length) {
    return acceptanceRuns.map((run) => ({
      source: "qa",
      tone: run.failed ? "pdf" : "success",
      symbol: run.id,
      relation: run.model,
      score: run.partial ? `${run.passed}+${run.partial}/${run.queryCount}` : `${run.passed}/${run.queryCount}`,
      path: run.artifactPath
    }));
  }
  if (pageId === "acceptance-tests") {
    return [];
  }
  return fallbackRows;
}

function buildSettingsMetrics(settings: ProviderSettings, providerVerification: ProviderVerificationState): Metric[] {
  return [
    { label: "provider", value: providerVerification, tone: providerVerification === "verified" ? "success" : "neutral" },
    { label: "edge model", value: settings.edgeModel || "unset", tone: providerVerification === "verified" ? "success" : "neutral" },
    { label: "think", value: settings.think ? "on" : "off", tone: settings.think ? "doc" : "success" },
    { label: "timeout", value: `${settings.timeoutSeconds || defaultProviderSettings.timeoutSeconds}s` }
  ];
}

function buildSettingsEvidenceRows(settings: ProviderSettings): EvidenceRow[] {
  return [
    {
      source: "provider",
      tone: "success",
      symbol: settings.edgeModel || "unset",
      relation: "semantic_edges",
      score: settings.provider,
      path: providerRequestEndpoint(settings)
    },
    {
      source: "provider",
      tone: "register",
      symbol: settings.embeddingModel || "unset",
      relation: "embedding",
      score: settings.embeddingProvider,
      path: `${settings.embeddingApiBaseUrl || defaultProviderSettings.embeddingApiBaseUrl}${settings.embeddingApiPath || defaultProviderSettings.embeddingApiPath}`
    }
  ];
}

function normalizeApiCorpus(corpus: ApiCorpusEntry): CorpusEntry {
  const include = Array.isArray(corpus.include) ? corpus.include.join(", ") : corpus.include;
  return {
    id: corpus.id,
    repo: corpus.repo ?? "local",
    sourceRoot: corpus.sourceRoot ?? corpus.source_root ?? corpus.id,
    include: include ?? "**/*",
    subfolders: formatSubfolderFilters(corpus.metadata?.subfolders),
    fileCount: String(corpus.fileCount ?? corpus.file_count ?? "api"),
    status: corpus.status ?? "not_indexed"
  };
}

function parseSubfolderFilters(value: string) {
  return value
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
    .flatMap((line) => {
      const [relativeRoot, includeText = ""] = line.split(/[:=]/, 2);
      const include = includeText.split(",").map((item) => item.trim()).filter(Boolean);
      return relativeRoot.trim()
        ? [{ relativeRoot: relativeRoot.trim(), include: include.length ? include : ["**/*"] }]
        : [];
    });
}

function formatSubfolderFilters(value: unknown) {
  if (!Array.isArray(value)) {
    return "";
  }
  return value
    .flatMap((item) => {
      if (!isObjectRecord(item)) {
        return [];
      }
      const relativeRoot = String(item.relative_root ?? item.relativeRoot ?? item.path ?? "").trim();
      if (!relativeRoot) {
        return [];
      }
      const include = Array.isArray(item.include) ? item.include.map(String).join(", ") : String(item.include ?? "**/*");
      return `${relativeRoot}: ${include}`;
    })
    .join("\n");
}

function normalizeApiResolverProfile(profile: ApiResolverProfile): ResolverProfile {
  const wrappers = profile.wrappers?.filter(Boolean) ?? [];
  const functionNormalization = profile.config?.graph?.function_normalization;
  const firstRule = functionNormalization?.rules?.find(
    (rule) => rule.id?.trim() || rule.match?.trim() || rule.canonical?.trim()
  );
  return {
    id: profile.id,
    wrapper: wrappers[0] ?? profile.id,
    wrappers,
    strategy: profile.language ?? "config",
    path: profile.path ?? `configs/resolvers/${profile.id}.yaml`,
    enabled: profile.enabled ?? true,
    functionNormalizationEnabled: functionNormalization?.enabled ?? false,
    conceptRuleId: firstRule?.id ?? defaultConceptRuleId,
    conceptMatch: firstRule?.match ?? defaultConceptMatch,
    conceptCanonical: firstRule?.canonical ?? defaultConceptCanonical
  };
}

function mergeResolverProfiles(base: ResolverProfile[], overrides: ResolverProfile[]) {
  const merged = new Map<string, ResolverProfile>();
  for (const profile of base) {
    merged.set(profile.id, profile);
  }
  for (const profile of overrides) {
    merged.set(profile.id, profile);
  }
  return Array.from(merged.values());
}

function normalizeApiEvidenceRow(row: EvidenceRow): EvidenceRow {
  return {
    source: row.source ?? "api",
    tone: row.tone ?? "neutral",
    symbol: row.symbol,
    target_symbol: row.target_symbol,
    relation: row.relation,
    score: String(row.score),
    path: row.path,
    snippet: row.snippet,
    resolved_chain: row.resolved_chain,
    source_type: row.source_type,
    entity_type: row.entity_type,
    corpus_id: row.corpus_id,
    line_start: row.line_start,
    line_end: row.line_end,
    page: row.page
  };
}

function normalizeAcceptanceRun(run: AcceptanceRun): AcceptanceRun {
  return {
    ...run,
    partial: run.partial ?? 0,
    details: (run.details ?? []).map(normalizeAcceptanceDetail),
    databaseHealth: (run.databaseHealth ?? []).map(normalizeAcceptanceDetail)
  };
}

function normalizeJobRun(job: JobRun): JobRun {
  return {
    id: Number(job.id),
    kind: String(job.kind ?? "job"),
    status: String(job.status ?? "unknown"),
    message: typeof job.message === "string" ? job.message : "",
    metadata: isObjectRecord(job.metadata) ? job.metadata : {},
    events: Array.isArray(job.events)
      ? job.events.map((event) => ({
          status: String(event.status ?? "unknown"),
          message: typeof event.message === "string" ? event.message : "",
          created_at: typeof event.created_at === "string" ? event.created_at : ""
        }))
      : []
  };
}

function jobLifecycle(job: JobRun) {
  const statuses = (job.events ?? []).map((event) => event.status).filter(Boolean);
  return statuses.length ? statuses.join(" -> ") : job.status;
}

function normalizeAcceptanceDetail(detail: Partial<AcceptanceDetail> & Record<string, unknown>): AcceptanceDetail {
  return {
    id: String(detail.id ?? "unknown"),
    status: String(detail.status ?? "unknown"),
    query: typeof detail.query === "string" ? detail.query : undefined,
    failureReasons: normalizeStringList(detail.failureReasons ?? detail.failure_reasons),
    missing: normalizeStringList(detail.missing),
    missingSurfaces: normalizeStringList(detail.missingSurfaces ?? detail.missing_surfaces),
    sourcePaths: normalizeStringList(detail.sourcePaths ?? detail.source_paths),
    sourceTypes: normalizeStringList(detail.sourceTypes ?? detail.source_types),
    retrievalSources: normalizeStringList(detail.retrievalSources ?? detail.retrieval_sources),
    rowCount: normalizeOptionalNumber(detail.rowCount ?? detail.row_count),
    graphEdgeCount: normalizeOptionalNumber(detail.graphEdgeCount ?? detail.graph_edge_count),
    edgeCount: normalizeOptionalNumber(detail.edgeCount ?? detail.edge_count),
    sourceHitCount: normalizeOptionalNumber(detail.sourceHitCount ?? detail.source_hit_count),
    surfaceResults: normalizeAcceptanceSurfaceResults(detail.surfaceResults ?? detail.surface_results),
    providerChecks: normalizeAcceptanceProviderChecks(detail.providerChecks ?? detail.provider_checks)
  };
}

function normalizeAcceptanceSurfaceResults(value: unknown): AcceptanceSurfaceResult[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((item): item is Record<string, unknown> => isObjectRecord(item))
    .map((item) => ({
      surface: String(item.surface ?? "surface"),
      transport: String(item.transport ?? "unknown"),
      status: String(item.status ?? "unknown"),
      dbPath: typeof item.dbPath === "string" ? item.dbPath : typeof item.db_path === "string" ? item.db_path : undefined,
      rowCount: normalizeOptionalNumber(item.rowCount ?? item.row_count),
      graphNodeCount: normalizeOptionalNumber(item.graphNodeCount ?? item.graph_node_count),
      graphEdgeCount: normalizeOptionalNumber(item.graphEdgeCount ?? item.graph_edge_count),
      message: typeof item.message === "string" ? item.message : undefined
    }));
}

function normalizeAcceptanceProviderChecks(value: unknown): AcceptanceDetail["providerChecks"] | undefined {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return undefined;
  }
  const checks = value as {
    embedding?: ProviderAcceptanceCheck;
    semanticEdge?: ProviderAcceptanceCheck;
    semantic_edge?: ProviderAcceptanceCheck;
  };
  return {
    embedding: normalizeProviderAcceptanceCheck(checks.embedding),
    semanticEdge: normalizeProviderAcceptanceCheck(checks.semanticEdge ?? checks.semantic_edge)
  };
}

function normalizeProviderAcceptanceCheck(check: unknown): ProviderAcceptanceCheck | undefined {
  if (!check || typeof check !== "object" || Array.isArray(check)) {
    return undefined;
  }
  const payload = check as Record<string, unknown>;
  return {
    status: typeof payload.status === "string" ? payload.status : undefined,
    provider: typeof payload.provider === "string" ? payload.provider : undefined,
    model: typeof payload.model === "string" ? payload.model : undefined,
    message: typeof payload.message === "string" ? payload.message : undefined
  };
}

function normalizeStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : [];
}

function normalizeOptionalNumber(value: unknown): number | undefined {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function evidenceRowKey(row: EvidenceRow): string {
  return `${row.source}:${row.symbol}:${row.relation}:${row.target_symbol ?? ""}:${row.path}:${row.line_start ?? ""}`;
}

function formatEvidenceSymbol(row: EvidenceRow): string {
  return row.target_symbol ? `${row.symbol} -> ${row.target_symbol}` : row.symbol;
}

function sourceToneForRow(row: EvidenceRow): SourceTone {
  const sourceType = String(row.source_type || row.source || "").toLowerCase();
  if (sourceType === "code" || sourceType === "register" || sourceType === "doc" || sourceType === "pdf") {
    return sourceType;
  }
  return row.tone;
}

function sourceLabelForRow(row: EvidenceRow): string {
  return String(row.source_type || row.source || "source").toLowerCase();
}

function formatEvidenceLocation(row: EvidenceRow): string {
  const parts = [row.path];
  if (row.page) {
    parts.push(`page ${row.page}`);
  } else if (row.line_start) {
    parts.push(row.line_end && row.line_end !== row.line_start ? `lines ${row.line_start}-${row.line_end}` : `line ${row.line_start}`);
  }
  return parts.filter(Boolean).join(" ");
}

function buildLiveInspectorChain(row: EvidenceRow): string[] {
  if (row.resolved_chain) {
    return row.resolved_chain.split(/\s*->\s*/).filter(Boolean);
  }
  if (row.target_symbol) {
    return [row.symbol, row.relation, row.target_symbol].filter(Boolean);
  }
  return [row.symbol, row.relation, row.path].filter(Boolean);
}

function buildLiveInspectorSections(row: EvidenceRow): InspectorDetailSection[] {
  const location = [row.path, row.line_start ? `line ${row.line_start}` : "", row.page ? `page ${row.page}` : ""]
    .filter(Boolean)
    .join(" ");
  return [
    {
      title: "Source Location",
      body: `${row.source_type ?? row.source} ${row.entity_type ?? "entity"} ${location}`.trim()
    },
    {
      title: "Source Preview",
      body: row.snippet || row.path
    }
  ];
}

function buildGraphNodeInspectorChain(node: WeightedGraphNode): string[] {
  return [
    String(node.kind ?? "node"),
    String(node.label ?? node.id),
    node.id
  ].filter(Boolean);
}

function buildGraphNodeInspectorSections(node: WeightedGraphNode): InspectorDetailSection[] {
  const attr = isObjectRecord(node.attr) ? node.attr : {};
  const sections: InspectorDetailSection[] = [
    {
      title: "Node Detail",
      body: [
        `kind=${node.kind ?? "unknown"}`,
        `weight=${formatNodeWeight(node.weight)}`,
        `in=${node.in?.length ?? 0}`,
        `out=${node.out?.length ?? 0}`
      ].join(" ")
    }
  ];
  const conceptImplementations = conceptImplementationLines(attr);
  if (isConceptFunctionNode(node) && conceptImplementations.length) {
    sections.push({
      title: "Concept Generated From",
      lines: conceptImplementations
    });
  }
  const sources = sourceRecordLines(attr.source);
  if (sources.length) {
    sections.push({
      title: "Source Records",
      lines: sources
    });
  }
  const metadata = compactMetadataLines(attr, [
    "function_name",
    "normalization_rule",
    "normalization_profile_id",
    "merge_status",
    "register_neighbor_overlap",
    "ip_block",
    "ip_version",
    "doc_kind"
  ]);
  if (metadata.length) {
    sections.push({
      title: "Metadata",
      lines: metadata
    });
  }
  return sections;
}

function buildLiveRelationshipLines(row: EvidenceRow, graph: GraphPayload | null): string[] {
  const lines = new Set<string>();
  if (row.resolved_chain) {
    lines.add(row.resolved_chain);
  }
  if (row.target_symbol) {
    lines.add(`${row.symbol} ${row.relation} ${row.target_symbol}`);
  }
  lines.add(`${row.symbol} ${row.relation} ${row.path}`);
  for (const edge of graph?.edges ?? []) {
    if (edge.src === row.symbol || edge.dst === row.symbol) {
      lines.add(`${edge.src} ${edge.relation} ${edge.dst}`);
    }
  }
  return Array.from(lines);
}

function buildSelectedNodeRelationshipLines(node: WeightedGraphNode, graph: GraphPayload, limit?: number): string[] {
  const previewLimit = Math.max(1, limit ?? graph.edges.length);
  const lines = graph.edges.flatMap((edge) => {
    if (edge.src !== node.id && edge.dst !== node.id) {
      return [];
    }
    const direction = edge.src === node.id ? "out" : "in";
    const provenance = graphEdgeProvenanceLabel(edge);
    return provenance
      ? [`${direction}: ${edge.src} ${edge.relation} ${edge.dst} [${provenance}]`]
      : [`${direction}: ${edge.src} ${edge.relation} ${edge.dst}`];
  });
  if (lines.length === 0) {
    return [`${node.id} has no visible relationships after current filters.`];
  }
  return lines.slice(0, previewLimit);
}

function isConceptFunctionNode(node: WeightedGraphNode): boolean {
  const attr = isObjectRecord(node.attr) ? node.attr : {};
  return node.kind === "function" && attr.is_concept === true;
}

function conceptImplementationLines(attr: Record<string, unknown>): string[] {
  const implementationRecords = Array.isArray(attr.concept_implementations)
    ? attr.concept_implementations.filter(isObjectRecord)
    : Array.isArray(attr.raw_implementations)
      ? attr.raw_implementations.filter(isObjectRecord)
      : [];
  const lines = implementationRecords.flatMap((item) => {
    const functionName = String(item.function_name ?? item.name ?? "").trim();
    if (!functionName) {
      return [];
    }
    const location = sourceLocationLabel(item);
    const version = [item.ip_block, item.ip_version].filter(Boolean).join(" ");
    return [`${functionName}${version ? ` (${version})` : ""}${location ? ` @ ${location}` : ""}`];
  });
  const rawFunctionNames = arrayOfStrings(attr.raw_function_names);
  for (const functionName of rawFunctionNames) {
    if (!lines.some((line) => line.startsWith(functionName))) {
      lines.push(functionName);
    }
  }
  const count = Number(attr.concept_implementation_count ?? attr.raw_function_names_count ?? attr.raw_implementation_count ?? lines.length);
  if (Number.isFinite(count) && count > lines.length) {
    lines.push(`+${count - lines.length} more implementations in the current graph payload`);
  }
  return lines;
}

function sourceRecordLines(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(isObjectRecord).map(sourceLocationLabel).filter(Boolean).slice(0, 8);
}

function compactMetadataLines(attr: Record<string, unknown>, keys: string[]): string[] {
  return keys.flatMap((key) => {
    const value = attr[key];
    if (value === undefined || value === null || value === "" || value === 0) {
      return [];
    }
    if (Array.isArray(value) && value.length === 0) {
      return [];
    }
    return [`${key}=${Array.isArray(value) ? value.map(String).join(", ") : String(value)}`];
  });
}

function sourceLocationLabel(record: Record<string, unknown>): string {
  const functionName = String(record.function_name ?? "").trim();
  const path = String(record.path ?? "").trim();
  const lineStart = record.line_start ?? record.lineStart;
  const lineEnd = record.line_end ?? record.lineEnd;
  const page = record.page;
  const location = [
    path,
    lineStart ? `line ${lineEnd && lineEnd !== lineStart ? `${lineStart}-${lineEnd}` : lineStart}` : "",
    page ? `page ${page}` : ""
  ].filter(Boolean).join(" ");
  if (location) {
    return location;
  }
  return functionName;
}

function arrayOfStrings(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map(String).map((item) => item.trim()).filter(Boolean);
}

function formatNodeWeight(value: unknown): string {
  const numeric = Number(value ?? 1);
  return Number.isFinite(numeric) ? numeric.toFixed(2) : "1.00";
}

function buildGraphRelationshipLines(graph: GraphPayload, emptyMessage: string, limit?: number): string[] {
  if (graph.edges.length === 0) {
    return [emptyMessage || "No graph relationships returned."];
  }
  const previewLimit = Math.max(1, limit ?? graph.edges.length);
  const relationshipOrder = [
    ...graph.edges.filter((edge) => edge.relation === "calls"),
    ...graph.edges.filter((edge) => edge.relation !== "calls")
  ];
  const seen = new Set<string>();
  return relationshipOrder.flatMap((edge) => {
    const provenance = graphEdgeProvenanceLabel(edge);
    const line = provenance
      ? `${edge.src} ${edge.relation} ${edge.dst} [${provenance}]`
      : `${edge.src} ${edge.relation} ${edge.dst}`;
    if (seen.has(line)) {
      return [];
    }
    seen.add(line);
    return [line];
  }).slice(0, previewLimit);
}

function sumFileCounts(corpora: CorpusEntry[]): string {
  const numeric = corpora.map((corpus) => Number(corpus.fileCount)).filter(Number.isFinite);
  if (numeric.length === 0) {
    return "unknown";
  }
  return String(numeric.reduce((sum, value) => sum + value, 0));
}

function chooseEmbeddingModel(modelNames: string[]): string {
  return (
    modelNames.find((name) => /embed|embedding|nomic|bge/i.test(name)) ??
    modelNames[0] ??
    defaultProviderSettings.embeddingModel
  );
}

function chooseEdgeModel(modelNames: string[], embeddingModel: string): string {
  const candidates = modelNames.filter((name) => name !== embeddingModel);
  return (
    candidates.find((name) => /^gemma/i.test(name)) ??
    candidates.find((name) => /^qwen/i.test(name)) ??
    candidates[0] ??
    defaultProviderSettings.edgeModel
  );
}

function providerRequestEndpoint(settings: ProviderSettings): string {
  const baseUrl = (settings.apiBaseUrl || defaultProviderSettings.apiBaseUrl).replace(/\/+$/, "");
  const path = settings.apiPath || defaultProviderSettings.apiPath;
  return `${baseUrl}${path.startsWith("/") ? path : `/${path}`}`;
}

function numberFromDraft(value: string, fallback: string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : Number(fallback);
}

function readStoredTheme(): Theme {
  if (typeof window === "undefined") {
    return defaultTheme;
  }

  try {
    const stored = window.localStorage.getItem(themeStorageKey);
    return isTheme(stored) ? stored : defaultTheme;
  } catch {
    return defaultTheme;
  }
}

function writeStoredTheme(theme: Theme) {
  try {
    window.localStorage.setItem(themeStorageKey, theme);
  } catch {
    // Ignore storage failures; the live page theme still updates.
  }
}

function isTheme(value: string | null): value is Theme {
  return value === "dark" || value === "light";
}

function ProviderSettingsPanel({
  acceptanceDbPath,
  draft,
  error,
  message,
  onAcceptanceDbPathChange,
  onChange,
  onDetectOllama,
  onRunAcceptance,
  onSave,
  runtimeConfig
}: {
  acceptanceDbPath: string;
  draft: ProviderSettingsDraft;
  error: string;
  message: string;
  onAcceptanceDbPathChange: (value: string) => void;
  onChange: (draft: ProviderSettingsDraft) => void;
  onDetectOllama: () => void;
  onRunAcceptance: () => void;
  onSave: () => void;
  runtimeConfig: RuntimeEdgeModelConfig;
}) {
  const update = <Key extends keyof ProviderSettingsDraft>(key: Key, value: ProviderSettingsDraft[Key]) => {
    onChange({ ...draft, [key]: value });
  };

  return (
    <Card className="provider-settings-panel" aria-label="Provider settings">
      <CardHeader className="provider-settings-header">
        <div>
          <CardTitle>Provider Runtime</CardTitle>
          <CardDescription>Model, API endpoint, and extra headers are saved to the workbench backend.</CardDescription>
        </div>
        <ToneBadge tone="success">{draft.provider}</ToneBadge>
      </CardHeader>
      <CardContent className="provider-settings-content">
        <FieldGroup className="provider-settings-grid">
        <Field>
          <FieldLabel>Edge provider</FieldLabel>
          <Select
            onValueChange={(value) => update("provider", value as ProviderSettings["provider"])}
            value={draft.provider}
          >
            <SelectTrigger aria-label="Provider">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ollama">Ollama</SelectItem>
              <SelectItem value="openai-compatible">OpenAI compatible</SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <Field>
          <FieldLabel>Edge API base URL</FieldLabel>
          <Input
            aria-label="Edge API base URL"
            onChange={(event) => update("apiBaseUrl", event.target.value)}
            value={draft.apiBaseUrl}
          />
        </Field>
        <Field>
          <FieldLabel>Edge API path</FieldLabel>
          <Input
            aria-label="Edge API path"
            onChange={(event) => update("apiPath", event.target.value)}
            value={draft.apiPath}
          />
        </Field>
        <Field>
          <FieldLabel>Edge model</FieldLabel>
          <Input
            aria-label="Edge model"
            onChange={(event) => update("edgeModel", event.target.value)}
            value={draft.edgeModel}
          />
        </Field>
        <Field>
          <FieldLabel>Fallback model</FieldLabel>
          <Input
            aria-label="Fallback model"
            onChange={(event) => update("fallbackModel", event.target.value)}
            value={draft.fallbackModel}
          />
        </Field>
        <Field>
          <FieldLabel>Embedding provider</FieldLabel>
          <Select
            onValueChange={(value) =>
              update("embeddingProvider", value as ProviderSettings["embeddingProvider"])
            }
            value={draft.embeddingProvider}
          >
            <SelectTrigger aria-label="Embedding provider">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ollama">Ollama</SelectItem>
              <SelectItem value="openai-compatible">OpenAI compatible</SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <Field>
          <FieldLabel>Embedding API base URL</FieldLabel>
          <Input
            aria-label="Embedding API base URL"
            onChange={(event) => update("embeddingApiBaseUrl", event.target.value)}
            value={draft.embeddingApiBaseUrl}
          />
        </Field>
        <Field>
          <FieldLabel>Embedding API path</FieldLabel>
          <Input
            aria-label="Embedding API path"
            onChange={(event) => update("embeddingApiPath", event.target.value)}
            value={draft.embeddingApiPath}
          />
        </Field>
        <Field>
          <FieldLabel>Embedding model</FieldLabel>
          <Input
            aria-label="Embedding model"
            onChange={(event) => update("embeddingModel", event.target.value)}
            value={draft.embeddingModel}
          />
        </Field>
        <Field>
          <FieldLabel>Timeout seconds</FieldLabel>
          <Input
            aria-label="Timeout seconds"
            inputMode="numeric"
            onChange={(event) => update("timeoutSeconds", event.target.value)}
            value={draft.timeoutSeconds}
          />
        </Field>
        <Field>
          <FieldLabel>Context tokens</FieldLabel>
          <Input
            aria-label="Context tokens"
            inputMode="numeric"
            onChange={(event) => update("numCtx", event.target.value)}
            value={draft.numCtx}
          />
        </Field>
        <Field>
          <FieldLabel>Prediction tokens</FieldLabel>
          <Input
            aria-label="Prediction tokens"
            inputMode="numeric"
            onChange={(event) => update("numPredict", event.target.value)}
            value={draft.numPredict}
          />
        </Field>
        <Field>
          <FieldLabel>Temperature</FieldLabel>
          <Input
            aria-label="Temperature"
            inputMode="decimal"
            onChange={(event) => update("temperature", event.target.value)}
            value={draft.temperature}
          />
        </Field>
        <Field className="provider-settings-field--toggle" orientation="horizontal">
          <Checkbox
            aria-label="Enable model thinking"
            checked={draft.think}
            onCheckedChange={(checked) => update("think", checked === true)}
          />
          <FieldContent>
            <FieldLabel>Enable model thinking</FieldLabel>
            <FieldDescription>Keep disabled for compact JSON edge generation unless a profile requires it.</FieldDescription>
          </FieldContent>
        </Field>
        <Field className="provider-settings-field--wide">
          <FieldLabel>Edge extra headers JSON</FieldLabel>
          <Textarea
            aria-label="Edge extra headers JSON"
            onChange={(event) => update("extraHeadersJson", event.target.value)}
            rows={4}
            value={draft.extraHeadersJson}
          />
        </Field>
        <Field className="provider-settings-field--wide">
          <FieldLabel>Embedding extra headers JSON</FieldLabel>
          <Textarea
            aria-label="Embedding extra headers JSON"
            onChange={(event) => update("embeddingExtraHeadersJson", event.target.value)}
            rows={4}
            value={draft.embeddingExtraHeadersJson}
          />
        </Field>
        <Field className="provider-settings-field--wide">
          <FieldLabel>AQ09 acceptance DB path</FieldLabel>
          <Input
            aria-label="AQ09 acceptance DB path"
            onChange={(event) => onAcceptanceDbPathChange(event.target.value)}
            value={acceptanceDbPath}
          />
        </Field>
      </FieldGroup>
      <div className="provider-settings-actions">
        <Button onClick={onDetectOllama} type="button" variant="secondary">
          Detect Ollama models
        </Button>
        <Button onClick={onSave} type="button">
          Save provider settings
        </Button>
        <Button onClick={onRunAcceptance} type="button" variant="secondary">
          Run AQ09 acceptance
        </Button>
        {message ? <span className="settings-feedback">{message}</span> : null}
        {error ? <span className="settings-feedback settings-feedback--error">{error}</span> : null}
      </div>
      <div className="runtime-config">
        <div className="runtime-config__header">
          <span>Edge runner config</span>
          <ToneBadge tone="code">JSON</ToneBadge>
        </div>
        <pre aria-label="Runtime config JSON" data-testid="runtime-config-preview">
          {JSON.stringify(runtimeConfig, null, 2)}
        </pre>
      </div>
      </CardContent>
    </Card>
  );
}

function CorpusEditor({
  draft,
  message,
  onAdd,
  onChange
}: {
  draft: CorpusEntry;
  message: string;
  onAdd: () => void;
  onChange: (draft: CorpusEntry) => void;
}) {
  const update = <Key extends keyof CorpusEntry>(key: Key, value: CorpusEntry[Key]) => {
    onChange({ ...draft, [key]: value });
  };

  return (
    <Card className="provider-settings-panel" aria-label="Corpus editor">
      <CardHeader className="provider-settings-header">
        <div>
          <CardTitle>Corpus Registry</CardTitle>
          <CardDescription>Add local or remote corpora before indexing them into the evidence store.</CardDescription>
        </div>
        <ToneBadge tone="code">editable</ToneBadge>
      </CardHeader>
      <CardContent className="provider-settings-content">
      <FieldGroup className="provider-settings-grid">
        <Field>
          <FieldLabel>Corpus id</FieldLabel>
          <Input aria-label="Corpus id" onChange={(event) => update("id", event.target.value)} value={draft.id} />
        </Field>
        <Field>
          <FieldLabel>Repository URL</FieldLabel>
          <Input
            aria-label="Repository URL"
            onChange={(event) => update("repo", event.target.value)}
            value={draft.repo}
          />
        </Field>
        <Field>
          <FieldLabel>Source root</FieldLabel>
          <Input
            aria-label="Source root"
            onChange={(event) => update("sourceRoot", event.target.value)}
            value={draft.sourceRoot}
          />
        </Field>
        <Field className="provider-settings-field--wide">
          <FieldLabel>Include globs</FieldLabel>
          <Input
            aria-label="Include globs"
            onChange={(event) => update("include", event.target.value)}
            value={draft.include}
          />
        </Field>
        <Field className="provider-settings-field--wide">
          <FieldLabel>Subfolder filters</FieldLabel>
          <Textarea
            aria-label="Subfolder filters"
            onChange={(event) => update("subfolders", event.target.value)}
            placeholder={"drivers/gpu/drm/amd/amdgpu: **/*.c, **/*.h\ndrivers/gpu/drm/amd/include/asic_reg: **/*.h"}
            value={draft.subfolders}
          />
          <FieldDescription>One relative subfolder per line, followed by optional include globs.</FieldDescription>
        </Field>
      </FieldGroup>
      <div className="provider-settings-actions">
        <Button onClick={onAdd} type="button">
          Add corpus
        </Button>
        {message ? <span className="settings-feedback">{message}</span> : null}
      </div>
      </CardContent>
    </Card>
  );
}

function ResolverProfileSelector({
  onToggle,
  profiles,
  selectedIds
}: {
  onToggle: (profileId: string, selected: boolean) => void;
  profiles: ResolverProfile[];
  selectedIds: string[];
}) {
  const enabledProfiles = profiles.filter((profile) => profile.enabled);
  return (
    <Card className="provider-settings-panel" aria-label="Index resolver profiles">
      <CardHeader className="provider-settings-header">
        <div>
          <CardTitle>Index Resolver Profiles</CardTitle>
          <CardDescription>Select the YAML-backed resolvers for the next corpus index job.</CardDescription>
        </div>
        <ToneBadge tone="code">{enabledProfiles.length} enabled</ToneBadge>
      </CardHeader>
      <CardContent className="provider-settings-content">
        {enabledProfiles.length ? (
          <FieldGroup className="resolver-profile-selection" data-slot="checkbox-group">
            {enabledProfiles.map((profile) => {
              const checkboxId = `resolver-profile-${profile.id}`;
              return (
                <Field className="provider-settings-field--toggle" key={profile.id} orientation="horizontal">
                  <Checkbox
                    aria-label={`Use resolver profile ${profile.id}`}
                    checked={selectedIds.includes(profile.id)}
                    id={checkboxId}
                    onCheckedChange={(checked) => onToggle(profile.id, checked === true)}
                  />
                  <FieldContent>
                    <FieldLabel htmlFor={checkboxId}>{profile.id}</FieldLabel>
                    <FieldDescription>
                      {profile.strategy} · {profile.wrappers.join(", ") || "no wrappers"} · {profile.path}
                    </FieldDescription>
                  </FieldContent>
                </Field>
              );
            })}
          </FieldGroup>
        ) : (
          <p className="settings-feedback">No enabled YAML resolver profiles are available.</p>
        )}
      </CardContent>
    </Card>
  );
}

function ResolverProfileEditor({
  draft,
  message,
  onAdd,
  onChange,
  onValidate,
  onValidateSourceChange,
  profiles,
  validateSource
}: {
  draft: ResolverProfile;
  message: string;
  onAdd: () => void;
  onChange: (draft: ResolverProfile) => void;
  onValidate: () => void;
  onValidateSourceChange: (source: string) => void;
  profiles: ResolverProfile[];
  validateSource: string;
}) {
  const [selectedProfileId, setSelectedProfileId] = useState(draft.id);
  const update = <Key extends keyof ResolverProfile>(key: Key, value: ResolverProfile[Key]) => {
    const next = { ...draft, [key]: value };
    if (key === "id") {
      const previousDefaultPath =
        !draft.path ||
        draft.path === "configs/resolvers/initial.yaml" ||
        draft.path === `configs/resolvers/${draft.id}.yaml`;
      const nextId = String(value).trim();
      if (previousDefaultPath && nextId) {
        next.path = `configs/resolvers/${nextId}.yaml`;
      }
    }
    onChange(next);
  };
  const loadSelectedProfile = () => {
    const selectedProfile = profiles.find((profile) => profile.id === selectedProfileId);
    if (!selectedProfile) {
      return;
    }
    onChange({
      ...selectedProfile,
      wrapper: selectedProfile.wrapper || selectedProfile.wrappers[0] || selectedProfile.id,
      wrappers: selectedProfile.wrappers.length
        ? selectedProfile.wrappers
        : [selectedProfile.wrapper].filter(Boolean)
    });
  };

  return (
    <Card className="provider-settings-panel" aria-label="Resolver profile editor">
      <CardHeader className="provider-settings-header">
        <div>
          <CardTitle>Resolver Profiles</CardTitle>
          <CardDescription>Configure wrapper names and language strategies without changing resolver code.</CardDescription>
        </div>
        <ToneBadge tone="code">config driven</ToneBadge>
      </CardHeader>
      <CardContent className="provider-settings-content">
      <FieldGroup className="provider-settings-grid">
        <Field>
          <FieldLabel>Existing profile</FieldLabel>
          <Select onValueChange={setSelectedProfileId} value={selectedProfileId}>
            <SelectTrigger aria-label="Existing resolver profile">
              <SelectValue placeholder="Choose profile" />
            </SelectTrigger>
            <SelectContent>
              {profiles.map((profile) => (
                <SelectItem key={profile.id} value={profile.id}>
                  {profile.id}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field>
          <FieldLabel>Profile action</FieldLabel>
          <Button onClick={loadSelectedProfile} type="button" variant="secondary">
            Load resolver profile
          </Button>
        </Field>
        <Field>
          <FieldLabel>Profile id</FieldLabel>
          <Input aria-label="Profile id" onChange={(event) => update("id", event.target.value)} value={draft.id} />
        </Field>
        <Field>
          <FieldLabel>Wrapper symbol</FieldLabel>
          <Input
            aria-label="Wrapper symbol"
            onChange={(event) => update("wrapper", event.target.value)}
            value={draft.wrapper}
          />
        </Field>
        <Field>
          <FieldLabel>Language strategy</FieldLabel>
          <Input
            aria-label="Language strategy"
            onChange={(event) => update("strategy", event.target.value)}
            value={draft.strategy}
          />
        </Field>
        <Field className="provider-settings-field--wide">
          <FieldLabel>Config path</FieldLabel>
          <Input
            aria-label="Config path"
            onChange={(event) => update("path", event.target.value)}
            value={draft.path}
          />
        </Field>
        <Field className="provider-settings-field--toggle" orientation="horizontal">
          <Checkbox
            aria-label="Enable resolver profile"
            checked={draft.enabled}
            onCheckedChange={(checked) => update("enabled", checked === true)}
          />
          <FieldContent>
            <FieldLabel>Enable resolver profile</FieldLabel>
            <FieldDescription>Only enabled profiles participate in symbol resolution.</FieldDescription>
          </FieldContent>
        </Field>
        <Field className="provider-settings-field--toggle" orientation="horizontal">
          <Checkbox
            aria-label="Enable concept normalization"
            checked={draft.functionNormalizationEnabled}
            onCheckedChange={(checked) => update("functionNormalizationEnabled", checked === true)}
          />
          <FieldContent>
            <FieldLabel>Enable concept normalization</FieldLabel>
          </FieldContent>
        </Field>
        <Field>
          <FieldLabel>Concept rule id</FieldLabel>
          <Input
            aria-label="Concept rule id"
            onChange={(event) => update("conceptRuleId", event.target.value)}
            value={draft.conceptRuleId}
          />
        </Field>
        <Field className="provider-settings-field--wide">
          <FieldLabel>Concept match regex</FieldLabel>
          <Input
            aria-label="Concept match regex"
            onChange={(event) => update("conceptMatch", event.target.value)}
            value={draft.conceptMatch}
          />
        </Field>
        <Field className="provider-settings-field--wide">
          <FieldLabel>Concept canonical name</FieldLabel>
          <Input
            aria-label="Concept canonical name"
            onChange={(event) => update("conceptCanonical", event.target.value)}
            value={draft.conceptCanonical}
          />
        </Field>
        <Field className="provider-settings-field--wide">
          <FieldLabel>Validation source</FieldLabel>
          <Textarea
            aria-label="Validation source"
            onChange={(event) => onValidateSourceChange(event.target.value)}
            rows={3}
            value={validateSource}
          />
        </Field>
      </FieldGroup>
      <div className="provider-settings-actions">
        <Button onClick={onAdd} type="button">
          Save resolver profile
        </Button>
        <Button onClick={onValidate} type="button" variant="secondary">
          Validate resolver profile
        </Button>
        {message ? <span className="settings-feedback">{message}</span> : null}
      </div>
      </CardContent>
    </Card>
  );
}

function JobRunsPanel({ jobs }: { jobs: JobRun[] }) {
  const visibleJobs = jobs.slice(0, 4);
  return (
    <Card className="inspector-card" data-testid="job-runs-panel">
      <CardHeader>
        <CardTitle>Index Jobs</CardTitle>
        <CardDescription>Durable job lifecycle from the local SQLite store.</CardDescription>
      </CardHeader>
      <CardContent>
        {visibleJobs.length ? (
          <div className="job-run-list">
            {visibleJobs.map((job) => (
              <div className="job-run" key={job.id}>
                <div className="job-run__header">
                  <strong>job {job.id}</strong>
                  <Badge>{job.status}</Badge>
                </div>
                <p>
                  <code>{job.kind}: {job.message || "no message"}</code>
                </p>
                <p>
                  <code>{jobLifecycle(job)}</code>
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p>
            <code>No index jobs returned.</code>
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function ImpactHopControl({
  level,
  onChange
}: {
  level: number;
  onChange: (level: number) => void;
}) {
  const clampedLevel = clampGraphHopLevel(level);
  const impactStyle = { "--impact-color": impactColorForHopLevel(clampedLevel) } as CSSProperties;
  return (
    <section
      aria-label="Impact hop level"
      className="impact-hop-control"
      data-impact-level={clampedLevel}
      style={impactStyle}
    >
      <div className="impact-hop-control__header">
        <span>Impact level</span>
        <strong>{clampedLevel} hop{clampedLevel === 1 ? "" : "s"}</strong>
      </div>
      <Slider
        aria-label="Impact hop level"
        max={graphHopMax}
        min={graphHopMin}
        onValueChange={([value]) => onChange(clampGraphHopLevel(Number(value ?? defaultGraphHopLevel)))}
        step={1}
        value={[clampedLevel]}
      />
      <div className="impact-hop-control__scale" aria-hidden="true">
        <span>{graphHopMin}</span>
        <span>{graphHopMax}</span>
      </div>
    </section>
  );
}

function GlobalNetworkGraph({
  emptyMessage,
  functionView,
  graph,
  impactLevel,
  limits,
  loadedEdgeBudget,
  onFunctionViewChange,
  onLoadedEdgeBudgetChange,
  onNodeSelect,
  selectedNodeId,
  testId
}: {
  emptyMessage?: string;
  functionView: GraphFunctionView;
  graph: GraphPayload | null;
  impactLevel: number;
  limits: WorkbenchLimits;
  loadedEdgeBudget: number | null;
  onFunctionViewChange: (value: GraphFunctionView) => void;
  onLoadedEdgeBudgetChange: (value: number | null) => void;
  onNodeSelect: (node: WeightedGraphNode) => void;
  selectedNodeId: string;
  testId: string;
}) {
  const graphData = buildGraphData(graph);
  const impactStyle = { "--graph-impact-color": impactColorForHopLevel(impactLevel) } as CSSProperties;
  const filterOptions = useMemo(() => graphFilterOptions(graphData.edges), [graphData.edges]);
  const [selectedRelations, setSelectedRelations] = useState<string[]>([]);
  const [selectedStages, setSelectedStages] = useState<string[]>([]);
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [minEdgeWeight, setMinEdgeWeight] = useState<number | null>(null);
  const [maxNodes, setMaxNodes] = useState<number | null>(null);
  const [maxEdges, setMaxEdges] = useState<number | null>(null);
  const relationOptionKey = filterOptions.relations.map((option) => option.value).join("\u0000");
  const stageOptionKey = filterOptions.stages.map((option) => option.value).join("\u0000");
  const sourceOptionKey = filterOptions.sources.map((option) => option.value).join("\u0000");
  useEffect(() => {
    setSelectedRelations((current) => reconcileGraphFilterSelection(current, filterOptions.relations));
  }, [relationOptionKey]);
  useEffect(() => {
    setSelectedStages((current) => reconcileGraphFilterSelection(current, filterOptions.stages));
  }, [stageOptionKey]);
  useEffect(() => {
    setSelectedSources((current) => reconcileGraphFilterSelection(current, filterOptions.sources));
  }, [sourceOptionKey]);
  const filteredGraphData = useMemo(
    () =>
      filterGraphDataByControls(graphData, {
        relations: selectedRelations,
        stages: selectedStages,
        sources: selectedSources
      }),
    [graphData, selectedRelations, selectedStages, selectedSources]
  );
  const isEmpty = filteredGraphData.nodes.length === 0;
  const effectiveMinEdgeWeight = minEdgeWeight ?? limits.graph?.minimumEdgeWeight ?? 0;
  const effectiveMaxNodes = maxNodes ?? limits.graph?.visibleNodeBudget ?? filteredGraphData.nodes.length;
  const effectiveMaxEdges = maxEdges ?? limits.graph?.visibleEdgeBudget ?? filteredGraphData.edges.length;
  const summaryLimit = Math.max(1, limits.graph?.accessibilitySummaryLimit ?? (filteredGraphData.nodes.length || 1));
  const layerSummary = graphLayerSummary(filteredGraphData.edges);
  const provenanceSummary = graphProvenanceSummary(filteredGraphData.edges);

  return (
    <div
      className="network-preview network-preview--global"
      data-impact-level={impactLevel}
      data-testid={testId}
      style={impactStyle}
    >
      <div className="network-preview__header">
        <span>Global Relation Graph</span>
        <ToneBadge tone="code">weighted connections</ToneBadge>
        {layerSummary ? <ToneBadge tone="success">layers {layerSummary}</ToneBadge> : null}
        {provenanceSummary ? <ToneBadge tone="code">provenance {provenanceSummary}</ToneBadge> : null}
      </div>
      <GraphDisplayControls
        edgeTotal={filteredGraphData.edges.length}
        filterOptions={filterOptions}
        loadedEdgeBudget={loadedEdgeBudget}
        maxEdgeBudget={limits.graph?.maxEdgeBudget}
        maxEdges={effectiveMaxEdges}
        maxNodes={effectiveMaxNodes}
        minEdgeWeight={effectiveMinEdgeWeight}
        nodeTotal={filteredGraphData.nodes.length}
        functionView={functionView}
        onFunctionViewChange={onFunctionViewChange}
        onLoadedEdgeBudgetChange={onLoadedEdgeBudgetChange}
        onMaxEdgesChange={setMaxEdges}
        onMaxNodesChange={setMaxNodes}
        onMinEdgeWeightChange={setMinEdgeWeight}
        onToggleFilter={(group, value) => {
          if (group === "relation") {
            setSelectedRelations((current) => toggleGraphFilterValue(current, value));
          } else if (group === "stage") {
            setSelectedStages((current) => toggleGraphFilterValue(current, value));
          } else {
            setSelectedSources((current) => toggleGraphFilterValue(current, value));
          }
        }}
        selectedRelations={selectedRelations}
        selectedSources={selectedSources}
        selectedStages={selectedStages}
      />
      {isEmpty ? (
        <div className="network-empty" role="status">
          <code>{emptyMessage || "No graph data returned."}</code>
        </div>
      ) : (
        <WeightedForceGraph
          graph={filteredGraphData}
          maxEdges={effectiveMaxEdges}
          maxNodes={effectiveMaxNodes}
          minEdgeWeight={effectiveMinEdgeWeight}
          onNodeSelect={onNodeSelect}
          selectedNodeId={selectedNodeId}
          summaryLimit={summaryLimit}
        />
      )}
    </div>
  );
}

function graphLayerSummary(edges: Array<{ stage?: string }>): string {
  const counts = new Map<string, number>();
  for (const edge of edges) {
    const stage = graphEdgeStage(edge);
    counts.set(stage, (counts.get(stage) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([stage, count]) => `${stage}: ${count}`)
    .join(" ");
}

function graphProvenanceSummary(edges: GraphPayload["edges"]): string {
  const labels = new Set<string>();
  for (const edge of edges) {
    const label = graphEdgeProvenanceLabel(edge);
    if (label) {
      labels.add(label);
    }
  }
  return Array.from(labels).slice(0, 4).join(" ");
}

function graphFilterOptions(edges: GraphPayload["edges"]): {
  relations: GraphFilterOption[];
  stages: GraphFilterOption[];
  sources: GraphFilterOption[];
} {
  const relations = new Map<string, number>();
  const stages = new Map<string, number>();
  const sources = new Map<string, number>();
  for (const edge of edges) {
    incrementGraphOption(relations, edge.relation || "relates_to");
    incrementGraphOption(stages, graphEdgeStage(edge));
    for (const source of graphEdgeSourceValues(edge)) {
      incrementGraphOption(sources, source);
    }
  }
  return {
    relations: graphOptionsFromCounts(relations),
    stages: graphOptionsFromCounts(stages),
    sources: graphOptionsFromCounts(sources)
  };
}

function filterGraphDataByControls(
  graph: GraphPayload,
  filters: { relations: string[]; stages: string[]; sources: string[] }
): GraphPayload {
  const edges = graph.edges.filter((edge) => {
    if (!graphFilterMatches([edge.relation], filters.relations)) {
      return false;
    }
    if (!graphFilterMatches([graphEdgeStage(edge)], filters.stages)) {
      return false;
    }
    return graphFilterMatches(graphEdgeSourceValues(edge), filters.sources);
  });
  const nodeIds = new Set(edges.flatMap((edge) => [edge.src, edge.dst]));
  return {
    nodes: edges.length ? graph.nodes.filter((node) => nodeIds.has(node.id)) : graph.nodes,
    edges
  };
}

function reconcileGraphFilterSelection(current: string[], options: GraphFilterOption[]): string[] {
  const values = options.map((option) => option.value);
  if (values.length === 0) {
    return [];
  }
  if (current.length === 0) {
    return values;
  }
  const valueSet = new Set(values);
  const next = current.filter((value) => valueSet.has(value));
  if (next.length === 0) {
    return values;
  }
  return sameStringList(current, next) ? current : next;
}

function toggleGraphFilterValue(current: string[], value: string): string[] {
  if (!current.includes(value)) {
    return [...current, value].sort((left, right) => left.localeCompare(right));
  }
  if (current.length <= 1) {
    return current;
  }
  return current.filter((candidate) => candidate !== value);
}

function graphFilterMatches(values: string[], selected: string[]): boolean {
  return selected.length === 0 || values.some((value) => selected.includes(value));
}

function graphOptionsFromCounts(counts: Map<string, number>): GraphFilterOption[] {
  return Array.from(counts.entries())
    .map(([value, count]) => ({ value, count }))
    .sort((left, right) => left.value.localeCompare(right.value));
}

function incrementGraphOption(counts: Map<string, number>, value: string) {
  const key = value.trim() || "unspecified";
  counts.set(key, (counts.get(key) ?? 0) + 1);
}

function graphEdgeStage(edge: { stage?: string }): string {
  return (edge.stage || "unspecified").trim() || "unspecified";
}

function graphEdgeSourceValues(edge: GraphPayload["edges"][number]): string[] {
  const values: string[] = [];
  if (typeof edge.source === "string") {
    values.push(edge.source);
  }
  if (Array.isArray(edge.sources)) {
    for (const source of edge.sources) {
      if (typeof source === "string") {
        values.push(source);
      } else if (source && typeof source === "object") {
        values.push(...stringValuesFromUnknown(source.source, source.provider, source.extractor));
      }
    }
  }
  return dedupeStrings(values).length > 0 ? dedupeStrings(values) : ["unspecified"];
}

function graphEdgeProvenanceLabel(edge: GraphPayload["edges"][number]): string {
  const attr = isObjectRecord(edge.attr) ? edge.attr : {};
  const sourceRecords = recordValuesFromUnknown(attr.source, attr.sources);
  const providers = dedupeStrings(
    stringValuesFromUnknown(
      attr.provider,
      attr.providers,
      ...sourceRecords.flatMap((source) => [source.provider, source.providers])
    )
  );
  const models = dedupeStrings(
    stringValuesFromUnknown(
      attr.model,
      attr.models,
      ...sourceRecords.flatMap((source) => [source.model, source.models])
    )
  );
  const jobIds = dedupeStrings(
    stringValuesFromUnknown(
      attr.job_id,
      attr.job_ids,
      ...sourceRecords.flatMap((source) => [source.job_id, source.job_ids])
    )
  );
  const sources = graphEdgeSourceValues(edge).filter((source) => source !== "unspecified");
  const providerModel =
    providers[0] && models[0] ? `${providers[0]}/${models[0]}` : providers[0] || models[0] || "";
  const source = sources.find((candidate) => candidate !== providers[0]);
  const dispatch = typeof attr.dispatch === "string" ? attr.dispatch : "";
  const candidateCount = Number(attr.callback_candidate_count ?? 0);
  const dispatchLabel = dispatch
    ? `${dispatch === "ambiguous" ? "dynamic dispatch" : dispatch}${candidateCount > 0 ? ` ${candidateCount} candidates` : ""}`
    : "";
  return [providerModel, jobIds[0] ? `job ${jobIds[0]}` : "", source ? `source ${source}` : "", dispatchLabel]
    .filter(Boolean)
    .join(" ");
}

function stringValuesFromUnknown(...values: unknown[]): string[] {
  return values.flatMap((value) => {
    if (value === "" || value === null || value === undefined) {
      return [];
    }
    if (Array.isArray(value)) {
      return value.map((item) => String(item)).filter(Boolean);
    }
  return [String(value)];
  });
}

function recordValuesFromUnknown(...values: unknown[]): Record<string, unknown>[] {
  return values.flatMap((value) => {
    if (Array.isArray(value)) {
      return value.filter(isObjectRecord);
    }
    return isObjectRecord(value) ? [value] : [];
  });
}

function dedupeStrings(values: string[]): string[] {
  const seen = new Set<string>();
  return values.flatMap((value) => {
    const trimmed = value.trim();
    if (!trimmed || seen.has(trimmed)) {
      return [];
    }
    seen.add(trimmed);
    return [trimmed];
  });
}

function sameStringList(left: string[], right: string[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function clampGraphHopLevel(value: number): number {
  const parsed = Number.isFinite(value) ? Math.round(value) : defaultGraphHopLevel;
  return Math.max(graphHopMin, Math.min(graphHopMax, parsed));
}

function impactColorForHopLevel(level: number): string {
  const clamped = clampGraphHopLevel(level);
  const ratio = (clamped - graphHopMin) / (graphHopMax - graphHopMin);
  const hue = Math.round(152 - ratio * 140);
  return `hsl(${hue} 82% 43%)`;
}

function GraphDisplayControls({
  edgeTotal,
  filterOptions,
  functionView,
  loadedEdgeBudget,
  maxEdgeBudget,
  maxEdges,
  maxNodes,
  minEdgeWeight,
  nodeTotal,
  onFunctionViewChange,
  onLoadedEdgeBudgetChange,
  onMaxEdgesChange,
  onMaxNodesChange,
  onMinEdgeWeightChange,
  onToggleFilter,
  selectedRelations,
  selectedSources,
  selectedStages
}: {
  edgeTotal: number;
  filterOptions: {
    relations: GraphFilterOption[];
    stages: GraphFilterOption[];
    sources: GraphFilterOption[];
  };
  functionView: GraphFunctionView;
  loadedEdgeBudget: number | null;
  maxEdgeBudget?: number;
  maxEdges: number;
  maxNodes: number;
  minEdgeWeight: number;
  nodeTotal: number;
  onFunctionViewChange: (value: GraphFunctionView) => void;
  onLoadedEdgeBudgetChange: (value: number | null) => void;
  onMaxEdgesChange: (value: number) => void;
  onMaxNodesChange: (value: number) => void;
  onMinEdgeWeightChange: (value: number) => void;
  onToggleFilter: (group: GraphFilterGroup, value: string) => void;
  selectedRelations: string[];
  selectedSources: string[];
  selectedStages: string[];
}) {
  const nodeMax = Math.max(nodeTotal || 1, maxNodes || 1);
  const edgeMax = Math.max(edgeTotal || 1, maxEdges || 1);
  const sourceMax = Math.max(maxEdgeBudget ?? 1, loadedEdgeBudget ?? 1, edgeTotal || 1);
  const sourceStep = Math.max(1, Math.ceil(sourceMax / 100));
  const visibleNodeStep = Math.max(1, Math.ceil(nodeMax / 100));
  const visibleEdgeStep = Math.max(1, Math.ceil(edgeMax / 100));

  return (
    <div className="graph-controls" aria-label="Graph display controls">
      <label className="graph-control">
        <span>Function view</span>
        <Select value={functionView} onValueChange={(value) => onFunctionViewChange(value as GraphFunctionView)}>
          <SelectTrigger aria-label="Function view">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="concept">Concept</SelectItem>
            <SelectItem value="implementation">Implementation</SelectItem>
          </SelectContent>
        </Select>
      </label>
      <label className="graph-control">
        <span>Loaded edge budget</span>
        <strong>{loadedEdgeBudget ?? "config"} / {sourceMax}</strong>
        <Slider
          aria-label="Loaded edge budget"
          max={sourceMax}
          min={1}
          onValueChange={([value]) => onLoadedEdgeBudgetChange(Math.max(1, Math.round(Number(value ?? 1))))}
          step={sourceStep}
          value={[Math.min(loadedEdgeBudget ?? sourceMax, sourceMax)]}
        />
      </label>
      <label className="graph-control">
        <span>Minimum edge weight</span>
        <strong>{minEdgeWeight.toFixed(2)}</strong>
        <Slider
          aria-label="Minimum edge weight"
          max={1}
          min={0}
          onValueChange={([value]) => onMinEdgeWeightChange(Number(value ?? 0))}
          step={0.05}
          value={[minEdgeWeight]}
        />
      </label>
      <label className="graph-control">
        <span>Visible nodes</span>
        <strong>{Math.min(maxNodes, nodeTotal || maxNodes)} visible / {nodeTotal} loaded</strong>
        <Slider
          aria-label="Visible nodes"
          max={nodeMax}
          min={1}
          onValueChange={([value]) => onMaxNodesChange(Math.max(1, Math.round(Number(value ?? 1))))}
          step={visibleNodeStep}
          value={[Math.min(maxNodes, nodeMax)]}
        />
      </label>
      <label className="graph-control">
        <span>Visible edges</span>
        <strong>{Math.min(maxEdges, edgeTotal || maxEdges)} visible / {edgeTotal} loaded</strong>
        <Slider
          aria-label="Visible edges"
          max={edgeMax}
          min={1}
          onValueChange={([value]) => onMaxEdgesChange(Math.max(1, Math.round(Number(value ?? 1))))}
          step={visibleEdgeStep}
          value={[Math.min(maxEdges, edgeMax)]}
        />
      </label>
      <GraphFilterChecklist
        group="relation"
        label="Relations"
        options={filterOptions.relations}
        selected={selectedRelations}
        onToggle={onToggleFilter}
      />
      <GraphFilterChecklist
        group="stage"
        label="Stages"
        options={filterOptions.stages}
        selected={selectedStages}
        onToggle={onToggleFilter}
      />
      <GraphFilterChecklist
        group="source"
        label="Sources"
        options={filterOptions.sources}
        selected={selectedSources}
        onToggle={onToggleFilter}
      />
    </div>
  );
}

function GraphFilterChecklist({
  group,
  label,
  onToggle,
  options,
  selected
}: {
  group: GraphFilterGroup;
  label: string;
  onToggle: (group: GraphFilterGroup, value: string) => void;
  options: GraphFilterOption[];
  selected: string[];
}) {
  if (options.length === 0) {
    return null;
  }
  return (
    <div className="graph-filter-group" aria-label={`Graph ${group} filters`}>
      <span>{label}</span>
      <div className="graph-filter-options">
        {options.map((option) => (
          <label className="graph-filter-option" key={option.value}>
            <Checkbox
              aria-label={`Graph ${group} ${option.value}`}
              checked={selected.length === 0 || selected.includes(option.value)}
              onCheckedChange={() => onToggle(group, option.value)}
            />
            <span>{option.value}</span>
            <strong>{option.count}</strong>
          </label>
        ))}
      </div>
    </div>
  );
}

function buildGraphData(graph: GraphPayload | null): GraphPayload {
  if (graph) {
    return sanitizeGraphPayload(graph) ?? { nodes: [], edges: [] };
  }
  return { nodes: [], edges: [] };
}

const allowedGraphKinds = new Set(["function", "register", "doc"]);
const allowedGraphRelations = new Set([
  "reads",
  "writes",
  "sets_field",
  "maps_base",
  "calls",
  "contains",
  "documents",
  "relates_to",
  "depends_on",
  "configures",
  "resets"
]);

function sanitizeGraphPayload(graph: GraphPayload | null | undefined): GraphPayload | null {
  if (!graph) {
    return null;
  }
  const nodes = (Array.isArray(graph.nodes) ? graph.nodes : [])
    .flatMap((node) => {
      const graphKind = normalizeGraphKind(node.kind);
      if (!node.id || !graphKind || !allowedGraphKinds.has(graphKind.kind)) {
        return [];
      }
      const attr = isObjectRecord(node.attr) ? { ...node.attr } : {};
      if (graphKind.docKind && !attr.doc_kind) {
        attr.doc_kind = graphKind.docKind;
      }
      if (!Array.isArray(attr.source)) {
        attr.source = [unknownSourceRecord()];
      }
      return [{
        ...node,
        id: String(node.id),
        kind: graphKind.kind,
        label: String(node.label ?? node.id),
        in: Array.isArray(node.in) ? node.in.map(String) : [],
        out: Array.isArray(node.out) ? node.out.map(String) : [],
        attr
      }];
    });
  const nodeIds = new Set(nodes.map((node) => node.id));
  const edges = (Array.isArray(graph.edges) ? graph.edges : []).flatMap((edge) => {
    if (!edge.src || !edge.dst || !nodeIds.has(String(edge.src)) || !nodeIds.has(String(edge.dst))) {
      return [];
    }
    const relation = normalizeGraphRelation(edge.relation);
    return [{
      ...edge,
      src: String(edge.src),
      dst: String(edge.dst),
      relation: relation.relation,
      attr: {
        ...(isObjectRecord(edge.attr) ? edge.attr : {}),
        ...(relation.original ? { original_relation: relation.original } : {})
      }
    }];
  });
  return { nodes, edges };
}

function normalizeGraphKind(rawKind: string | undefined) {
  const normalized = String(rawKind ?? "").trim().toLowerCase();
  if (normalized === "function" || normalized === "register" || normalized === "doc") {
    return { kind: normalized };
  }
  if (normalized === "doc_section") {
    return { kind: "doc", docKind: "markdown_section" };
  }
  if (normalized === "pdf_section") {
    return { kind: "doc", docKind: "pdf_section" };
  }
  if (normalized === "doc_box") {
    return { kind: "doc", docKind: "boxmatrix_box" };
  }
  return null;
}

function normalizeGraphRelation(rawRelation: string | undefined) {
  const raw = String(rawRelation ?? "").trim();
  const normalized = raw.toLowerCase().replace(/[-\s]+/g, "_");
  const aliases: Record<string, string> = {
    field_set: "sets_field",
    field_write: "writes",
    field_read: "reads",
    has_field: "sets_field",
    api_sets_field: "sets_field",
    api_global_sets_field: "sets_field",
    contains_box: "contains",
    section_contains_box: "contains",
    documents_register: "documents",
    section_mentions: "documents",
    api_relates: "relates_to",
    api_global_documented_by: "documents",
    related: "relates_to"
  };
  const candidate = aliases[normalized] ?? normalized;
  if (allowedGraphRelations.has(candidate)) {
    return { relation: candidate, original: candidate === normalized ? "" : raw };
  }
  return { relation: "relates_to", original: raw };
}

function unknownSourceRecord() {
  return { corpus_id: "unknown", repo: "unknown", path: "" };
}

function isObjectRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
