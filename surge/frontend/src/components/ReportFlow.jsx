import { useEffect, useMemo, useState } from "react";
import { createIncident, fetchCandidates } from "../api.js";
import { groupLabel } from "../categories.js";
import CameraCapture from "./CameraCapture.jsx";

const MAX_DESCRIPTION = 280;
const GOOD_ACCURACY_M = 50;
const MAX_ACCURACY_M = 100;
const WEAK_AFTER_MS = 20000;
const MAX_LINKS = 3;

function distanceText(metres) {
  return metres < 1000
    ? `${Math.round(metres)} m`
    : `${(metres / 1000).toFixed(1)} km`;
}

function ageText(iso) {
  const minutes = Math.max(
    0,
    Math.round((Date.now() - new Date(iso).getTime()) / 60000),
  );
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours} h ago`;
  return `${Math.round(hours / 24)} days ago`;
}

function reasonFrom(body) {
  if (!body) return null;
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail) && body.detail[0]?.msg) {
    return body.detail[0].msg;
  }
  return null;
}

export default function ReportFlow({
  categories,
  onClose,
  onPosted,
  onOpenIncident,
  onLogin,
}) {
  const [photo, setPhoto] = useState(null);
  const [preview, setPreview] = useState("");
  const [step, setStep] = useState("camera");
  const [position, setPosition] = useState(null);
  const [geoError, setGeoError] = useState("");
  const [allowWeak, setAllowWeak] = useState(false);
  const [category, setCategory] = useState("");
  const [description, setDescription] = useState("");
  const [candidates, setCandidates] = useState([]);
  const [candidateStatus, setCandidateStatus] = useState("idle");
  const [links, setLinks] = useState(new Set());
  const [message, setMessage] = useState("");
  const [duplicateId, setDuplicateId] = useState(null);
  const [needLogin, setNeedLogin] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (step !== "details") return undefined;
    if (!navigator.geolocation) {
      setGeoError("This browser cannot read your location.");
      return undefined;
    }
    const watchId = navigator.geolocation.watchPosition(
      (result) => {
        setGeoError("");
        setPosition({
          lat: result.coords.latitude,
          lng: result.coords.longitude,
          accuracy: result.coords.accuracy,
        });
      },
      (error) => {
        setGeoError(
          error.code === error.PERMISSION_DENIED
            ? "Location permission was denied. Allow location access to report a problem."
            : "Your location is not available. Move somewhere open and try again.",
        );
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 },
    );
    return () => navigator.geolocation.clearWatch(watchId);
  }, [step]);

  useEffect(() => {
    if (step !== "details") return undefined;
    const timer = setTimeout(() => setAllowWeak(true), WEAK_AFTER_MS);
    return () => clearTimeout(timer);
  }, [step]);

  useEffect(() => {
    if (!preview) return undefined;
    return () => URL.revokeObjectURL(preview);
  }, [preview]);

  const accuracy = position ? position.accuracy : null;
  const ready =
    position !== null &&
    (accuracy <= GOOD_ACCURACY_M ||
      (allowWeak && accuracy <= MAX_ACCURACY_M));

  useEffect(() => {
    if (step !== "details" || !category || !ready) {
      setCandidates([]);
      setCandidateStatus("idle");
      return undefined;
    }
    let active = true;
    setCandidateStatus("loading");
    setLinks(new Set());
    fetchCandidates({
      category,
      lat: position.lat.toFixed(6),
      lng: position.lng.toFixed(6),
      accuracyM: String(Math.round(position.accuracy)),
    })
      .then((data) => {
        if (!active) return;
        setCandidates(data.slice(0, MAX_LINKS));
        setCandidateStatus(data.length ? "ready" : "empty");
      })
      .catch(() => {
        if (!active) return;
        setCandidates([]);
        setCandidateStatus("error");
      });
    return () => {
      active = false;
    };
  }, [step, category, ready]);

  const grouped = useMemo(() => {
    const map = new Map();
    for (const item of categories) {
      if (!item.postable) continue;
      if (!map.has(item.group)) map.set(item.group, []);
      map.get(item.group).push(item);
    }
    return [...map.entries()];
  }, [categories]);

  const acceptPhoto = (next) => {
    setPhoto(next);
    setPreview(URL.createObjectURL(next.blob));
    setStep("details");
  };

  const toggleLink = (id) => {
    const next = new Set(links);
    if (next.has(id)) {
      next.delete(id);
    } else if (next.size < MAX_LINKS) {
      next.add(id);
    }
    setLinks(next);
  };

  const fail = (error) => {
    setDuplicateId(null);
    setNeedLogin(false);
    if (error.status === 401) {
      setMessage("Please log in again to post.");
      setNeedLogin(true);
    } else if (error.status === 409) {
      setMessage("That photo has already been posted.");
      setDuplicateId(error.body?.detail?.existing_incident_id ?? null);
    } else if (error.status === 422) {
      setMessage(reasonFrom(error.body) ?? "Some details could not be accepted.");
    } else if (error.status === 429) {
      setMessage("Too many posts in the last hour. Try again later.");
    } else if (error.status === 413) {
      setMessage("That photo is too large.");
    } else {
      setMessage("Could not post. Check the connection and try again.");
    }
  };

  const submit = async () => {
    if (busy || !photo || !position || !ready || !category) return;
    setBusy(true);
    setMessage("");
    setDuplicateId(null);
    setNeedLogin(false);

    const form = new FormData();
    form.append("photo", photo.blob, "photo.jpg");
    form.append("category", category);
    form.append("lat", position.lat.toFixed(6));
    form.append("lng", position.lng.toFixed(6));
    form.append("accuracy_m", position.accuracy.toFixed(1));
    form.append("captured_at", photo.capturedAt.toISOString());
    if (description.trim()) form.append("description", description.trim());
    for (const id of links) form.append("link_to", String(id));

    try {
      const incident = await createIncident(form);
      onPosted(incident);
    } catch (error) {
      fail(error);
    } finally {
      setBusy(false);
    }
  };

  if (step === "camera") {
    return <CameraCapture onAccept={acceptPhoto} onClose={onClose} />;
  }

  let locationText = "Finding your location…";
  let locationClass = "camera-message";
  if (geoError) {
    locationText = geoError;
    locationClass = "camera-error";
  } else if (position) {
    const metres = Math.round(accuracy);
    if (accuracy <= GOOD_ACCURACY_M) {
      locationText = `Location good: about ${metres} m.`;
    } else if (!allowWeak) {
      locationText = `Waiting for a better signal: about ${metres} m (aim for ${GOOD_ACCURACY_M} m).`;
    } else if (accuracy <= MAX_ACCURACY_M) {
      locationText = `Using a rough location: about ${metres} m. Move somewhere open for a better one.`;
    } else {
      locationText = `Location is too rough: about ${metres} m. Move somewhere open and wait.`;
      locationClass = "camera-error";
    }
  }

  const categoryLabel =
    categories.find((item) => item.slug === category)?.label ?? "";

  return (
    <div className="camera-backdrop">
      <div className="report">
        <header className="camera-header">
          <span>Report a problem</span>
          <button
            type="button"
            className="panel-close"
            onClick={onClose}
            aria-label="Close"
          >
            ×
          </button>
        </header>

        {preview && (
          <img className="report-photo" src={preview} alt="Your photo" />
        )}

        <p className={locationClass}>{locationText}</p>

        <label className="report-field">
          <span>Category</span>
          <select
            value={category}
            disabled={busy}
            onChange={(event) => setCategory(event.target.value)}
          >
            <option value="">Choose a category</option>
            {grouped.map(([group, items]) => (
              <optgroup key={group} label={groupLabel(group)}>
                {items.map((item) => (
                  <option key={item.slug} value={item.slug}>
                    {item.label}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>

        <label className="report-field">
          <span>Description (optional)</span>
          <textarea
            rows={3}
            maxLength={MAX_DESCRIPTION}
            value={description}
            disabled={busy}
            onChange={(event) => setDescription(event.target.value)}
          />
          <span className="report-count">
            {description.length}/{MAX_DESCRIPTION}
          </span>
        </label>

        {category && ready && (
          <section className="report-candidates">
            <p className="report-candidates-title">Is this the same problem?</p>
            {candidateStatus === "loading" && (
              <p className="camera-message">Looking for nearby reports…</p>
            )}
            {candidateStatus === "error" && (
              <p className="camera-message">
                Could not load nearby reports. You can still post.
              </p>
            )}
            {candidateStatus === "empty" && (
              <p className="camera-message">
                No nearby reports of this category.
              </p>
            )}
            {candidates.map((candidate) => {
              const checked = links.has(candidate.id);
              return (
                <label
                  key={candidate.id}
                  className={`candidate ${checked ? "candidate-on" : ""}`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={busy || (!checked && links.size >= MAX_LINKS)}
                    onChange={() => toggleLink(candidate.id)}
                  />
                  {candidate.thumb_url && (
                    <img
                      className="candidate-thumb"
                      src={`/api${candidate.thumb_url}`}
                      alt=""
                    />
                  )}
                  <span className="candidate-text">
                    <strong>{categoryLabel || "Report"}</strong>
                    <span>
                      {distanceText(candidate.distance_m)} ·{" "}
                      {ageText(candidate.created_at)}
                    </span>
                  </span>
                </label>
              );
            })}
          </section>
        )}

        {message && (
          <div className="report-message">
            <p className="camera-error">{message}</p>
            <div className="report-message-actions">
              {needLogin && (
                <button type="button" className="auth-btn" onClick={onLogin}>
                  Log in
                </button>
              )}
              {duplicateId !== null && (
                <button
                  type="button"
                  className="auth-btn"
                  onClick={() => onOpenIncident(duplicateId)}
                >
                  Open that incident
                </button>
              )}
            </div>
          </div>
        )}

        <div className="camera-actions">
          <button
            type="button"
            className="auth-btn"
            onClick={onClose}
            disabled={busy}
          >
            Cancel
          </button>
          <button
            type="button"
            className="auth-btn"
            onClick={submit}
            disabled={busy || !ready || !category}
          >
            {busy ? "Posting…" : "Post report"}
          </button>
        </div>
      </div>
    </div>
  );
}
