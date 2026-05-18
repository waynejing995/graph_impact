"use client";

import dynamic from "next/dynamic";
import { useEffect, useId, useMemo, useRef, useState, type ComponentType } from "react";
import type { ForceGraphProps, LinkObject, NodeObject } from "react-force-graph-2d";

type WeightedGraphNode = {
  id: string;
  kind?: string;
  label?: string;
  weight?: number;
  in?: string[];
  out?: string[];
  attr?: Record<string, unknown>;
};

type WeightedGraphEdge = {
  src: string;
  dst: string;
  relation: string;
  confidence?: number;
  weight?: number;
  stage?: string;
  sources?: Array<Record<string, unknown>>;
  attr?: Record<string, unknown>;
};

export type WeightedGraphPayload = {
  nodes: WeightedGraphNode[];
  edges: WeightedGraphEdge[];
};

type ProductGraphKind = "function" | "register" | "doc_section" | "pdf_section" | "doc_box";

type ForceNode = NodeObject<{
  id: string;
  kind: ProductGraphKind;
  label: string;
  weight: number;
  in: string[];
  out: string[];
  attr: Record<string, unknown>;
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

type ForceGraphMethods = {
  d3Force?: (forceName: string) => unknown;
  zoomToFit?: (durationMs?: number, padding?: number) => void;
};

type GraphPalette = {
  function: string;
  register: string;
  doc: string;
  pdf: string;
  edge: string;
  foreground: string;
  surface: string;
};

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false
}) as ComponentType<ForceGraphProps<ForceNode, ForceLink> & { ref?: (instance: ForceGraphMethods | null) => void }>;

const fallbackPalette: GraphPalette = {
  function: "#7dd3fc",
  register: "#facc15",
  doc: "#c084fc",
  pdf: "#fb7185",
  edge: "#60a5fa",
  foreground: "#f3f7f8",
  surface: "#0a0d0e"
};

