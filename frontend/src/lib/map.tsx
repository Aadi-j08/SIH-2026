/**
 * Phase C — free geo discovery map (Leaflet + OpenStreetMap tiles).
 * No key required: uses the public OSM raster tile server. Marker icons from
 * Leaflet's bundled images; the default-icon fix is needed under Vite because
 * the images are emitted as separate assets.
 */
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { useEffect } from "react";
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";

// Vite rewrites the bundled marker assets, so re-point the icons at the resolved
// URLs so they actually render on the map.
const _icon = L.icon({
  iconUrl: new URL("leaflet/dist/images/marker-icon.png", import.meta.url).href,
  iconRetinaUrl: new URL("leaflet/dist/images/marker-icon-2x.png", import.meta.url).href,
  shadowUrl: new URL("leaflet/dist/images/marker-shadow.png", import.meta.url).href,
  className: "sahakarsetu-marker",
});

export interface MapMarker {
  lat: number;
  lng: number;
  label?: string;
  color?: "blue" | "red" | "green";
  onClick?: () => void;
}

const COLOR_CLASS = {
  blue: "marker-blue",
  red: "marker-red",
  green: "marker-green",
};

export interface LocationMapProps {
  center: [number, number];
  markers?: MapMarker[];
  zoom?: number;
  height?: number | string;
  interactive?: boolean;
  onLoaded?: () => void;
}

function FitOrZoom({ markers, zoom, onLoaded }: { markers: MapMarker[]; zoom?: number; onLoaded?: () => void }) {
  const map = useMap();
  useEffect(() => {
    if (markers.length > 1) {
      const b = L.latLngBounds(markers.map((m) => [m.lat, m.lng]));
      map.fitBounds(b, { padding: [40, 40], maxZoom: 15 });
    } else if (markers.length === 1) {
      map.setView([markers[0].lat, markers[0].lng], zoom ?? 15);
    } else {
      map.setView([markers[0]?.lat ?? 0, markers[0]?.lng ?? 0], zoom ?? 13);
    }
    onLoaded?.();
  }, [markers, map, zoom, onLoaded]);
  return null;
}

/** A small, dependency-light map for booking locations and nearby workers. */
export function LocationMap({ center, markers = [], zoom = 14, height = 240, interactive = true, onLoaded }: LocationMapProps) {
  return (
    <div className="map-wrapper" style={{ height, width: "100%", borderRadius: 8, overflow: "hidden" }}>
      <MapContainer
        center={center}
        zoom={zoom}
        style={{ height: "100%", width: "100%" }}
        scrollWheelZoom={interactive}
        dragging={interactive}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitOrZoom markers={markers} zoom={zoom} onLoaded={onLoaded} />
        {markers.map((m, i) => (
          <Marker
            key={`${m.lat}-${m.lng}-${i}`}
            position={[m.lat, m.lng]}
            icon={L.divIcon({
              className: `sahakarsetu-marker-pin ${COLOR_CLASS[m.color ?? "blue"]}`,
              html: `<span class="pin-dot"></span>`,
              iconSize: [26, 26],
              iconAnchor: [13, 26],
            })}
            eventHandlers={{ click: m.onClick }}
          >
            {m.label ? <Popup>{m.label}</Popup> : null}
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}

void _icon;
