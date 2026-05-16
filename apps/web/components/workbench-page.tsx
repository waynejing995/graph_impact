"use client";

import Image from "next/image";
import Link from "next/link";
import { Activity, Moon, Search, Sun } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { navItems, pageConfigs, type EvidenceRow, type Metric, type PageId } from "@/lib/page-data";

type WorkbenchPageProps = {
  pageId: PageId;
};

const providerSettingsStorageKey = "asip-provider-settings";
const themeStorageKey = "asip-theme";
const defaultTheme = "dark";

type Theme = "dark" | "light";

type ProviderSettings = {
  provider: "ollama" | "openai-compatible";
  apiBaseUrl: string;
  apiPath: string;
  edgeModel: string;
  fallbackModel: string;
  embeddingModel: string;
  timeoutSeconds: string;
  numCtx: string;
  numPredict: string;
  temperature: string;
  think: boolean;
  extraHeaders: Record<string, string>;
};

type ProviderSettingsDraft = Omit<ProviderSettings, "extraHeaders"> & {
  extraHeadersJson: string;
};

type RuntimeEdgeModelConfig = {
  provider: ProviderSettings["provider"];
  api_base_url: string;
  api_path: string;
  preferred: string;
  fallback: string;
  embedding_model: string;
  extra_headers: Record<string, string>;
  format: "json";
  num_ctx: number;
  num_predict: number;
  temperature: number;
  think: boolean;
  timeout_seconds: number;
};

const defaultProviderSettings: ProviderSettings = {
  provider: "ollama",
  apiBaseUrl: "http://localhost:11434",
  apiPath: "/api/chat",
  edgeModel: "qwen3.5:4b",
  fallbackModel: "qwen3.6",
  embeddingModel: "nomic-embed-text:latest",
  timeoutSeconds: "900",
  numCtx: "2048",
  numPredict: "1024",
  temperature: "0",
  think: false,
  extraHeaders: {}
};

