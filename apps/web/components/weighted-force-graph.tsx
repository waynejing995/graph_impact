"use client";

import dynamic from "next/dynamic";
import { useEffect, useId, useMemo, useRef, useState, type ComponentType } from "react";
import type { ForceGraphProps, LinkObject, NodeObject } from "react-force-graph-2d";

export type WeightedGraphNode = {
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
  source?: string;
  sources?: Array<string | Record<string, unknown>>;
  attr?: Record<string, unknown>;
};

export type WeightedGraphPayload = {
  nodes: WeightedGraphNode[];
  edges: WeightedGraphEdge[];
};

type ProductGraphKind = "function" | "register" | "doc";

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
  graph2ScreenCoords?: (x: number, y: number) => { x: number; y: number };
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
  onNodeSelect,
  selectedNodeId,
  summaryLimit
}: {
  graph: WeightedGraphPayload;
  label?: string;
  maxEdges: number;
  maxNodes: number;
  minEdgeWeight?: number;
  onNodeSelect?: (node: WeightedGraphNode) => void;
  selectedNodeId?: string;
  summaryLimit: number;
}) {
  const summaryId = useId();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const graphRef = useRef<ForceGraphMethods | null>(null);
  const fitPendingRef = useRef(true);
  const hitTargetRefreshTimerRef = useRef<number | null>(null);
  const [size, setSize] = useState({ width: 1280, height: 720 });
  const [ready, setReady] = useState(false);
  const [canvasHitTargets, setCanvasHitTargets] = useState("[]");
  const [hoveredCanvasNodeId, setHoveredCanvasNodeId] = useState("");
  const [lastNodeSelectSource, setLastNodeSelectSource] = useState("");
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

  useEffect(() => () => {
    if (hitTargetRefreshTimerRef.current !== null) {
      window.clearTimeout(hitTargetRefreshTimerRef.current);
    }
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
  const layoutProfile =
    graphData.nodes.length >= 150 || graphData.links.length >= 300 ? "dense" : "standard";

  useEffect(() => {
    fitPendingRef.current = true;
    setReady(false);
    setCanvasHitTargets("[]");
    setHoveredCanvasNodeId("");
    setLastNodeSelectSource("");
    configureForceLayout(graphRef.current, layoutProfile);
  }, [graphData.nodes.length, graphData.links.length, layoutProfile]);

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
  const sharedRegisterCount = useMemo(
    () => graphData.nodes.filter((node) => isSharedRegisterNode(node)).length,
    [graphData.nodes]
  );

  function selectNodeFromCanvas(node: ForceNode) {
    setLastNodeSelectSource("canvas-node-click");
    onNodeSelect?.(forceNodeToPayload(node));
  }

  function selectNodeFromSummary(node: ForceNode) {
    setLastNodeSelectSource("summary-button");
    onNodeSelect?.(forceNodeToPayload(node));
  }

  return (
    <div
      aria-describedby={summaryId}
      aria-label={label}
      className="force-graph-shell"
      data-edge-count={graphData.links.length}
      data-edge-total={graph.edges.length}
      data-layout-profile={layoutProfile}
      data-max-edges={maxEdges}
      data-max-nodes={maxNodes}
      data-min-edge-weight={minEdgeWeight.toFixed(2)}
      data-ready={ready ? "true" : "false"}
      data-canvas-hit-targets={canvasHitTargets}
      data-hovered-canvas-node-id={hoveredCanvasNodeId}
      data-last-node-select-source={lastNodeSelectSource}
      data-shared-register-count={sharedRegisterCount}
      data-strongest-weight={topLinks[0]?.weight.toFixed(2) ?? "0.00"}
      data-testid="force-graph"
      data-weakest-weight={topLinks.at(-1)?.weight.toFixed(2) ?? "0.00"}
      data-node-count={graphData.nodes.length}
      data-node-total={graph.nodes.length}
      ref={containerRef}
      role="img"
    >
      <ForceGraph2D
        autoPauseRedraw={layoutProfile === "dense"}
        backgroundColor="rgba(0,0,0,0)"
        cooldownTicks={layoutProfile === "dense" ? 70 : 140}
        d3AlphaDecay={0.025}
        d3VelocityDecay={0.22}
        enableNodeDrag
        enablePanInteraction
        enablePointerInteraction
        enableZoomInteraction
        graphData={graphData}
        height={size.height}
        linkColor={() => (layoutProfile === "dense" ? "rgba(96, 165, 250, 0.34)" : palette.edge)}
        linkDirectionalArrowLength={(link) => (link.weight > 0.72 ? (layoutProfile === "dense" ? 2.5 : 4) : 0)}
        linkDirectionalParticles={(link) => (layoutProfile === "dense" ? 0 : link.weight > 0.78 ? 2 : 0)}
        linkDirectionalParticleWidth={(link) => 1.2 + link.weight * 2}
        linkLabel={(link) => link.label}
        linkWidth={(link) => (layoutProfile === "dense" ? 0.25 + link.weight * 1.1 : 0.45 + link.weight * 2.4)}
        nodeCanvasObject={(node, context, globalScale) =>
          drawNodeLabel(node, context, globalScale, palette, node.id === selectedNodeId)
        }
        nodeCanvasObjectMode={() => "after"}
        nodeColor={(node) => colorForKind(node.kind, palette)}
        nodeId="id"
        nodeLabel={(node) => `${node.label} (${node.kind}, weight ${node.weight})`}
        onNodeHover={(node) => setHoveredCanvasNodeId(node?.id ? String(node.id) : "")}
        onNodeClick={(node) => selectNodeFromCanvas(node)}
        nodeRelSize={4}
        nodeVal={(node) => Math.max(2, node.weight)}
        onEngineStop={() => {
          if (hitTargetRefreshTimerRef.current !== null) {
            window.clearTimeout(hitTargetRefreshTimerRef.current);
          }
          const publishHitTargets = () => {
            setCanvasHitTargets(buildCanvasHitTargets(graphRef.current, summaryNodes));
            setReady(true);
          };
          if (fitPendingRef.current) {
            graphRef.current?.zoomToFit?.(450, 72);
            fitPendingRef.current = false;
            hitTargetRefreshTimerRef.current = window.setTimeout(publishHitTargets, 500);
            return;
          }
          publishHitTargets();
        }}
        ref={(instance) => {
          graphRef.current = instance;
          configureForceLayout(instance, layoutProfile);
        }}
        warmupTicks={layoutProfile === "dense" ? 35 : 90}
        width={size.width}
      />
      <div className="graph-accessibility-summary" id={summaryId}>
        <span>visible nodes {graphData.nodes.length} / loaded {graph.nodes.length}</span>
        <span>visible edges {graphData.links.length} / loaded {graph.edges.length}</span>
        <span>shared registers {sharedRegisterCount}</span>
        {kindCounts.map(([kind, count]) => (
          <span key={`kind-${kind}`}>{kind} {count}</span>
        ))}
        {summaryNodes.map((node) => (
          onNodeSelect ? (
            <button
              aria-pressed={node.id === selectedNodeId}
              className="graph-summary-node"
              key={`node-${node.id}`}
              onClick={() => selectNodeFromSummary(node)}
              type="button"
            >
              {node.label}
            </button>
          ) : (
            <span key={`node-${node.id}`}>{node.label}</span>
          )
        ))}
        {topLinks.map((link, index) => (
          <span key={`link-${index}-${link.relation}`}>{link.relation} / {link.weight.toFixed(2)}</span>
        ))}
      </div>
    </div>
  );
}

function buildCanvasHitTargets(instance: ForceGraphMethods | null, nodes: ForceNode[]) {
  if (!instance?.graph2ScreenCoords) {
    return "[]";
  }
  return JSON.stringify(
    nodes.flatMap((node) => {
      const x = Number(node.x);
      const y = Number(node.y);
      if (!Number.isFinite(x) || !Number.isFinite(y)) {
        return [];
      }
      const point = instance.graph2ScreenCoords?.(x, y);
      if (!point || !Number.isFinite(point.x) || !Number.isFinite(point.y)) {
        return [];
      }
      return [{
        id: node.id,
        label: node.label,
        x: Math.round(point.x),
        y: Math.round(point.y)
      }];
    })
  );
}

function configureForceLayout(instance: ForceGraphMethods | null, layoutProfile: "dense" | "standard") {
  if (!instance?.d3Force) {
    return;
  }
  const charge = instance.d3Force("charge") as { strength?: (value: number) => void } | undefined;
  charge?.strength?.(layoutProfile === "dense" ? -90 : -120);
  const link = instance.d3Force("link") as {
    distance?: (value: number | ((link: ForceLink) => number)) => void;
    strength?: (value: number | ((link: ForceLink) => number)) => void;
  } | undefined;
  link?.distance?.((link: ForceLink) => (layoutProfile === "dense" ? 34 : 42) + (1 - link.weight) * (layoutProfile === "dense" ? 70 : 96));
  link?.strength?.((link: ForceLink) => (layoutProfile === "dense" ? 0.16 : 0.12) + link.weight * (layoutProfile === "dense" ? 0.32 : 0.38));
}

function drawNodeLabel(
  node: ForceNode,
  context: CanvasRenderingContext2D,
  globalScale: number,
  palette: GraphPalette,
  selected = false
) {
  if (globalScale < 0.42) {
    return;
  }
  const label = shortLabel(node.label);
  const fontSize = Math.max(8, 11 / globalScale);
  const x = Number(node.x ?? 0);
  const y = Number(node.y ?? 0);
  if (isSharedRegisterNode(node)) {
    const radius = Math.max(8, Math.sqrt(Math.max(1, node.weight)) * 4.2);
    context.save();
    context.lineWidth = Math.max(1.5, 2.5 / globalScale);
    context.strokeStyle = palette.doc;
    context.beginPath();
    context.arc(x, y, radius, 0, Math.PI * 2);
    context.stroke();
    context.setLineDash([Math.max(3, 5 / globalScale), Math.max(2, 4 / globalScale)]);
    context.strokeStyle = palette.register;
    context.beginPath();
    context.arc(x, y, radius + 4 / globalScale, 0, Math.PI * 2);
    context.stroke();
    context.restore();
  }
  if (selected) {
    const radius = Math.max(10, Math.sqrt(Math.max(1, node.weight)) * 4.8);
    context.save();
    context.lineWidth = Math.max(2, 3 / globalScale);
    context.strokeStyle = palette.foreground;
    context.setLineDash([Math.max(4, 6 / globalScale), Math.max(2, 4 / globalScale)]);
    context.beginPath();
    context.arc(x, y, radius + 7 / globalScale, 0, Math.PI * 2);
    context.stroke();
    context.restore();
  }
  context.font = `700 ${fontSize}px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`;
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.lineWidth = Math.max(2, 3 / globalScale);
  context.strokeStyle = palette.surface;
  context.strokeText(label, x, y + 13 / globalScale);
  context.fillStyle = palette.foreground;
  context.fillText(label, x, y + 13 / globalScale);
}

function forceNodeToPayload(node: ForceNode): WeightedGraphNode {
  return {
    id: node.id,
    kind: node.kind,
    label: node.label,
    weight: node.weight,
    in: node.in,
    out: node.out,
    attr: node.attr
  };
}

function normalizeKind(kind: string | undefined) {
  const normalized = String(kind || "").toLowerCase();
  if (normalized === "register" || normalized === "function" || normalized === "doc") {
    return normalized as ProductGraphKind;
  }
  if (normalized === "doc_section" || normalized === "doc_box" || normalized === "pdf_section") {
    return "doc";
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
  if (kind === "doc") {
    return palette.doc;
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

function isSharedRegisterNode(node: Pick<ForceNode, "kind" | "attr">) {
  if (node.kind !== "register") {
    return false;
  }
  const source = node.attr.source;
  if (!Array.isArray(source)) {
    return false;
  }
  const corpora = new Set<string>();
  for (const item of source) {
    if (!isPlainObject(item)) {
      continue;
    }
    const corpus = String(item.corpus_id ?? item.repo ?? "").trim();
    if (corpus) {
      corpora.add(corpus);
    }
  }
  return corpora.size > 1;
}
