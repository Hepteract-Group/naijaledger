import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D, { type NodeObject } from "react-force-graph-2d";
import type { ForceGraphData, ForceGraphNode, GraphNodeKind } from "../graph/types";
import { useTheme } from "../hooks/useTheme";

type GraphCanvasProps = {
  data: ForceGraphData;
  selectedId: string | null;
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

export function GraphCanvas({ data, selectedId, onSelect }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { theme } = useTheme();
  const [size, setSize] = useState({ width: 640, height: 420 });
  const tokens = useMemo(
    () => ({
      accent: readToken("--accent", "#0b6e4f"),
      indigo: readToken("--indigo", "#243b6b"),
      gold: readToken("--gold", "#b8892d"),
      muted: readToken("--ink-muted", "#4a6354"),
      line: readToken("--line", "#c5d4c8"),
      ink: readToken("--ink", "#14261c"),
      font: readToken("--font-body", "sans-serif"),
    }),
    [theme],
  );

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

  const graphData = useMemo(() => ({ nodes: data.nodes, links: data.links }), [data]);

  return (
    <div ref={containerRef} className="graph-canvas" data-testid="graph-canvas">
      <ForceGraph2D
        width={size.width}
        height={size.height}
        graphData={graphData}
        nodeId="id"
        nodeLabel={(node) => (node as ForceGraphNode).name}
        linkLabel={(link) => String((link as { rel_type?: string }).rel_type ?? "")}
        linkDirectionalArrowLength={4}
        linkDirectionalArrowRelPos={1}
        linkWidth={1.2}
        linkColor={() => tokens.line}
        backgroundColor="rgba(0,0,0,0)"
        nodeCanvasObject={(node, ctx, globalScale) => {
          const n = node as NodeObject<ForceGraphNode> & ForceGraphNode;
          const x = n.x ?? 0;
          const y = n.y ?? 0;
          const selected = n.id === selectedId;
          const radius = selected ? 8 : 6;
          ctx.beginPath();
          ctx.arc(x, y, radius, 0, 2 * Math.PI, false);
          ctx.fillStyle = colorForKind(n.kind, tokens);
          ctx.fill();
          if (selected) {
            ctx.strokeStyle = tokens.gold;
            ctx.lineWidth = 2;
            ctx.stroke();
          }
          const label = n.name;
          const fontSize = 12 / globalScale;
          ctx.font = `${fontSize}px ${tokens.font}`;
          ctx.textAlign = "center";
          ctx.textBaseline = "top";
          ctx.fillStyle = tokens.ink;
          ctx.fillText(label.length > 28 ? `${label.slice(0, 26)}…` : label, x, y + radius + 2);
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