export function WorkbenchPage({ pageId }: WorkbenchPageProps) {
  const config = pageConfigs[pageId];
  const [query, setQuery] = useState(config.query);
  const [runCount, setRunCount] = useState(1);
  const [theme, setTheme] = useState<Theme>(defaultTheme);
  const [themeReady, setThemeReady] = useState(false);
  const [providerSettings, setProviderSettings] = useState<ProviderSettings>(defaultProviderSettings);
  const [settingsDraft, setSettingsDraft] = useState<ProviderSettingsDraft>(
    settingsToDraft(defaultProviderSettings)
  );
  const [settingsMessage, setSettingsMessage] = useState("");
  const [settingsError, setSettingsError] = useState("");
  const [actionMessage, setActionMessage] = useState("");

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
    const stored = window.localStorage.getItem(providerSettingsStorageKey);
    if (!stored) {
      return;
    }

    try {
      const parsed = JSON.parse(stored) as Partial<ProviderSettings>;
      const next = normalizeProviderSettings(parsed);
      setProviderSettings(next);
      setSettingsDraft(settingsToDraft(next));
    } catch {
      setSettingsError("Stored provider settings are invalid JSON.");
    }
  }, []);

  const inspectorTitle = useMemo(() => {
    if (query.toLowerCase().includes("enable")) {
      return `${config.inspectorTitle}: ENABLE_L2_CACHE`;
    }

    return config.inspectorTitle;
  }, [config.inspectorTitle, query]);

  const providerLabel = providerSettings.provider === "ollama" ? "Ollama" : "OpenAI-compatible";
  const runtimeConfig = useMemo(() => buildRuntimeEdgeModelConfig(providerSettings), [providerSettings]);
  const pageMetrics = useMemo(
    () => (config.id === "settings" ? buildSettingsMetrics(providerSettings) : config.metrics),
    [config.id, config.metrics, providerSettings]
  );
  const evidenceRows = useMemo(
    () => (config.id === "settings" ? buildSettingsEvidenceRows(providerSettings) : config.rows),
    [config.id, config.rows, providerSettings]
  );

  function saveProviderSettings() {
    try {
      const parsedHeaders = parseExtraHeaders(settingsDraft.extraHeadersJson);
      const next: ProviderSettings = {
        provider: settingsDraft.provider,
        apiBaseUrl: settingsDraft.apiBaseUrl.trim(),
        apiPath: settingsDraft.apiPath.trim() || "/api/chat",
        edgeModel: settingsDraft.edgeModel.trim(),
        fallbackModel: settingsDraft.fallbackModel.trim(),
        embeddingModel: settingsDraft.embeddingModel.trim(),
        timeoutSeconds: settingsDraft.timeoutSeconds.trim(),
        numCtx: settingsDraft.numCtx.trim(),
        numPredict: settingsDraft.numPredict.trim(),
        temperature: settingsDraft.temperature.trim(),
        think: settingsDraft.think,
        extraHeaders: parsedHeaders
      };
      window.localStorage.setItem(providerSettingsStorageKey, JSON.stringify(next));
      setProviderSettings(next);
      setSettingsDraft(settingsToDraft(next));
      setSettingsError("");
      setSettingsMessage("Provider settings saved");
    } catch (error) {
      setSettingsMessage("");
      setSettingsError(error instanceof Error ? error.message : "Provider settings are invalid.");
    }
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
          <Input aria-label="Global symbol search" defaultValue={config.globalSymbol} />
        </label>
        <div className="status-row" aria-label="Workbench status">
          <Badge tone="success">
            <span className="status-dot" />
            {providerLabel}: {providerSettings.edgeModel}
          </Badge>
          <Badge>Index: ready</Badge>
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
        <Badge>amd-mvp1</Badge>
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
          <div className="composer">
            <label className="query-input">
              <Search aria-hidden="true" size={16} />
              <Input aria-label="Evidence query" onChange={(event) => setQuery(event.target.value)} value={query} />
            </label>
            <Button onClick={() => setRunCount((count) => count + 1)} type="button">
              Run query
            </Button>
          </div>

          <div className="metric-row" aria-label="Page metrics">
            {pageMetrics.map((metric) => (
              <Badge key={metric.label} tone={metric.tone ?? "neutral"}>
                {metric.label}: {metric.value}
              </Badge>
            ))}
          </div>

          <div className="filter-row" aria-label="Evidence source filters">
            {config.filters.map(({ icon: Icon, label, tone }) => (
              <Badge key={label} tone={tone}>
                <Icon aria-hidden="true" size={14} />
                {label}
              </Badge>
            ))}
          </div>

          {config.id === "settings" ? (
            <ProviderSettingsPanel
              draft={settingsDraft}
              error={settingsError}
              message={settingsMessage}
              onChange={setSettingsDraft}
              onSave={saveProviderSettings}
              runtimeConfig={runtimeConfig}
            />
          ) : null}

          {config.id === "graph-explorer" ? <GlobalNetworkGraph /> : null}

          <div className="results-table" role="table" aria-label="Evidence results">
            {evidenceRows.map((item) => (
              <div className="evidence-row" key={`${item.source}-${item.symbol}`} role="row">
                <span className={`source-dot source-dot--${item.tone}`} />
                <code>{item.symbol}</code>
                <Badge tone={item.tone}>{item.relation}</Badge>
                <span className="score">{item.score}</span>
                <span className="path">{item.path}</span>
              </div>
            ))}
          </div>
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
            {config.chain.map((item, index) => (
              <p className={index > 0 ? "edge" : undefined} key={item}>
                <code>{item}</code>
              </p>
            ))}
          </div>
          {config.detailSections.map((section) => (
            <section className="inspector-section" key={section.title}>
              <h3>{section.title}</h3>
              <p>
                <code>{section.body}</code>
              </p>
            </section>
          ))}
          <h3>Relationship Panel</h3>
          <div className="chain" data-testid="relationship-panel">
            {config.relationshipLines.map((line) => (
              <p key={line}>
                <code>{line}</code>
              </p>
            ))}
          </div>
          <Button
            className="settings-button"
            onClick={() => setActionMessage(`${config.actionLabel} queued`)}
            type="button"
            variant="secondary"
          >
            {config.actionLabel}
          </Button>
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

function settingsToDraft(settings: ProviderSettings): ProviderSettingsDraft {
  return {
    ...settings,
    extraHeadersJson: JSON.stringify(settings.extraHeaders, null, 2)
  };
}

function normalizeProviderSettings(settings: Partial<ProviderSettings>): ProviderSettings {
  return {
    ...defaultProviderSettings,
    ...settings,
    extraHeaders: settings.extraHeaders ?? {}
  };
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

function buildRuntimeEdgeModelConfig(settings: ProviderSettings): RuntimeEdgeModelConfig {
  return {
    provider: settings.provider,
    api_base_url: settings.apiBaseUrl,
    api_path: settings.apiPath,
    preferred: settings.edgeModel,
    fallback: settings.fallbackModel,
    embedding_model: settings.embeddingModel,
    extra_headers: settings.extraHeaders,
    format: "json",
    num_ctx: numberFromDraft(settings.numCtx, defaultProviderSettings.numCtx),
    num_predict: numberFromDraft(settings.numPredict, defaultProviderSettings.numPredict),
    temperature: numberFromDraft(settings.temperature, defaultProviderSettings.temperature),
    think: settings.think,
    timeout_seconds: numberFromDraft(settings.timeoutSeconds, defaultProviderSettings.timeoutSeconds)
  };
}

function buildSettingsMetrics(settings: ProviderSettings): Metric[] {
  return [
    { label: "edge model", value: settings.edgeModel || "unset", tone: "success" },
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
      score: settings.provider,
      path: settings.apiBaseUrl || defaultProviderSettings.apiBaseUrl
    },
    {
      source: "storage",
      tone: "code",
      symbol: "SQLite FTS5 + sqlite-vec",
      relation: "index",
      score: "local",
      path: "data/asip.db"
    }
  ];
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
  draft,
  error,
  message,
  onChange,
  onSave,
  runtimeConfig
}: {
  draft: ProviderSettingsDraft;
  error: string;
  message: string;
  onChange: (draft: ProviderSettingsDraft) => void;
  onSave: () => void;
  runtimeConfig: RuntimeEdgeModelConfig;
}) {
  const update = <Key extends keyof ProviderSettingsDraft>(key: Key, value: ProviderSettingsDraft[Key]) => {
    onChange({ ...draft, [key]: value });
  };

  return (
    <section className="provider-settings-panel" aria-label="Provider settings">
      <div className="provider-settings-header">
        <div>
          <h2>Provider Runtime</h2>
          <p>Model, API endpoint, and extra headers are saved locally for the workbench.</p>
        </div>
        <Badge tone="success">{draft.provider}</Badge>
      </div>
      <div className="provider-settings-grid">
        <label className="provider-settings-field">
          <span>Provider</span>
          <select
            aria-label="Provider"
            className="ui-select"
            onChange={(event) => update("provider", event.target.value as ProviderSettings["provider"])}
            value={draft.provider}
          >
            <option value="ollama">Ollama</option>
            <option value="openai-compatible">OpenAI compatible</option>
          </select>
        </label>
        <label className="provider-settings-field">
          <span>Chat API base URL</span>
          <Input
            aria-label="Chat API base URL"
            onChange={(event) => update("apiBaseUrl", event.target.value)}
            value={draft.apiBaseUrl}
          />
        </label>
        <label className="provider-settings-field">
          <span>Chat API path</span>
          <Input
            aria-label="Chat API path"
            onChange={(event) => update("apiPath", event.target.value)}
            value={draft.apiPath}
          />
        </label>
        <label className="provider-settings-field">
          <span>Edge model</span>
          <Input
            aria-label="Edge model"
            onChange={(event) => update("edgeModel", event.target.value)}
            value={draft.edgeModel}
          />
        </label>
        <label className="provider-settings-field">
          <span>Fallback model</span>
          <Input
            aria-label="Fallback model"
            onChange={(event) => update("fallbackModel", event.target.value)}
            value={draft.fallbackModel}
          />
        </label>
        <label className="provider-settings-field">
          <span>Embedding model</span>
          <Input
            aria-label="Embedding model"
            onChange={(event) => update("embeddingModel", event.target.value)}
            value={draft.embeddingModel}
          />
        </label>
        <label className="provider-settings-field">
          <span>Timeout seconds</span>
          <Input
            aria-label="Timeout seconds"
            inputMode="numeric"
            onChange={(event) => update("timeoutSeconds", event.target.value)}
            value={draft.timeoutSeconds}
          />
        </label>
        <label className="provider-settings-field">
          <span>Context tokens</span>
          <Input
            aria-label="Context tokens"
            inputMode="numeric"
            onChange={(event) => update("numCtx", event.target.value)}
            value={draft.numCtx}
          />
        </label>
        <label className="provider-settings-field">
          <span>Prediction tokens</span>
          <Input
            aria-label="Prediction tokens"
            inputMode="numeric"
            onChange={(event) => update("numPredict", event.target.value)}
            value={draft.numPredict}
          />
        </label>
        <label className="provider-settings-field">
          <span>Temperature</span>
          <Input
            aria-label="Temperature"
            inputMode="decimal"
            onChange={(event) => update("temperature", event.target.value)}
            value={draft.temperature}
          />
        </label>
        <label className="provider-settings-field provider-settings-field--toggle">
          <input
            aria-label="Enable model thinking"
            checked={draft.think}
            onChange={(event) => update("think", event.target.checked)}
            type="checkbox"
          />
          <span>Enable model thinking</span>
        </label>
        <label className="provider-settings-field provider-settings-field--wide">
          <span>Extra headers JSON</span>
          <Textarea
            aria-label="Extra headers JSON"
            onChange={(event) => update("extraHeadersJson", event.target.value)}
            rows={4}
            value={draft.extraHeadersJson}
          />
        </label>
      </div>
      <div className="provider-settings-actions">
        <Button onClick={onSave} type="button">
          Save provider settings
        </Button>
        {message ? <span className="settings-feedback">{message}</span> : null}
        {error ? <span className="settings-feedback settings-feedback--error">{error}</span> : null}
      </div>
      <div className="runtime-config">
        <div className="runtime-config__header">
          <span>Edge runner config</span>
          <Badge tone="code">JSON</Badge>
        </div>
        <pre aria-label="Runtime config JSON" data-testid="runtime-config-preview">
          {JSON.stringify(runtimeConfig, null, 2)}
        </pre>
      </div>
    </section>
  );
}

