const BASE = "/api";

async function getJson(path) {
  const response = await fetch(`${BASE}${path}`);
  if (!response.ok) {
    throw new Error(`GET ${path} failed with ${response.status}`);
  }
  return response.json();
}

async function sendJson(path, body) {
  const response = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (response.status === 204) return null;

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(`POST ${path} failed with ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return data;
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

export async function fetchMe() {
  const response = await fetch(`${BASE}/auth/me`);
  if (response.status === 401) return null;
  if (!response.ok) {
    throw new Error(`GET /auth/me failed with ${response.status}`);
  }
  return response.json();
}

export function signup(handle, password) {
  return sendJson("/auth/signup", { handle, password });
}

export function login(handle, password) {
  return sendJson("/auth/login", { handle, password });
}

export function logout() {
  return sendJson("/auth/logout");
}
