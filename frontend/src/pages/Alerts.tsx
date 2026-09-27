import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  acknowledgeAlert,
  createAlert,
  escalateAlert,
  getAlerts,
  resolveAlert,
  setRouteActive
} from "../lib/data";
import { useAsync } from "../lib/useAsync";
import { useLiveTable } from "../lib/useLive";
import { dateTime } from "../lib/format";
import { useAuth } from "../app/AuthProvider";
import { Field, FormError, Modal, useSubmit } from "../components/forms";
import { Card, Empty, ErrorNote, Metric, PageHeader, Pill } from "../components/ui";
import { CATEGORIES, SEVERITIES, type AlertPriority, type Category, type Severity } from "../types";

const PRIORITIES: AlertPriority[] = ["Low", "Medium", "High", "Urgent"];

export function Alerts() {
  const navigate = useNavigate();
  const { profile } = useAuth();
  const tick = useLiveTable("alerts");
  const { data, loading, error } = useAsync(getAlerts, [tick]);
  const [simulating, setSimulating] = useState(false);
  const [escalating, setEscalating] = useState<{ id: string; title: string } | null>(null);
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

  return (
    <>
      <PageHeader
        icon="▲"
        title="Alerts"
        actions={
          <button className="btn" onClick={() => setSimulating(true)}>
            Simulate inbound alert
          </button>
        }
      />
      <div className="pageBody">
        {error && <ErrorNote message={error} />}
        {loading && !data && <Empty>Loading…</Empty>}

        {data && (
          <>
            <div className="grid cols4">
              <Metric
                label="Open alerts"
                value={data.recent.filter(a => a.status === "Open").length}
                foot="Not yet escalated or resolved"
              />
              <Metric
                label="Sources connected"
                value={data.sources.filter(s => s.connected).length}
                foot={`${data.sources.length} configured`}
              />
              <Metric
                label="Alerts in 24h"
                value={data.sources.reduce((n, s) => n + s.alerts_24h, 0)}
                foot="Across all sources"
              />
              <Metric
                label="Active routes"
                value={data.routes.filter(r => r.active).length}
                foot={`${data.routes.length} total`}
              />
            </div>

            <div className="grid cols2">
              <Card title="Sources" note="Where alerts arrive from">
                {data.sources.map(s => (
                  <div className="railRow" key={s.id}>
                    <span>
                      <span className="title">{s.name}</span>
                      <div className="cardNote">{s.description}</div>
                    </span>
                    <span className="row">
                      <span className="cardNote">{s.alerts_24h}/24h</span>
                      <Pill tone={s.connected ? "done" : "neutral"}>
                        {s.connected ? "Connected" : "Not connected"}
                      </Pill>
                    </span>
                  </div>
                ))}
              </Card>

              <Card title="Routes" note="How alerts reach an escalation path">
                {data.routes.map(r => (
                  <div className="railRow" key={r.id}>
                    <span>
                      <span className="title">{r.name}</span>
                      <div className="cardNote mono">{r.condition}</div>
                      <div className="cardNote">
                        → {r.escalation_path?.name ?? "no escalation path"}
                      </div>
                    </span>
                    <span className="row">
                      <Pill>{r.priority}</Pill>
                      <button
                        className={r.active ? "filter active" : "filter"}
                        disabled={busy === r.id}
                        onClick={() => run(r.id, () => setRouteActive(r.id, !r.active))}
                      >
                        {r.active ? "Active" : "Inactive"}
                      </button>
                    </span>
                  </div>
                ))}
              </Card>
            </div>

            <Card title="Recent alerts" note="Newest first, updating live" tight>
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Alert</th>
                      <th>Source</th>
                      <th>Priority</th>
                      <th>Received</th>
                      <th>Status</th>
                      <th>Incident</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {data.recent.map(a => (
                      <tr key={a.id}>
                        <td className="incidentCell">
                          <div className="title">{a.title}</div>
                          <div className="sub mono">{a.reference}</div>
                        </td>
                        <td>{a.source?.name ?? "—"}</td>
                        <td>
                          <Pill>{a.priority}</Pill>
                        </td>
                        <td className="sub">{dateTime(a.received_at)}</td>
                        <td>
                          <Pill
                            tone={
                              a.status === "Resolved"
                                ? "done"
                                : a.status === "Escalated"
                                  ? "open"
                                  : "neutral"
                            }
                          >
                            {a.status}
                          </Pill>
                          {a.acknowledged_by && (
                            <div className="sub">ack {a.acknowledged_by.full_name}</div>
                          )}
                        </td>
                        <td>
                          {a.incident ? (
                            <Link className="mono" to={`/incidents/${a.incident.reference}`}>
                              {a.incident.reference}
                            </Link>
                          ) : (
                            <span className="sub">—</span>
                          )}
                        </td>
                        <td>
                          <span className="row">
                            {!a.acknowledged_at && profile && (
                              <button
                                className="btn ghost"
                                disabled={busy === a.id}
                                onClick={() => run(a.id, () => acknowledgeAlert(a.id, profile.id))}
                              >
                                Ack
                              </button>
                            )}
                            {!a.incident && a.status !== "Resolved" && (
                              <button
                                className="btn"
                                onClick={() => setEscalating({ id: a.id, title: a.title })}
                              >
                                Declare
                              </button>
                            )}
                            {a.status !== "Resolved" && (
                              <button
                                className="btn ghost"
                                disabled={busy === a.id}
                                onClick={() => run(a.id, () => resolveAlert(a.id))}
                              >
                                Resolve
                              </button>
                            )}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </>
        )}
      </div>

      {simulating && (
        <SimulateAlert
          sources={data?.sources ?? []}
          onClose={() => setSimulating(false)}
        />
      )}

      {escalating && (
        <EscalateAlert
          alert={escalating}
          onClose={() => setEscalating(null)}
          onDone={reference => {
            setEscalating(null);
            navigate(`/incidents/${reference}`);
          }}
        />
      )}
    </>
  );
}

function SimulateAlert({
  sources,
  onClose
}: {
  sources: { id: string; name: string }[];
  onClose: () => void;
}) {
  const [title, setTitle] = useState("");
  const [sourceId, setSourceId] = useState(sources[0]?.id ?? "");
  const [priority, setPriority] = useState<AlertPriority>("High");

  const { onSubmit, pending, error } = useSubmit(
    () => createAlert({ title, sourceId, priority }),
    onClose
  );

  return (
    <Modal title="Simulate an inbound alert" onClose={onClose}>
      <form onSubmit={onSubmit}>
        <FormError message={error} />
        <p className="cardNote" style={{ marginBottom: 12 }}>
          This writes the same row a monitoring webhook would create.
        </p>
        <Field label="Alert title">
          <input
            className="input"
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="checkout error rate above 5%"
            autoFocus
            required
          />
        </Field>
        <div className="grid cols2">
          <Field label="Source">
            <select className="select" value={sourceId} onChange={e => setSourceId(e.target.value)}>
              {sources.map(s => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Priority">
            <select
              className="select"
              value={priority}
              onChange={e => setPriority(e.target.value as AlertPriority)}
            >
              {PRIORITIES.map(p => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <button className="btn primary" style={{ marginTop: 12 }} disabled={pending || !title.trim()}>
          {pending ? "Sending…" : "Send alert"}
        </button>
      </form>
    </Modal>
  );
}

function EscalateAlert({
  alert,
  onClose,
  onDone
}: {
  alert: { id: string; title: string };
  onClose: () => void;
  onDone: (reference: string) => void;
}) {
  const [severity, setSeverity] = useState<Severity>("ERROR");
  const [category, setCategory] = useState<Category>("Availability");

  const { onSubmit, pending, error } = useSubmit(async () => {
    const incident = await escalateAlert(alert.id, severity, category);
    onDone(incident.reference);
  });

  return (
    <Modal title="Declare an incident from this alert" onClose={onClose}>
      <form onSubmit={onSubmit}>
        <FormError message={error} />
        <p style={{ marginBottom: 12 }}>{alert.title}</p>
        <div className="grid cols2">
          <Field label="Severity">
            <select
              className="select"
              value={severity}
              onChange={e => setSeverity(e.target.value as Severity)}
            >
              {SEVERITIES.map(s => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Category">
            <select
              className="select"
              value={category}
              onChange={e => setCategory(e.target.value as Category)}
            >
              {CATEGORIES.map(c => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <button className="btn primary" style={{ marginTop: 12 }} disabled={pending}>
          {pending ? "Declaring…" : "Declare incident"}
        </button>
      </form>
    </Modal>
  );
}
