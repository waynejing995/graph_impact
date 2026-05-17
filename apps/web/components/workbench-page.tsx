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
  type FormEvent
} from "react";
import { WeightedForceGraph, type WeightedGraphPayload } from "@/components/weighted-force-graph";
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

type CorpusEntry = {
  id: string;
  repo: string;
  sourceRoot: string;
  include: string;
  fileCount: string;
  status?: string;
};

type ApiCorpusEntry = {
  id: string;
  repo?: string;
  sourceRoot?: string;
  source_root?: string;
  include?: string[] | string;
  fileCount?: number | string;
  file_count?: number | string;
  status?: string;
};

type ResolverProfile = {
  id: string;
  wrapper: string;
  strategy: string;
  path: string;
  enabled: boolean;
};

type ApiResolverProfile = {
  id: string;
  language?: string;
  wrappers?: string[];
  path?: string;
  enabled?: boolean;
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
};

type GraphPayload = WeightedGraphPayload;

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
  const providerSettingsDirtyRef = useRef(false);
  const queryInputRef = useRef<HTMLInputElement | null>(null);
  const queryRequestSeqRef = useRef(0);
  const [settingsDraft, setSettingsDraft] = useState<ProviderSettingsDraft>(
    settingsToDraft(defaultProviderSettings)
  );
  const [settingsMessage, setSettingsMessage] = useState("");
  const [settingsError, setSettingsError] = useState("");
  const [acceptanceDbPath, setAcceptanceDbPath] = useState("");
  const [corpora, setCorpora] = useState<CorpusEntry[]>([]);
  const [selectedCorpusIds, setSelectedCorpusIds] = useState<string[]>([]);
  const [corpusDraft, setCorpusDraft] = useState<CorpusEntry>({
    id: "",
    repo: "",
    sourceRoot: "",
    include: "**/*.c, **/*.h",
    fileCount: "user"
  });
  const [corpusMessage, setCorpusMessage] = useState("");
  const [resolverProfiles, setResolverProfiles] = useState<ResolverProfile[]>([]);
  const [resolverDraft, setResolverDraft] = useState<ResolverProfile>({
    id: "initial",
    wrapper: "RREG32",
    strategy: "macro",
    path: "configs/resolvers/initial.yaml",
    enabled: true
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
  const [graphEmptyMessage, setGraphEmptyMessage] = useState("");
  const [queryEmptyMessage, setQueryEmptyMessage] = useState(
    config.id === "evidence-workbench" ? "Enter a query to search live evidence." : ""
  );
  const [acceptanceRuns, setAcceptanceRuns] = useState<AcceptanceRun[]>([]);

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

  useLayoutEffect(() => {
    if (config.id === "evidence-workbench" && queryValueRef.current.trim()) {
      setQueryEmptyMessage("");
      return;
    }
    updateQuery(config.query);
    setQueryEmptyMessage(config.id === "evidence-workbench" ? "Enter a query to search live evidence." : "");
  }, [config.id, config.query]);

  useEffect(() => {
    if (config.id !== "evidence-workbench") {
      return;
    }
    if (config.query.trim()) {
      void executeQuery(config.query, { announce: false, incrementRun: false });
    }
  }, [config.id, config.query]);

  useEffect(() => {
    if (config.id !== "graph-explorer") {
      setApiGraph(null);
      return;
    }

    let cancelled = false;
    setGraphEmptyMessage("");
    fetch("/api/workbench/graph")
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Graph API returned ${response.status}`);
        }
        return response.json() as Promise<GraphPayload>;
      })
      .then((payload) => {
        if (!cancelled) {
          setApiGraph(payload);
          setGraphEmptyMessage(payload.nodes.length || payload.edges.length ? "" : "No graph data returned.");
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setApiGraph({ nodes: [], edges: [] });
          setGraphEmptyMessage(error instanceof Error ? error.message : "Graph failed");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [config.id]);

  useEffect(() => {
    let cancelled = false;
    const applySettings = (next: ProviderSettings) => {
      if (cancelled) {
        return;
      }
      setProviderSettings(next);
      setSettingsDraft(settingsToDraft(next));
      setProviderVerification("unverified");
    };

    fetch("/api/workbench/providers/settings")
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
  }, []);

  useEffect(() => {
    let cancelled = false;

    fetch("/api/workbench/resolver-profiles")
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Resolver API returned ${response.status}`);
        }
        return response.json() as Promise<{ profiles?: ApiResolverProfile[] }>;
      })
      .then((payload) => {
        if (!cancelled) {
          const apiProfiles = (payload.profiles ?? []).map(normalizeApiResolverProfile);
          setResolverProfiles(apiProfiles);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setResolverProfiles([]);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    fetch("/api/workbench/corpora")
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
  }, []);

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
  const inspectorTitle = useMemo(() => {
    if (selectedEvidence) {
      return `Resolved Evidence: ${selectedEvidence.symbol}`;
    }
    return config.inspectorTitle;
  }, [config.inspectorTitle, selectedEvidence]);
  const inspectorChain = useMemo(
    () => (selectedEvidence ? buildLiveInspectorChain(selectedEvidence) : []),
    [selectedEvidence]
  );
  const inspectorDetailSections = useMemo(
    () => (selectedEvidence ? buildLiveInspectorSections(selectedEvidence) : []),
    [selectedEvidence]
  );
  const inspectorRelationshipLines = useMemo(
    () => {
      if (selectedEvidence) {
        return buildLiveRelationshipLines(selectedEvidence, apiGraph);
      }
      if (config.id === "graph-explorer" && apiGraph) {
        return buildGraphRelationshipLines(apiGraph, graphEmptyMessage);
      }
      return ["No relationship data returned from API."];
    },
    [apiGraph, config.id, graphEmptyMessage, selectedEvidence]
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
      setApiQueryRows([]);
      setSelectedEvidenceKey("");
      setApiGraph(config.id === "graph-explorer" ? apiGraph : { nodes: [], edges: [] });
      setQueryEmptyMessage("Enter a query to search live evidence.");
      if (config.id !== "graph-explorer") {
        setGraphEmptyMessage("");
      }
      return;
    }
    updateQuery(nextQuery);
    await executeQuery(nextQuery, { announce: true, incrementRun: true });
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
        setApiQueryRows(normalizedRows);
        setSelectedEvidenceKey(normalizedRows[0] ? evidenceRowKey(normalizedRows[0]) : "");
        setApiGraph(payload.graph ?? null);
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

  async function runPageAction(options: { semanticMode?: "query" | "batch" } = {}) {
    if (config.id === "corpus") {
      const selectedIds = selectedCorpusIds.filter((id) => corpora.some((corpus) => corpus.id === id));
      if (selectedIds.length === 0) {
        setActionMessage("Select at least one corpus to index.");
        return;
      }
      setActionMessage("Running index job...");
      try {
        const response = await fetch("/api/workbench/index", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ corpusIds: selectedIds })
        });
        const payload = (await response.json()) as {
          status?: string;
          corpusIds?: string[];
          dbPath?: string;
          documents?: number;
          chunks?: number;
          edges?: number;
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
        setActionMessage(
          `Index built${corpusLabel}: ${payload.documents ?? 0} documents, ${payload.chunks ?? 0} chunks, ${
            payload.edges ?? 0
          } edges -> ${payload.dbPath ?? "data/asip.db"}`
        );
      } catch (error) {
        setActionMessage(error instanceof Error ? error.message : "Index job failed");
      }
      return;
    }

    if (config.id !== "settings") {
      if (config.id === "graph-explorer") {
        if (options.semanticMode === "batch") {
          setActionMessage("Generating batch semantic edges...");
          try {
            const response = await fetch("/api/workbench/semantic-edges", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ mode: "batch", limit: 24, batchSize: 6 })
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
              setApiGraph(payload.graph);
              setGraphEmptyMessage(
                payload.graph.nodes.length || payload.graph.edges.length
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
          const response = await fetch("/api/workbench/semantic-edges", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ q: semanticEdgeQuery })
          });
          const payload = (await response.json()) as { edge_count?: number; graph?: GraphPayload; error?: string };
          if (!response.ok) {
            throw new Error(payload.error ?? `Semantic edge API returned ${response.status}`);
          }
          if (payload.graph) {
            setApiGraph(payload.graph);
            setGraphEmptyMessage(payload.graph.nodes.length || payload.graph.edges.length ? "" : "Semantic edge job returned no graph data");
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
      await persistProviderSettings(next);
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
      await persistProviderSettings(next);
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
          surfaces: ["CLI", "API", "Web"],
          ...(acceptanceDbPath.trim() ? { dbPath: acceptanceDbPath.trim() } : {})
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
          type: next.include.includes("pdf") ? "doc" : "code"
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
      setCorpusDraft({ id: "", repo: "", sourceRoot: "", include: "**/*.c, **/*.h", fileCount: "user" });
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
      strategy: resolverDraft.strategy.trim() || "macro",
      path: resolverDraft.path.trim() || `configs/resolvers/${id}.yaml`,
      enabled: resolverDraft.enabled
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
          enabled: next.enabled
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
        strategy: "macro",
        path: "configs/resolvers/initial.yaml",
        enabled: true
      });
      setResolverMessage(`Resolver profile ${persisted.id} added`);
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
          validateSource: resolverValidateSource
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

  return (
    <div className="workbench-shell" data-page-id={config.id} data-testid="asip-workbench">
      <header className="topbar" role="banner">
        <div className="brand">
          <Image alt="" className="brand-logo" height={32} priority src="/brand/asip-logo.png" width={32} />
          <span>ASIP Evidence Workbench</span>
        </div>
        <label className="global-search">
          <Search aria-hidden="true" size={15} />
          <Input aria-label="Global symbol search" placeholder="Search indexed symbols" />
        </label>
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

          <div className="filter-row" aria-label="Evidence source filters">
            {config.filters.map(({ icon: Icon, label, tone }) => (
              <ToneBadge key={label} tone={tone}>
                <Icon aria-hidden="true" size={14} />
                {label}
              </ToneBadge>
            ))}
          </div>

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
              onAcceptanceDbPathChange={setAcceptanceDbPath}
              onSave={saveProviderSettings}
              onRunAcceptance={runProviderAcceptance}
              runtimeConfig={runtimeConfig}
            />
          ) : null}

          {config.id === "corpus" ? (
            <CorpusEditor
              draft={corpusDraft}
              message={corpusMessage}
              onAdd={addCorpus}
              onChange={setCorpusDraft}
            />
          ) : null}

          {config.id === "resolver-profiles" ? (
            <ResolverProfileEditor
              draft={resolverDraft}
              message={resolverMessage}
              onAdd={addResolverProfile}
              onChange={setResolverDraft}
              onValidate={validateResolverProfile}
              onValidateSourceChange={setResolverValidateSource}
              validateSource={resolverValidateSource}
            />
          ) : null}

          {config.id === "graph-explorer" || config.id === "evidence-workbench" ? (
            <GlobalNetworkGraph
              emptyMessage={graphEmptyMessage || queryEmptyMessage}
              graph={apiGraph}
              rows={queryEvidenceRows}
              testId={config.id === "graph-explorer" ? "global-network-graph" : "query-network-graph"}
            />
          ) : null}

          {config.id === "acceptance-tests" ? <AcceptanceRunsPanel runs={acceptanceRuns} /> : null}

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
              <p>
                <code>{section.body}</code>
              </p>
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
            <Button
              className="settings-button"
              onClick={() => void runPageAction({ semanticMode: "batch" })}
              type="button"
              variant="secondary"
            >
              Generate batch semantic edges
            </Button>
          ) : null}
          {actionMessage ? (
            <p className="action-feedback" data-testid="action-feedback">
              {actionMessage}
            </p>
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
                      <code>{item.symbol}</code>
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
    detail.missing.length ? `missing terms: ${detail.missing.join(", ")}` : ""
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

async function persistProviderSettings(next: ProviderSettings) {
  const response = await fetch("/api/workbench/providers/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(providerSettingsToBackend(next))
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
      { label: "graph edges", value: String(graph?.edges.length ?? Math.min(7, queryRows.length)) },
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
      symbol: profile.wrapper,
      relation: profile.enabled ? profile.strategy : "disabled",
      score: profile.id,
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
    fileCount: String(corpus.fileCount ?? corpus.file_count ?? "api"),
    status: corpus.status ?? "not_indexed"
  };
}

function normalizeApiResolverProfile(profile: ApiResolverProfile): ResolverProfile {
  return {
    id: profile.id,
    wrapper: profile.wrappers?.[0] ?? profile.id,
    strategy: profile.language ?? "config",
    path: profile.path ?? `configs/resolvers/${profile.id}.yaml`,
    enabled: profile.enabled ?? true
  };
}

function normalizeApiEvidenceRow(row: EvidenceRow): EvidenceRow {
  return {
    source: row.source ?? "api",
    tone: row.tone ?? "neutral",
    symbol: row.symbol,
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
    sourceHitCount: normalizeOptionalNumber(detail.sourceHitCount ?? detail.source_hit_count)
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
  return `${row.source}:${row.symbol}:${row.path}`;
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
  return [row.symbol, row.relation, row.path].filter(Boolean);
}

function buildLiveInspectorSections(row: EvidenceRow): Array<{ title: string; body: string }> {
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

function buildLiveRelationshipLines(row: EvidenceRow, graph: GraphPayload | null): string[] {
  const lines = new Set<string>();
  if (row.resolved_chain) {
    lines.add(row.resolved_chain);
  }
  lines.add(`${row.symbol} ${row.relation} ${row.path}`);
  for (const edge of graph?.edges ?? []) {
    if (edge.src === row.symbol || edge.dst === row.symbol) {
      lines.add(`${edge.src} ${edge.relation} ${edge.dst}`);
    }
  }
  return Array.from(lines);
}

function buildGraphRelationshipLines(graph: GraphPayload, emptyMessage: string): string[] {
  if (graph.edges.length === 0) {
    return [emptyMessage || "No graph relationships returned."];
  }
  return graph.edges.slice(0, 12).map((edge) => `${edge.src} ${edge.relation} ${edge.dst}`);
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

function ResolverProfileEditor({
  draft,
  message,
  onAdd,
  onChange,
  onValidate,
  onValidateSourceChange,
  validateSource
}: {
  draft: ResolverProfile;
  message: string;
  onAdd: () => void;
  onChange: (draft: ResolverProfile) => void;
  onValidate: () => void;
  onValidateSourceChange: (source: string) => void;
  validateSource: string;
}) {
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
            <FieldDescription>Only enabled YAML-backed profiles participate in symbol resolution.</FieldDescription>
          </FieldContent>
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
          Add resolver profile
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

function GlobalNetworkGraph({
  emptyMessage,
  graph,
  rows,
  testId
}: {
  emptyMessage?: string;
  graph: GraphPayload | null;
  rows: EvidenceRow[];
  testId: string;
}) {
  const graphData = buildGraphData(graph, rows);
  const isEmpty = graphData.nodes.length === 0;

  return (
    <div className="network-preview network-preview--global" data-testid={testId}>
      <div className="network-preview__header">
        <span>Global Relation Graph</span>
        <ToneBadge tone="code">weighted connections</ToneBadge>
      </div>
      {isEmpty ? (
        <div className="network-empty" role="status">
          <code>{emptyMessage || "No graph data returned."}</code>
        </div>
      ) : (
        <WeightedForceGraph graph={graphData} />
      )}
    </div>
  );
}

function buildGraphData(graph: GraphPayload | null, rows: EvidenceRow[]): GraphPayload {
  if (graph) {
    return {
      nodes: graph.nodes,
      edges: graph.edges.filter((edge) => edge.src && edge.dst)
    };
  }
  if (rows.length === 0) {
    return { nodes: [], edges: [] };
  }
  const merged = rows.filter(
    (row, index, allRows) => allRows.findIndex((candidate) => candidate.symbol === row.symbol) === index
  );
  const registerIndex = merged.findIndex((row) => row.tone === "register");
  if (registerIndex > 0) {
    const [registerRow] = merged.splice(registerIndex, 1);
    merged.unshift(registerRow);
  }
  const pdfIndex = merged.findIndex((row, index) => index > 0 && row.tone === "pdf");
  if (pdfIndex > 0) {
    const [pdfRow] = merged.splice(pdfIndex, 1);
    merged.splice(Math.min(6, merged.length), 0, pdfRow);
  }
  const nodes = merged.slice(0, 9).map((row, index) => ({
    id: row.symbol,
    kind: row.tone === "success" ? "field" : row.tone,
    weight: Math.max(1, 9 - index)
  }));
  const edges = nodes.slice(1).map((node, index) => ({
    src: nodes[0].id,
    dst: node.id,
    relation: merged[index + 1]?.relation ?? "related",
    weight: Number(merged[index + 1]?.score) || Math.max(0.2, 0.9 - index * 0.08)
  }));
  return { nodes, edges };
}
