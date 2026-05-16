"use client";

import Image from "next/image";
import Link from "next/link";
import { Activity, Moon, Search, Sun } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { navItems, pageConfigs, type PageId } from "@/lib/page-data";

type WorkbenchPageProps = {
  pageId: PageId;
};

export function WorkbenchPage({ pageId }: WorkbenchPageProps) {
  const config = pageConfigs[pageId];
  const [query, setQuery] = useState(config.query);
  const [runCount, setRunCount] = useState(1);
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  const inspectorTitle = useMemo(() => {
    if (query.toLowerCase().includes("enable")) {
      return `${config.inspectorTitle}: ENABLE_L2_CACHE`;
    }

    return config.inspectorTitle;
  }, [config.inspectorTitle, query]);

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
            Ollama: qwen3.5
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
            {config.metrics.map((metric) => (
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

          {config.id === "graph-explorer" ? <GlobalNetworkGraph /> : null}

          <div className="results-table" role="table" aria-label="Evidence results">
            {config.rows.map((item) => (
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
          <Button className="settings-button" type="button" variant="secondary">
            {config.actionLabel}
          </Button>
        </aside>
      </main>
    </div>
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
