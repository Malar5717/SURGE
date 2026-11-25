import { useEffect, useState } from "react";
import { fetchIncident } from "../api.js";
import { CATEGORY_BY_KEY } from "../categories.js";

export default function DetailPanel({
  incidentId,
  onClose,
  onSelectLinked,
  knownIncidents,
}) {
  const [incident, setIncident] = useState(null);
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    let active = true;
    setStatus("loading");
    setIncident(null);
    fetchIncident(incidentId)
      .then((data) => {
        if (!active) return;
        setIncident(data);
        setStatus("ready");
      })
      .catch(() => {
        if (active) setStatus("error");
      });
    return () => {
      active = false;
    };
  }, [incidentId]);

  const category = incident ? CATEGORY_BY_KEY[incident.category] : null;
  const others = incident ? incident.group_size - 1 : 0;

  return (
    <aside className="panel">
      <header className="panel-header">
        <span className="panel-category">
          {category && (
            <span className="panel-dot" style={{ background: category.color }} />
          )}
          {category ? category.label : "Incident"}
        </span>
        <button className="panel-close" onClick={onClose} aria-label="Close">
          ×
        </button>
      </header>

      {status === "loading" && <p className="panel-muted">Loading…</p>}
      {status === "error" && (
        <p className="panel-error">Could not load this incident.</p>
      )}

      {status === "ready" && incident && (
        <>
          {incident.description && (
            <p className="panel-description">{incident.description}</p>
          )}
          <p className="panel-muted">
            {incident.created_by_handle
              ? `Reported by @${incident.created_by_handle}`
              : "Reported"}{" "}
            {new Date(incident.created_at).toLocaleString()}
          </p>
          <ol className="timeline">
            {incident.events.map((event) => (
              <li key={event.id}>
                <span className="timeline-type">
                  {event.type === "note" ? "Note" : "Reported"}
                </span>
                {event.note && <span className="timeline-note"> — {event.note}</span>}
                <div className="timeline-time">
                  {new Date(event.created_at).toLocaleString()}
                  {event.created_by_handle && ` · by @${event.created_by_handle}`}
                </div>
              </li>
            ))}
          </ol>

          {others > 0 && (
            <section className="linked">
              <p className="linked-summary">
                Linked with {others} other {others === 1 ? "report" : "reports"}
              </p>
              <ul className="linked-list">
                {incident.linked_incident_ids.map((id) => {
                  const known = knownIncidents?.get(id);
                  const linkedCategory = known
                    ? CATEGORY_BY_KEY[known.category]
                    : null;
                  return (
                    <li key={id}>
                      <button
                        className="linked-item"
                        onClick={() => onSelectLinked(id)}
                      >
                        {linkedCategory && (
                          <span
                            className="panel-dot"
                            style={{ background: linkedCategory.color }}
                          />
                        )}
                        {linkedCategory ? linkedCategory.label : "Report"} #{id}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
          )}
        </>
      )}
    </aside>
  );
}
