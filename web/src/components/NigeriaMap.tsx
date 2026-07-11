import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Map, NavigationControl, useControl, type MapRef } from "react-map-gl/maplibre";
import { MapboxOverlay, type MapboxOverlayProps } from "@deck.gl/mapbox";
import { ColumnLayer } from "@deck.gl/layers";
import type { PickingInfo } from "@deck.gl/core";
import "maplibre-gl/dist/maplibre-gl.css";
import {
  columnFillColor,
  elevationForMetric,
  formatMetricValue,
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
  /** Full national series (live or demo); focus filters the layer. */
  data: StateMetric[];
  /** State code from the shared facet bar — filters columns + flies camera. */
  focusId?: string | null;
  onSelect: (row: StateMetric | null) => void;
};

const LIGHT_STYLE = "https://basemaps.cartocdn.com/gl/positron-nolabels-gl-style/style.json";
const DARK_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-nolabels-gl-style/style.json";

const NATIONAL_VIEW = {
  longitude: 8.1,
  latitude: 9.2,
  zoom: 5.15,
  pitch: 38,
  bearing: -8,
};

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function DeckGLOverlay(props: MapboxOverlayProps) {
  const overlay = useControl<MapboxOverlay>(() => new MapboxOverlay(props));
  overlay.setProps(props);
  return null;
}

function viewForFocus(row: StateMetric | null) {
  if (row === null) {
    return NATIONAL_VIEW;
  }
  return {
    longitude: row.lng,
    latitude: row.lat,
    zoom: 7.2,
    pitch: 42,
    bearing: -12,
  };
}

export function NigeriaMap({
  metric,
  selectedId,
  data,
  focusId = null,
  onSelect,
}: NigeriaMapProps) {
  const { theme } = useTheme();
  const mapRef = useRef<MapRef>(null);
  const allRows = data;
  const focusCode = focusId?.trim().toUpperCase() || null;
  const rows = useMemo(() => {
    if (!focusCode) {
      return allRows;
    }
    return allRows.filter((row) => row.id === focusCode);
  }, [allRows, focusCode]);
  // Keep national scale so a single focused column keeps relative intensity.
  const ceiling = useMemo(() => maxMetric(allRows, metric), [allRows, metric]);
  const [viewState, setViewState] = useState(NATIONAL_VIEW);

  useEffect(() => {
    const focused = focusCode ? (allRows.find((row) => row.id === focusCode) ?? null) : null;
    const next = viewForFocus(focused);
    const map = mapRef.current?.getMap();
    if (map) {
      map.flyTo({
        center: [next.longitude, next.latitude],
        zoom: next.zoom,
        pitch: next.pitch,
        bearing: next.bearing,
        duration: 900,
      });
    } else {
      setViewState(next);
    }
  }, [focusCode, allRows]);

  const layers = useMemo(() => {
    return [
      new ColumnLayer<StateMetric>({
        id: "state-columns",
        data: rows,
        diskResolution: 24,
        radius: focusCode ? 22_000 : 16_000,
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
        getElevation: (d) => elevationForMetric(d, metric, ceiling),
        getFillColor: (d) =>
          columnFillColor(metricIntensity(d, metric, ceiling), metric, d.id === selectedId),
        updateTriggers: {
          getElevation: [metric, ceiling],
          getFillColor: [metric, selectedId, ceiling],
        },
      }),
    ];
  }, [rows, metric, selectedId, ceiling, focusCode]);

  const onClick = useCallback(
    (info: PickingInfo) => {
      if (info.object) {
        onSelect(info.object as StateMetric);
      } else if (!focusCode) {
        onSelect(null);
      }
    },
    [onSelect, focusCode],
  );

  const getTooltip = useCallback(
    (info: PickingInfo) => {
      const row = info.object as StateMetric | undefined;
      if (!row) {
        return null;
      }
      return {
        html: `<strong>${escapeHtml(row.name)}</strong><br/>${escapeHtml(metricLabel(metric))}: ${escapeHtml(formatMetricValue(row, metric))}`,
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
        ref={mapRef}
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
