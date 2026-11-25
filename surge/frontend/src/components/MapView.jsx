import { useEffect, useRef, useState } from "react";
import {
  CircleMarker,
  MapContainer,
  Polyline,
  TileLayer,
  useMap,
  useMapEvents,
} from "react-leaflet";
import { fetchIncidents, fetchLinks } from "../api.js";
import { CATEGORIES, CATEGORY_BY_KEY } from "../categories.js";
import AuthPanel from "./AuthPanel.jsx";
import DetailPanel from "./DetailPanel.jsx";
import FilterChips from "./FilterChips.jsx";

const CHENNAI = [13.0827, 80.2707];
const OSM_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
const ALL_CATEGORIES = new Set(CATEGORIES.map((category) => category.key));

function toBox(bounds) {
  return {
    minLat: bounds.getSouth(),
    maxLat: bounds.getNorth(),
    minLng: bounds.getWest(),
    maxLng: bounds.getEast(),
  };
}

function BoundsWatcher({ onBounds, onMapClick }) {
  const map = useMap();
  const timer = useRef(null);

  useEffect(() => {
    onBounds(toBox(map.getBounds()));
    return () => clearTimeout(timer.current);
  }, [map]);

  useMapEvents({
    moveend() {
      clearTimeout(timer.current);
      timer.current = setTimeout(() => onBounds(toBox(map.getBounds())), 300);
    },
    click() {
      onMapClick();
    },
  });

  return null;
}

function MapController({ onReady }) {
  const map = useMap();

  useEffect(() => {
    onReady(map);
  }, [map]);

  return null;
}

export default function MapView({ user, onAuth, onLogout }) {
  const [incidents, setIncidents] = useState([]);
  const [links, setLinks] = useState([]);
  const [status, setStatus] = useState("loading");
  const [selectedId, setSelectedId] = useState(null);
  const [activeCategories, setActiveCategories] = useState(ALL_CATEGORIES);
  const requestId = useRef(0);
  const mapRef = useRef(null);
  const categoryCache = useRef(new Map());

  const load = async (box) => {
    const current = ++requestId.current;
    setStatus("loading");
    try {
      const [incidentData, linkData] = await Promise.all([
        fetchIncidents(box),
        fetchLinks(box),
      ]);
      if (current !== requestId.current) return;
      for (const incident of incidentData) {
        categoryCache.current.set(incident.id, incident.category);
      }
      setIncidents(incidentData);
      setLinks(linkData);
      setStatus(incidentData.length === 0 ? "empty" : "ready");
    } catch {
      if (current !== requestId.current) return;
      setIncidents([]);
      setLinks([]);
      setStatus("error");
    }
  };

  const selectLinked = (id) => {
    const link = links.find(
      (item) =>
        (item.incident_a === selectedId && item.incident_b === id) ||
        (item.incident_b === selectedId && item.incident_a === id),
    );
    if (link && mapRef.current) {
      const target =
        link.incident_a === id
          ? [link.a_lat, link.a_lng]
          : [link.b_lat, link.b_lng];
      mapRef.current.panTo(target);
    }
    setSelectedId(id);
  };

  const toggleCategory = (key) => {
    const next = new Set(activeCategories);
    if (next.has(key)) {
      next.delete(key);
    } else {
      next.add(key);
    }
    setActiveCategories(next);
    if (
      selectedId !== null &&
      categoryCache.current.get(selectedId) === key &&
      !next.has(key)
    ) {
      setSelectedId(null);
    }
  };

  const isHidden = (id) => {
    const category = categoryCache.current.get(id);
    return category !== undefined && !activeCategories.has(category);
  };

  const visibleIncidents = incidents.filter((incident) =>
    activeCategories.has(incident.category),
  );
  const visibleLinks = links.filter(
    (link) => !isHidden(link.incident_a) && !isHidden(link.incident_b),
  );
  const knownIncidents = new Map(
    incidents.map((incident) => [incident.id, incident]),
  );

  return (
    <div className="map-wrap">
      <MapContainer center={CHENNAI} zoom={12} className="map">
        <TileLayer
          attribution={OSM_ATTRIBUTION}
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <BoundsWatcher onBounds={load} onMapClick={() => setSelectedId(null)} />
        <MapController onReady={(map) => (mapRef.current = map)} />

        {visibleLinks.map((link) => {
          const selected =
            link.incident_a === selectedId || link.incident_b === selectedId;
          return (
            <Polyline
              key={`${link.incident_a}-${link.incident_b}`}
              positions={[
                [link.a_lat, link.a_lng],
                [link.b_lat, link.b_lng],
              ]}
              bubblingMouseEvents={false}
              pathOptions={{
                color: selected ? "#111111" : "#555555",
                weight: selected ? 4 : 1.5,
                opacity: selected ? 0.9 : 0.6,
              }}
            />
          );
        })}

        {visibleIncidents.map((incident) => {
          const category = CATEGORY_BY_KEY[incident.category];
          return (
            <CircleMarker
              key={incident.id}
              center={[incident.lat, incident.lng]}
              radius={8}
              bubblingMouseEvents={false}
              pathOptions={{
                color: category.color,
                fillColor: category.color,
                fillOpacity: 0.8,
                weight: 1,
              }}
              eventHandlers={{
                click: () => setSelectedId(incident.id),
              }}
            />
          );
        })}
      </MapContainer>

      <div className="overlay-top">
        <div className="auth-row">
          <AuthPanel user={user} onAuth={onAuth} onLogout={onLogout} />
        </div>
        <FilterChips active={activeCategories} onToggle={toggleCategory} />
        {status === "loading" && <div className="status">Loading…</div>}
        {status === "empty" && <div className="status">No incidents here</div>}
        {status === "error" && (
          <div className="status status-error">
            Cannot reach the backend. Is it running on port 8000?
          </div>
        )}
      </div>

      {selectedId !== null && (
        <DetailPanel
          incidentId={selectedId}
          onClose={() => setSelectedId(null)}
          onSelectLinked={selectLinked}
          knownIncidents={knownIncidents}
        />
      )}
    </div>
  );
}
