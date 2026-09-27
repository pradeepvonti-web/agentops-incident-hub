import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  getStatusPage,
  listIncidents,
  publishStatusUpdate,
  setComponentStatus,
  setOverallStatus
} from "../lib/data";
import { useAsync } from "../lib/useAsync";
import { useLiveTables } from "../lib/useLive";
import { dateTime } from "../lib/format";
import { useAuth } from "../app/AuthProvider";
import { Field, FormError, Modal, useSubmit } from "../components/forms";
import { StatusPill } from "../components/StatusPill";
import { Card, Empty, ErrorNote, PageHeader, Pill } from "../components/ui";
import { LIFECYCLE, type ComponentStatus, type IncidentRow, type Status } from "../types";

const COMPONENT_STATUSES: ComponentStatus[] = [
  "Operational",
  "Degraded performance",
  "Partial outage",
  "Major outage"
];

const OVERALL = [
  "All systems operational",
  "Degraded performance",
  "Partial outage",
  "Major outage"
];

export function uptimeCells(uptime: number) {
  const bad = Math.round((100 - uptime) * 6);
  return Array.from({ length: 45 }, (_, i) => {
    if (i >= 45 - bad) return i >= 44 ? "bad" : "warn";
    return "";
  });
}

export function StatusPageView() {
  const tick = useLiveTables(["status_updates", "status_components"]);
  const { data, loading, error } = useAsync(getStatusPage, [tick]);
  const [publishing, setPublishing] = useState(false);
  const [busy, setBusy] = useState("");

  async function run(id: string, fn: () => Promise<unknown>) {
    setBusy(id);
    try {
      await fn();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusy("");
    }
  }

  const degraded = data && data.overall !== "All systems operational";

  return (
    <>
      <PageHeader
        icon="▮"
        eyebrow={data?.url}
        title={data?.name ?? "Status page"}
        actions={
          <>
            <Link className="btn" to="/status" target="_blank">
              View public page
            </Link>
            <button className="btn primary" onClick={() => setPublishing(true)}>
              Publish update
            </button>
          </>
        }
      />
      <div className="pageBody">
        {error && <ErrorNote message={error} />}
        {loading && !data && <Empty>Loading…</Empty>}

        {data && (
          <>
            <div className={`statusHero ${degraded ? "degraded" : "ok"}`}>
              <div className="row wrap">
                <div>
                  <h2>{data.overall}</h2>
                  <p className="cardNote">
                    This is what customers see at {data.url}.
                  </p>
                </div>
                <select
                  className="select spacer"
                  style={{ marginLeft: "auto" }}
                  value={data.overall}
                  disabled={busy === "overall"}
                  onChange={e => run("overall", () => setOverallStatus(e.target.value))}
                >
                  {OVERALL.map(o => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <Card title="Components" note="Uptime over the last 45 days">
              {data.components.map(c => (
                <div key={c.id} style={{ marginBottom: 14 }}>
                  <div className="railRow">
                    <span className="title">{c.name}</span>
                    <span className="row">
                      <span className="cardNote">{Number(c.uptime_90d).toFixed(2)}%</span>
                      <select
                        className="select"
                        value={c.status}
                        disabled={busy === c.id}
                        onChange={e =>
                          run(c.id, () =>
                            setComponentStatus(c.id, e.target.value as ComponentStatus)
                          )
                        }
                      >
                        {COMPONENT_STATUSES.map(s => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ))}
                      </select>
                    </span>
                  </div>
                  <div className="uptimeBar">
                    {uptimeCells(Number(c.uptime_90d)).map((cls, i) => (
                      <i key={i} className={cls} />
                    ))}
                  </div>
                </div>
              ))}
            </Card>

            <Card title="Customer updates" note="Everything published to the status page">
              {!data.updates.length && <Empty>Nothing published yet.</Empty>}
              {data.updates.map(u => (
                <article className="update" key={u.id}>
                  <div className="meta">
                    <StatusPill status={u.status} />
                    <span className="cardNote">{dateTime(u.published_at)}</span>
                    <span className="spacer" style={{ marginLeft: "auto" }} />
                    {u.author_name && <Pill>{u.author_name}</Pill>}
                    {u.incident_reference && (
                      <Link className="mono" to={`/incidents/${u.incident_reference}`}>
                        {u.incident_reference}
                      </Link>
                    )}
                  </div>
                  <p>{u.message}</p>
                </article>
              ))}
            </Card>
          </>
        )}
      </div>

      {publishing && <PublishDialog onClose={() => setPublishing(false)} />}
    </>
  );
}

function PublishDialog({ onClose }: { onClose: () => void }) {
  const { profile } = useAuth();
  const [incidents, setIncidents] = useState<IncidentRow[]>([]);
  const [incidentId, setIncidentId] = useState("");
  const [status, setStatus] = useState<Status>("Investigating");
  const [message, setMessage] = useState("");

  useEffect(() => {
    listIncidents({ status: "active" })
      .then(rows => {
        setIncidents(rows);
        if (rows[0]) {
          setIncidentId(rows[0].id);
          setStatus(rows[0].status);
        }
      })
      .catch(() => setIncidents([]));
  }, []);

  const { onSubmit, pending, error } = useSubmit(
    () =>
      publishStatusUpdate({
        incidentId: incidentId || null,
        status,
        message,
        authorId: profile?.id ?? null
      }),
    onClose
  );

  return (
    <Modal title="Publish a status page update" onClose={onClose} wide>
      <form onSubmit={onSubmit}>
        <FormError message={error} />
        <p className="cardNote" style={{ marginBottom: 12 }}>
          Customers read this. Say what is affected and what you are doing about it.
        </p>
        <div className="grid cols2">
          <Field label="Incident">
            <select
              className="select"
              value={incidentId}
              onChange={e => {
                setIncidentId(e.target.value);
                const found = incidents.find(i => i.id === e.target.value);
                if (found) setStatus(found.status);
              }}
            >
              <option value="">Not tied to an incident</option>
              {incidents.map(i => (
                <option key={i.id} value={i.id}>
                  {i.reference} · {i.title}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Status shown">
            <select
              className="select"
              value={status}
              onChange={e => setStatus(e.target.value as Status)}
            >
              {LIFECYCLE.map(s => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <Field label="Message">
          <textarea
            className="input"
            rows={4}
            value={message}
            onChange={e => setMessage(e.target.value)}
            placeholder="We are investigating reports of failed checkouts and will update within 30 minutes."
            required
          />
        </Field>
        <button className="btn primary" disabled={pending || !message.trim()}>
          {pending ? "Publishing…" : "Publish to status page"}
        </button>
      </form>
    </Modal>
  );
}
