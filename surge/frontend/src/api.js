const BASE = "/api";

async function getJson(path) {
  const response = await fetch(`${BASE}${path}`);
  if (!response.ok) {
    throw new Error(`GET ${path} failed with ${response.status}`);
  }
  return response.json();
}

export function fetchIncidents({ minLat, maxLat, minLng, maxLng }) {
  const params = new URLSearchParams({
    min_lat: minLat,
    max_lat: maxLat,
    min_lng: minLng,
    max_lng: maxLng,
  });
  return getJson(`/incidents?${params.toString()}`);
}

export function fetchIncident(id) {
  return getJson(`/incidents/${id}`);
}

export function fetchLinks({ minLat, maxLat, minLng, maxLng }) {
  const params = new URLSearchParams({
    min_lat: minLat,
    max_lat: maxLat,
    min_lng: minLng,
    max_lng: maxLng,
  });
  return getJson(`/links?${params.toString()}`);
}
