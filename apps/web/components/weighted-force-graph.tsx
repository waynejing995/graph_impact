"use client";

import dynamic from "next/dynamic";
import { useEffect, useId, useMemo, useRef, useState, type ComponentType } from "react";
import type { ForceGraphProps, LinkObject, NodeObject } from "react-force-graph-2d";

type WeightedGraphNode = {
  id: string;
  kind?: string;
  weight?: number;
};

type WeightedGraphEdge = {
  src: string;
  dst: string;
  relation: string;
  confidence?: number;
  weight?: number;
};

export type WeightedGraphPayload = {
  nodes: WeightedGraphNode[];
  edges: WeightedGraphEdge[];
};

type ForceNode = NodeObject<{
  id: string;
  kind: string;
  label: string;
  weight: number;
}>;

type ForceLink = LinkObject<
  ForceNode,
  {
    source: string;
    target: string;
    relation: string;
    label: string;
    weight: number;
  }
>;

type GraphPalette = {
  code: string;
  register: string;
  field: string;
  doc: string;
  pdf: string;
  edge: string;
  foreground: string;
  surface: string;
};

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false
}) as ComponentType<ForceGraphProps<ForceNode, ForceLink>>;

const fallbackPalette: GraphPalette = {
  code: "#7dd3fc",
  register: "#facc15",
  field: "#39d98a",
  doc: "#c084fc",
  pdf: "#fb7185",
  edge: "#60a5fa",
  foreground: "#f3f7f8",
  surface: "#0a0d0e"
};

export function WeightedForceGraph({
  graph,
  label = "Global weighted network graph"
}: {
  graph: WeightedGraphPayload;
  label?: string;
}) {
  const summaryId = useId();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [size, setSize] = useState({ width: 960, height: 420 });
  const [ready, setReady] = useState(false);
  const [palette, setPalette] = useState<GraphPalette>(fallbackPalette);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) {
      return undefined;
    }
    const observer = new ResizeObserver(([entry]) => {
      const width = Math.max(320, Math.round(entry.contentRect.width));
      const height = Math.max(300, Math.round(Math.min(560, width * 0.44)));
      setSize({ width, height });
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const root = getComputedStyle(document.documentElement);
    setPalette({
      code: cssValue(root, "--code", fallbackPalette.code),
      register: cssValue(root, "--register", fallbackPalette.register),
      field: cssValue(root, "--primary", fallbackPalette.field),
      doc: cssValue(root, "--doc", fallbackPalette.doc),
      pdf: cssValue(root, "--pdf", fallbackPalette.pdf),
      edge: cssValue(root, "--graph-edge", fallbackPalette.edge),
      foreground: cssValue(root, "--foreground", fallbackPalette.foreground),
      surface: cssValue(root, "--surface-1", fallbackPalette.surface)
    });
  }, [graph]);

  const graphData = useMemo(() => {
    const nodes = graph.nodes.slice(0, 140).map((node): ForceNode => {
      const kind = normalizeKind(node.kind);
      return {
        id: node.id,
        label: node.id,
        kind,
        weight: Math.max(1, Number(node.weight ?? 1))
      };
    });
    const nodeIds = new Set(nodes.map((node) => String(node.id)));
    const links = graph.edges
      .filter((edge) => edge.src && edge.dst && nodeIds.has(edge.src) && nodeIds.has(edge.dst))
      .slice(0, 260)
      .map((edge): ForceLink => {
        const weight = normalizedWeight(edge);
        return {
          source: edge.src,
          target: edge.dst,
          relation: edge.relation,
          label: `${edge.src} ${edge.relation} ${edge.dst} (${weight.toFixed(2)})`,
          weight
        };
      });
    return { nodes, links };
  }, [graph]);

  const topNodes = useMemo(
    () => [...graphData.nodes].sort((left, right) => right.weight - left.weight).slice(0, 8),
    [graphData.nodes]
  );
  const summaryNodes = graphData.nodes.length <= 32 ? graphData.nodes : topNodes;
  const topLinks = useMemo(
    () => [...graphData.links].sort((left, right) => right.weight - left.weight).slice(0, 8),
    [graphData.links]
  );
  const kindCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const node of graphData.nodes) {
      counts.set(node.kind, (counts.get(node.kind) ?? 0) + 1);
    }
    return [...counts.entries()].sort((left, right) => left[0].localeCompare(right[0]));
  }, [graphData.nodes]);

  return (
    <div
      aria-describedby={summaryId}
      aria-label={label}
      className="force-graph-shell"
      data-edge-count={graphData.links.length}
      data-ready={ready ? "true" : "false"}
      data-strongest-weight={topLinks[0]?.weight.toFixed(2) ?? "0.00"}
      data-testid="force-graph"
      data-weakest-weight={topLinks.at(-1)?.weight.toFixed(2) ?? "0.00"}
      data-node-count={graphData.nodes.length}
      ref={containerRef}
      role="img"
    >
      <ForceGraph2D
        autoPauseRedraw={false}
        backgroundColor="rgba(0,0,0,0)"
        cooldownTicks={90}
        d3AlphaDecay={0.035}
        d3VelocityDecay={0.28}
        enableNodeDrag
        enablePanInteraction
        enablePointerInteraction
        enableZoomInteraction
        graphData={graphData}
        height={size.height}
        linkColor={() => palette.edge}
        linkDirectionalArrowLength={(link) => (link.weight > 0.72 ? 4 : 0)}
        linkDirectionalParticles={(link) => (link.weight > 0.78 ? 2 : 0)}
        linkDirectionalParticleWidth={(link) => 1.2 + link.weight * 2}
        linkLabel={(link) => link.label}
        linkWidth={(link) => 0.8 + link.weight * 4.8}
        nodeCanvasObject={(node, context, globalScale) => drawNodeLabel(node, context, globalScale, palette)}
        nodeCanvasObjectMode={() => "after"}
        nodeColor={(node) => colorForKind(node.kind, palette)}
        nodeId="id"
        nodeLabel={(node) => `${node.label} (${node.kind}, weight ${node.weight})`}
        nodeRelSize={4}
        nodeVal={(node) => Math.max(2, node.weight)}
        onEngineStop={() => setReady(true)}
        warmupTicks={60}
        width={size.width}
      />
      <div className="graph-accessibility-summary" id={summaryId}>
        <span>nodes {graphData.nodes.length}</span>
        <span>edges {graphData.links.length}</span>
        {kindCounts.map(([kind, count]) => (
          <span key={`kind-${kind}`}>{kind} {count}</span>
        ))}
        {summaryNodes.map((node) => (
          <span key={`node-${node.id}`}>{node.label}</span>
        ))}
        {topLinks.map((link, index) => (
          <span key={`link-${index}-${link.relation}`}>{link.relation} / {link.weight.toFixed(2)}</span>
        ))}
      </div>
    </div>
  );
}

