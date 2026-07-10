import { useCallback, useMemo, useState } from "react";
import { Map, useControl } from "react-map-gl/maplibre";
import { MapboxOverlay, type MapboxOverlayProps } from "@deck.gl/mapbox";
import { ColumnLayer } from "@deck.gl/layers";
import type { PickingInfo } from "@deck.gl/core";
import "maplibre-gl/dist/maplibre-gl.css";
import {
  elevationForMetric,
  listStateMetrics,
  type MapMetric,
  type StateMetric,
} from "../map/fixtures";
import { useTheme } from "../hooks/useTheme";

type NigeriaMapProps = {
  metric: MapMetric;
  selectedId: string | null;
  onSelect: (row: StateMetric | null) => void;
};

const LIGHT_STYLE = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";
const DARK_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

function DeckGLOverlay(props: MapboxOverlayProps) {
  const overlay = useControl<MapboxOverlay>(() => new MapboxOverlay(props));
  overlay.setProps(props);
  return null;
}

export function NigeriaMap({ metric, selectedId, onSelect }: NigeriaMapProps) {
  const { theme } = useTheme();
  const rows = useMemo(() => listStateMetrics(), []);
  const [viewState, setViewState] = useState({
    longitude: 8.0,
    latitude: 9.0,
    zoom: 5.2,
    pitch: 45,
    bearing: -10,
  });

  const layers = useMemo(() => {
    return [
      new ColumnLayer<StateMetric>({
        id: "state-columns",
        data: rows,
        diskResolution: 12,
        radius: 18000,
        extruded: true,
        pickable: true,
        elevationScale: 1,
        getPosition: (d) => [d.lng, d.lat],
        getElevation: (d) => elevationForMetric(d, metric),
        getFillColor: (d) => {
          const selected = d.id === selectedId;
          if (metric === "contract_volume") {
            return selected ? [184, 137, 45, 230] : [11, 110, 79, 200];
          }
          return selected ? [184, 137, 45, 230] : [36, 59, 107, 200];
        },
        updateTriggers: {
          getElevation: metric,
          getFillColor: [metric, selectedId],
        },
      }),
    ];
  }, [rows, metric, selectedId]);

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

  return (
    <div className="nigeria-map" data-testid="nigeria-map">
      <Map
        {...viewState}
        onMove={(event) => setViewState(event.viewState)}
        mapStyle={theme === "dark" ? DARK_STYLE : LIGHT_STYLE}
        style={{ width: "100%", height: "100%" }}
      >
        <DeckGLOverlay layers={layers} interleaved onClick={onClick} />
      </Map>
    </div>
  );
}
