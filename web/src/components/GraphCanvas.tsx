import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D, { type ForceGraphMethods, type NodeObject } from "react-force-graph-2d";
import type { ForceGraphData, ForceGraphNode, GraphNodeKind } from "../graph/types";
import { useTheme } from "../hooks/useTheme";

type GraphCanvasProps = {
  data: ForceGraphData;
  selectedId: string | null;
  focusKinds: ReadonlySet<GraphNodeKind> | null;
  onSelect: (node: ForceGraphNode | null) => void;
};

function readToken(name: string, fallback: string): string {
  if (typeof window === "undefined") {
    return fallback;
  }
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

function colorForKind(kind: GraphNodeKind, tokens: Record<string, string>): string {
  if (kind === "party") {
    return tokens.accent;
  }
  if (kind === "tender") {
    return tokens.indigo;
  }
  if (kind === "award") {
    return tokens.gold;
  }
  return tokens.muted;
}

function radiusForKind(kind: GraphNodeKind, selected: boolean): number {
  const base = kind === "party" ? 7 : kind === "tender" ? 6 : 5;
  return selected ? base + 2.5 : base;
}

export function GraphCanvas({ data, selectedId, focusKinds, onSelect }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<ForceGraphMethods<ForceGraphNode> | undefined>(undefined);
  const { theme } = useTheme();
  const [size, setSize] = useState({ width: 640, height: 420 });
  const tokens = useMemo(() => {
    void theme;
    return {
      accent: readToken("--accent", "#0b6e4f"),
      indigo: readToken("--indigo", "#243b6b"),
      gold: readToken("--gold", "#b8892d"),
      muted: readToken("--ink-muted", "#4a6354"),
      line: readToken("--line", "#c5d4c8"),
      ink: readToken("--ink", "#14261c"),
      bg: readToken("--bg-elevated", "#ffffff"),
      font: readToken("--font-body", "sans-serif"),
    };
  }, [theme]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || typeof ResizeObserver === "undefined") {
      return;
    }
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) {
        return;
      }
      const { width, height } = entry.contentRect;
      setSize({
        width: Math.max(320, Math.floor(width)),
        height: Math.max(280, Math.floor(height)),
      });
    });
    observer.observe(el);
    return () => {
      observer.disconnect();
    };
  }, []);

  useEffect(() => {
    const fg = graphRef.current;
    if (!fg) {
      return;
    }
    fg.d3Force("charge")?.strength(-180);
    fg.d3Force("link")?.distance(72);
  }, [data]);

  const graphData = useMemo(() => ({ nodes: data.nodes, links: data.links }), [data]);

  const isDimmed = (node: ForceGraphNode): boolean => {
    if (!focusKinds || focusKinds.size === 0) {
      return false;
    }
    return !focusKinds.has(node.kind);
  };

  return (
    <div ref={containerRef} className="graph-canvas" data-testid="graph-canvas">
      <ForceGraph2D
        ref={graphRef}
        width={size.width}
        height={size.height}
        graphData={graphData}
        nodeId="id"
        warmupTicks={40}
        cooldownTicks={80}
        nodeLabel={(node) => (node as ForceGraphNode).name}
        linkLabel={(link) => String((link as { rel_type?: string }).rel_type ?? "")}
        linkDirectionalArrowLength={3.5}
        linkDirectionalArrowRelPos={0.92}
        linkWidth={(link) => {
          const src = link.source as ForceGraphNode | string;
          const tgt = link.target as ForceGraphNode | string;
          const sid = typeof src === "string" ? src : src.id;
          const tid = typeof tgt === "string" ? tgt : tgt.id;
          return sid === selectedId || tid === selectedId ? 2.2 : 1;
        }}
        linkColor={(link) => {
          const src = link.source as ForceGraphNode | string;
          const tgt = link.target as ForceGraphNode | string;
          const sid = typeof src === "string" ? src : src.id;
          const tid = typeof tgt === "string" ? tgt : tgt.id;
          if (sid === selectedId || tid === selectedId) {
            return tokens.gold;
          }
          return tokens.line;
        }}
        backgroundColor="rgba(0,0,0,0)"
        nodeCanvasObject={(node, ctx, globalScale) => {
          const n = node as NodeObject<ForceGraphNode> & ForceGraphNode;
          const x = n.x ?? 0;
          const y = n.y ?? 0;
          const selected = n.id === selectedId;
          const dimmed = isDimmed(n);
          const radius = radiusForKind(n.kind, selected);
          ctx.globalAlpha = dimmed ? 0.22 : 1;
          ctx.beginPath();
          ctx.arc(x, y, radius, 0, 2 * Math.PI, false);
          ctx.fillStyle = colorForKind(n.kind, tokens);
          ctx.fill();
          if (selected) {
            ctx.strokeStyle = tokens.gold;
            ctx.lineWidth = 2.5 / Math.max(globalScale, 0.5);
            ctx.stroke();
          }
          const showLabel = selected || globalScale > 1.15 || !dimmed;
          if (showLabel && !dimmed) {
            const label = n.name;
            const fontSize = Math.max(11, 13 / globalScale);
            ctx.font = `600 ${fontSize}px ${tokens.font}`;
            ctx.textAlign = "center";
            ctx.textBaseline = "top";
            const text = label.length > 22 ? `${label.slice(0, 20)}…` : label;
            const metrics = ctx.measureText(text);
            const padX = 4;
            const padY = 2;
            const boxW = metrics.width + padX * 2;
            const boxH = fontSize + padY * 2;
            const boxY = y + radius + 3;
            ctx.fillStyle = tokens.bg;
            ctx.globalAlpha = dimmed ? 0.15 : 0.88;
            ctx.fillRect(x - boxW / 2, boxY, boxW, boxH);
            ctx.globalAlpha = dimmed ? 0.22 : 1;
            ctx.fillStyle = tokens.ink;
            ctx.fillText(text, x, boxY + padY);
          }
          ctx.globalAlpha = 1;
        }}
        onNodeClick={(node) => {
          onSelect(node as ForceGraphNode);
        }}
        onBackgroundClick={() => {
          onSelect(null);
        }}
      />
    </div>
  );
}
