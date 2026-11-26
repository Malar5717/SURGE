import { useEffect, useRef, useState } from "react";
import {
  CircleMarker,
  MapContainer,
  Polyline,
  TileLayer,
  useMap,
  useMapEvents,
} from "react-leaflet";
import {
  fetchCategories,
  fetchIncident,
  fetchIncidents,
  fetchLinks,
} from "../api.js";
import { GROUP_COLORS } from "../categories.js";
import AuthPanel from "./AuthPanel.jsx";
import DetailPanel from "./DetailPanel.jsx";
import FilterChips from "./FilterChips.jsx";
import ReportFlow from "./ReportFlow.jsx";

const CHENNAI = [13.0827, 80.2707];
const OSM_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

function groupKeys(categories) {
  return [
    ...new Set(
      categories
        .filter((category) => category.postable)
        .map((category) => category.group),
    ),
  ];
}

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
  const [categories, setCategories] = useState([]);
  const [status, setStatus] = useState("loading");
  const [selectedId, setSelectedId] = useState(null);
  const [activeGroups, setActiveGroups] = useState(new Set());
  const [reportOpen, setReportOpen] = useState(false);
  const [loginTick, setLoginTick] = useState(0);
  const requestId = useRef(0);
  const mapRef = useRef(null);
  const categoryBySlug = useRef(new Map());
  const incidentCategory = useRef(new Map());

  useEffect(() => {
    let active = true;
    fetchCategories()
      .then((data) => {
        if (!active) return;
        categoryBySlug.current = new Map(
          data.map((category) => [category.slug, category]),
        );
        setCategories(data);
        setActiveGroups(new Set(groupKeys(data)));
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  const groupOf = (slug) => categoryBySlug.current.get(slug)?.group ?? "other";

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
        incidentCategory.current.set(incident.id, incident.category);
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

  const toggleGroup = (key) => {
    const next = new Set(activeGroups);
    if (next.has(key)) {
      next.delete(key);
    } else {
      next.add(key);
    }
    setActiveGroups(next);
    if (selectedId !== null) {
      const category = incidentCategory.current.get(selectedId);
      if (category !== undefined && groupOf(category) === key && !next.has(key)) {
        setSelectedId(null);
      }
    }
  };

  const isHidden = (id) => {
    const category = incidentCategory.current.get(id);
    if (category === undefined || categories.length === 0) return false;
    return !activeGroups.has(groupOf(category));
  };

  const visibleIncidents = incidents.filter(
    (incident) =>
      categories.length === 0 || activeGroups.has(groupOf(incident.category)),
  );
  const visibleLinks = links.filter(
    (link) => !isHidden(link.incident_a) && !isHidden(link.incident_b),
  );
  const knownIncidents = new Map(
    incidents.map((incident) => [incident.id, incident]),
  );

  const revealGroup = (categorySlug) => {
    const group = groupOf(categorySlug);
    setActiveGroups((current) => {
      if (current.has(group)) return current;
      const next = new Set(current);
      next.add(group);
      return next;
    });
  };

  const startReport = () => {
    if (!user) {
      setLoginTick((count) => count + 1);
      return;
    }
    setReportOpen(true);
  };

  const handlePosted = (incident) => {
    setReportOpen(false);
    revealGroup(incident.category);
    if (mapRef.current) {
      mapRef.current.flyTo([incident.lat, incident.lng], 16);
    }
    setSelectedId(incident.id);
  };

  const handleOpenIncident = async (id) => {
    setReportOpen(false);
    try {
      const incident = await fetchIncident(id);
      revealGroup(incident.category);
      if (mapRef.current) {
        mapRef.current.flyTo([incident.lat, incident.lng], 16);
      }
    } catch {
      // The panel shows its own error if the incident has gone.
    }
    setSelectedId(id);
  };

  const handleLoginRequest = () => {
    setReportOpen(false);
    setLoginTick((count) => count + 1);
  };

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
          const color = GROUP_COLORS[groupOf(incident.category)] ?? "grey";
          return (
            <CircleMarker
              key={incident.id}
              center={[incident.lat, incident.lng]}
              radius={8}
              bubblingMouseEvents={false}
              pathOptions={{
                color,
                fillColor: color,
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
          <button type="button" className="auth-btn" onClick={startReport}>
            Report
          </button>
          <AuthPanel
            user={user}
            onAuth={onAuth}
            onLogout={onLogout}
            openSignal={loginTick}
          />
        </div>
        <FilterChips
          groups={groupKeys(categories)}
          active={activeGroups}
          onToggle={toggleGroup}
        />
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
          categories={categoryBySlug.current}
        />
      )}

      {reportOpen && (
        <ReportFlow
          categories={categories}
          onClose={() => setReportOpen(false)}
          onPosted={handlePosted}
          onOpenIncident={handleOpenIncident}
          onLogin={handleLoginRequest}
        />
      )}
    </div>
  );
}