export function WeightedForceGraph({
  graph,
  label = "Global weighted network graph",
  maxEdges,
  maxNodes,
  minEdgeWeight = 0,
  summaryLimit
}: {
  graph: WeightedGraphPayload;
  label?: string;
  maxEdges: number;
  maxNodes: number;
  minEdgeWeight?: number;
  summaryLimit: number;
}) {
  const summaryId = useId();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const graphRef = useRef<ForceGraphMethods | null>(null);
  const fitPendingRef = useRef(true);
  const [size, setSize] = useState({ width: 1280, height: 720 });
  const [ready, setReady] = useState(false);
  const [palette, setPalette] = useState<GraphPalette>(fallbackPalette);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) {
      return undefined;
    }
    const observer = new ResizeObserver(([entry]) => {
      const width = Math.max(320, Math.round(entry.contentRect.width));
      const height = Math.max(680, Math.round(Math.min(1080, width * 0.72)));
      setSize({ width, height });
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const root = getComputedStyle(document.documentElement);
    setPalette({
      function: cssValue(root, "--code", fallbackPalette.function),
      register: cssValue(root, "--register", fallbackPalette.register),
      doc: cssValue(root, "--doc", fallbackPalette.doc),
      pdf: cssValue(root, "--pdf", fallbackPalette.pdf),
      edge: cssValue(root, "--graph-edge", fallbackPalette.edge),
      foreground: cssValue(root, "--foreground", fallbackPalette.foreground),
      surface: cssValue(root, "--surface-1", fallbackPalette.surface)
    });
  }, [graph]);

  const graphData = useMemo(() => {
    const requestedMaxNodes = Math.max(1, Math.floor(maxNodes));
    const requestedMaxEdges = Math.max(1, Math.floor(maxEdges));
    const minimumWeight = Math.max(0, Math.min(1, minEdgeWeight));
    const nodes = graph.nodes.flatMap((node): ForceNode[] => {
      const kind = normalizeKind(node.kind);
      if (!kind || !node.id) {
        return [];
      }
      return [{
        id: String(node.id),
        label: String(node.label ?? node.id),
        kind,
        weight: Math.max(1, Number(node.weight ?? 1)),
        in: Array.isArray(node.in) ? node.in.map(String) : [],
        out: Array.isArray(node.out) ? node.out.map(String) : [],
        attr: isPlainObject(node.attr) ? node.attr : {}
      } satisfies ForceNode];
    }).slice(0, requestedMaxNodes);
    const nodeIds = new Set(nodes.map((node) => String(node.id)));
    const links = graph.edges
      .filter((edge) => {
        const weight = normalizedWeight(edge);
        return edge.src && edge.dst && nodeIds.has(edge.src) && nodeIds.has(edge.dst) && weight >= minimumWeight;
      })
      .slice(0, requestedMaxEdges)
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
  }, [graph, maxEdges, maxNodes, minEdgeWeight]);

  useEffect(() => {
    fitPendingRef.current = true;
    setReady(false);
    configureForceLayout(graphRef.current);
  }, [graphData.nodes.length, graphData.links.length]);

  const topNodes = useMemo(
    () => [...graphData.nodes].sort((left, right) => right.weight - left.weight).slice(0, summaryLimit),
    [graphData.nodes, summaryLimit]
  );
  const summaryNodes =
    graphData.nodes.length <= summaryLimit
      ? graphData.nodes
      : uniqueNodesForSummary([...topNodes, ...graphData.nodes.slice(-summaryLimit)]);
  const topLinks = useMemo(
    () => [...graphData.links].sort((left, right) => right.weight - left.weight).slice(0, summaryLimit),
    [graphData.links, summaryLimit]
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
      data-edge-total={graph.edges.length}
      data-max-edges={maxEdges}
      data-max-nodes={maxNodes}
      data-min-edge-weight={minEdgeWeight.toFixed(2)}
      data-ready={ready ? "true" : "false"}
      data-strongest-weight={topLinks[0]?.weight.toFixed(2) ?? "0.00"}
      data-testid="force-graph"
      data-weakest-weight={topLinks.at(-1)?.weight.toFixed(2) ?? "0.00"}
      data-node-count={graphData.nodes.length}
      data-node-total={graph.nodes.length}
      ref={containerRef}
      role="img"
    >
      <ForceGraph2D
        autoPauseRedraw={false}
        backgroundColor="rgba(0,0,0,0)"
        cooldownTicks={140}
        d3AlphaDecay={0.025}
        d3VelocityDecay={0.22}
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
        onEngineStop={() => {
          if (fitPendingRef.current) {
            graphRef.current?.zoomToFit?.(450, 72);
            fitPendingRef.current = false;
          }
          setReady(true);
        }}
        ref={(instance) => {
          graphRef.current = instance;
          configureForceLayout(instance);
        }}
        warmupTicks={90}
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

function configureForceLayout(instance: ForceGraphMethods | null) {
  if (!instance?.d3Force) {
    return;
  }
  const charge = instance.d3Force("charge") as { strength?: (value: number) => void } | undefined;
  charge?.strength?.(-120);
  const link = instance.d3Force("link") as {
    distance?: (value: number | ((link: ForceLink) => number)) => void;
    strength?: (value: number | ((link: ForceLink) => number)) => void;
  } | undefined;
  link?.distance?.((link: ForceLink) => 42 + (1 - link.weight) * 96);
  link?.strength?.((link: ForceLink) => 0.12 + link.weight * 0.38);
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
  const normalized = String(kind || "").toLowerCase();
  if (
    normalized === "register" ||
    normalized === "function" ||
    normalized === "doc_section" ||
    normalized === "doc_box" ||
    normalized === "pdf_section"
  ) {
    return normalized as ProductGraphKind;
  }
  return null;
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
  if (kind === "doc_section" || kind === "doc_box") {
    return palette.doc;
  }
  if (kind === "pdf_section") {
    return palette.pdf;
  }
  return palette.function;
}

function cssValue(styles: CSSStyleDeclaration, name: string, fallback: string) {
  return styles.getPropertyValue(name).trim() || fallback;
}

function shortLabel(value: string) {
  return value.length > 24 ? `${value.slice(0, 21)}...` : value;
}

function uniqueNodesForSummary(nodes: ForceNode[]) {
  const seen = new Set<string>();
  return nodes.filter((node) => {
    const id = String(node.id);
    if (seen.has(id)) {
      return false;
    }
    seen.add(id);
    return true;
  });
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