function GlobalNetworkGraph() {
  return (
    <div className="network-preview network-preview--global" data-testid="global-network-graph">
      <div className="network-preview__header">
        <span>Global Relation Graph</span>
        <Badge tone="code">weighted connections</Badge>
      </div>
      <svg aria-label="Global weighted network graph" role="img" viewBox="0 0 960 420">
        <defs>
          <marker id="arrow" markerHeight="8" markerWidth="8" orient="auto" refX="7" refY="4">
            <path d="M0,0 L8,4 L0,8 Z" fill="var(--graph-edge)" />
          </marker>
        </defs>
        <line className="graph-edge-line graph-edge-line--w5" x1="470" x2="245" y1="205" y2="110" />
        <line className="graph-edge-line graph-edge-line--w4" x1="470" x2="700" y1="205" y2="120" />
        <line className="graph-edge-line graph-edge-line--w3" x1="470" x2="710" y1="205" y2="305" />
        <line className="graph-edge-line graph-edge-line--w2" x1="470" x2="240" y1="205" y2="305" />
        <line className="graph-edge-line graph-edge-line--w2" x1="245" x2="240" y1="110" y2="305" />
        <line className="graph-edge-line graph-edge-line--w1" x1="700" x2="710" y1="120" y2="305" />
        <line className="graph-edge-line graph-edge-line--w1" x1="470" x2="480" y1="205" y2="55" />
        <circle className="graph-halo" cx="470" cy="205" r="86" />
        <g className="graph-bubble graph-bubble--register" transform="translate(470 205)">
          <circle r="58" />
          <text y="-5">GCVM_L2_CNTL</text>
          <text y="17">weight 12</text>
        </g>
        <g className="graph-bubble graph-bubble--code" transform="translate(245 110)">
          <circle r="46" />
          <text y="-4">gmc_v11_0</text>
          <text y="16">writes 8</text>
        </g>
        <g className="graph-bubble graph-bubble--field" transform="translate(700 120)">
          <circle r="42" />
          <text y="-4">ENABLE_L2</text>
          <text y="16">field 6</text>
        </g>
        <g className="graph-bubble graph-bubble--doc" transform="translate(710 305)">
          <circle r="36" />
          <text y="-4">GC docs</text>
          <text y="16">mentions 3</text>
        </g>
        <g className="graph-bubble graph-bubble--code" transform="translate(240 305)">
          <circle r="38" />
          <text y="-4">MxGPU</text>
          <text y="16">maps 4</text>
        </g>
        <g className="graph-bubble graph-bubble--neutral" transform="translate(480 55)">
          <circle r="30" />
          <text y="-3">PDF</text>
          <text y="15">2</text>
        </g>
        <text className="graph-edge-label" x="328" y="145">writes / 0.94</text>
        <text className="graph-edge-label" x="565" y="150">has_field / 0.91</text>
        <text className="graph-edge-label" x="585" y="265">documented_by / 0.72</text>
        <text className="graph-edge-label" x="305" y="265">maps_base / 0.68</text>
      </svg>
    </div>
  );
}
