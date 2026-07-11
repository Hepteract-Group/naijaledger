import { useCallback, useMemo, useState } from "react";
import { Map, NavigationControl, useControl } from "react-map-gl/maplibre";
import { MapboxOverlay, type MapboxOverlayProps } from "@deck.gl/mapbox";
import { ColumnLayer } from "@deck.gl/layers";
import type { PickingInfo } from "@deck.gl/core";
import "maplibre-gl/dist/maplibre-gl.css";
import {
  columnFillColor,
  elevationForMetric,
  formatMetricValue,
  listStateMetrics,
  maxMetric,
  metricIntensity,
  metricLabel,
  type MapMetric,
  type StateMetric,
} from "../map/fixtures";
import { useTheme } from "../hooks/useTheme";

type NigeriaMapProps = {
  metric: MapMetric;
  selectedId: string | null;
  onSelect: (row: StateMetric | null) => void;
};

const LIGHT_STYLE = "https://basemaps.cartocdn.com/gl/positron-nolabels-gl-style/style.json";
const DARK_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-nolabels-gl-style/style.json";

function DeckGLOverlay(props: MapboxOverlayProps) {
  const overlay = useControl<MapboxOverlay>(() => new MapboxOverlay(props));
  overlay.setProps(props);
  return null;
}

export function NigeriaMap({ metric, selectedId, onSelect }: NigeriaMapProps) {
  const { theme } = useTheme();
  const rows = useMemo(() => listStateMetrics(), []);
  const ceiling = useMemo(() => maxMetric(rows, metric), [rows, metric]);
  const [viewState, setViewState] = useState({
    longitude: 8.1,
    latitude: 9.2,
    zoom: 5.15,
    pitch: 38,
    bearing: -8,
  });

  const layers = useMemo(() => {
    return [
      new ColumnLayer<StateMetric>({
        id: "state-columns",
        data: rows,
        diskResolution: 24,
        radius: 16_000,
        extruded: true,
        pickable: true,
        elevationScale: 1,
        material: {
          ambient: 0.45,
          diffuse: 0.7,
          shininess: 24,
          specularColor: [40, 40, 40],
        },
        getPosition: (d) => [d.lng, d.lat],
        getElevation: (d) => elevationForMetric(d, metric),
        getFillColor: (d) =>
          columnFillColor(metricIntensity(d, metric, ceiling), metric, d.id === selectedId),
        updateTriggers: {
          getElevation: metric,
          getFillColor: [metric, selectedId, ceiling],
        },
      }),
    ];
  }, [rows, metric, selectedId, ceiling]);

  const onClick = useCallback(
    (info: PickingInfo) => {
      if (info.object) {
        onSelect(info.object as StateMetric);
      } else {
        onSelect(null);
      }
    },
    [onSelect],
  );

  const getTooltip = useCallback(
    (info: PickingInfo) => {
      const row = info.object as StateMetric | undefined;
      if (!row) {
        return null;
      }
      return {
        html: `<strong>${row.name}</strong><br/>${metricLabel(metric)}: ${formatMetricValue(row, metric)}`,
        style: {
          background: "var(--bg-elevated, #fff)",
          color: "var(--ink, #14261c)",
          border: "1px solid var(--line, #c5d4c8)",
          fontFamily: "var(--font-body, sans-serif)",
          fontSize: "13px",
          padding: "8px 10px",
          borderRadius: "4px",
        },
      };
    },
    [metric],
  );

  return (
    <div className="nigeria-map" data-testid="nigeria-map">
      <Map
        {...viewState}
        onMove={(event) => setViewState(event.viewState)}
        mapStyle={theme === "dark" ? DARK_STYLE : LIGHT_STYLE}
        style={{ width: "100%", height: "100%" }}
        attributionControl={false}
      >
        <NavigationControl position="top-right" showCompass={false} />
        <DeckGLOverlay layers={layers} interleaved onClick={onClick} getTooltip={getTooltip} />
      </Map>
    </div>
  );
}