function drawNodeLabel(
  node: ForceNode,
  context: CanvasRenderingContext2D,
  globalScale: number,
  palette: GraphPalette
) {
  if (globalScale < 0.42) {
    return;
  }
  const label = shortLabel(node.label);
  const fontSize = Math.max(8, 11 / globalScale);
  const x = Number(node.x ?? 0);
  const y = Number(node.y ?? 0);
  context.font = `700 ${fontSize}px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`;
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.lineWidth = Math.max(2, 3 / globalScale);
  context.strokeStyle = palette.surface;
  context.strokeText(label, x, y + 13 / globalScale);
  context.fillStyle = palette.foreground;
  context.fillText(label, x, y + 13 / globalScale);
}

function normalizeKind(kind: string | undefined) {
  const normalized = String(kind || "code").toLowerCase();
  if (
    normalized === "register" ||
    normalized === "field" ||
    normalized === "doc" ||
    normalized === "doc_section" ||
    normalized === "pdf" ||
    normalized === "pdf_section"
  ) {
    return normalized;
  }
  return "code";
}

function normalizedWeight(edge: WeightedGraphEdge) {
  const value = Number(edge.weight ?? edge.confidence ?? 0.5);
  if (!Number.isFinite(value)) {
    return 0.5;
  }
  return Math.max(0.08, Math.min(1, value));
}

function colorForKind(kind: string, palette: GraphPalette) {
  if (kind === "register") {
    return palette.register;
  }
  if (kind === "field") {
    return palette.field;
  }
  if (kind === "doc" || kind === "doc_section") {
    return palette.doc;
  }
  if (kind === "pdf" || kind === "pdf_section") {
    return palette.pdf;
  }
  return palette.code;
}

function cssValue(styles: CSSStyleDeclaration, name: string, fallback: string) {
  return styles.getPropertyValue(name).trim() || fallback;
}

function shortLabel(value: string) {
  return value.length > 24 ? `${value.slice(0, 21)}...` : value;
}
