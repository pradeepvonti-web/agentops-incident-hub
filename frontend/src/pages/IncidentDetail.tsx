import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  addAction,
  addFollowUp,
  addParticipant,
  deleteRow,
  getIncident,
  getReport,
  listPeople,
  listServiceOptions,
  postUpdate,
  setTaskStatus,
  startPostIncidentFlow,
  updateIncident
} from "../lib/data";
import { useAsync } from "../lib/useAsync";
import { useLiveTables } from "../lib/useLive";
import { dateTime, day, duration, time } from "../lib/format";
import { useAuth } from "../app/AuthProvider";
import { SeverityBadge } from "../components/SeverityBadge";
import { LifecycleBar, StatusPill } from "../components/StatusPill";
import { Field, FormError, Modal, PersonSelect, useSubmit } from "../components/forms";
import {
  AvatarGroup,
  Card,
  CheckLine,
  Empty,
  ErrorNote,
  PageHeader,
  Person as PersonChip,
  Pill
} from "../components/ui";
import {
  LIFECYCLE,
  SEVERITIES,
  type IncidentDetail as Incident,
  type Person,
  type Priority,
  type Severity,
  type Status,
  type TimelineEntry
} from "../types";

const TABS = ["Updates", "Timeline", "Actions", "Follow-ups", "Evidence"] as const;
type Tab = (typeof TABS)[number];

const MARKER: Record<TimelineEntry["kind"], string> = {
  alert: "▲",
  declared: "◆",
  update: "✎",
  status: "⇉",
  severity: "↕",
  action: "✓",
  note: "·",
  closed: "■"
};

export function IncidentDetail() {
  const { reference = "" } = useParams();
  const { profile } = useAuth();
  const [tab, setTab] = useState<Tab>("Updates");
  const [people, setPeople] = useState<Person[]>([]);
  const [busy, setBusy] = useState("");

  const tick = useLiveTables([
    "incidents",
    "incident_updates",
    "incident_timeline",
    "actions",
    "follow_ups",
    "post_incident_tasks"
  ]);

  const incident = useAsync(() => getIncident(reference), [reference, tick]);
  const x = incident.data;
  const report = useAsync(
    async () => (x ? getReport(x.id) : null),
    [x?.id, x?.logs.length, tick]
  );

  useEffect(() => {
    listPeople().then(setPeople).catch(() => setPeople([]));
  }, []);

  async function run(label: string, fn: () => Promise<unknown>) {
    setBusy(label);
    try {
      await fn();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusy("");
    }
  }

  if (incident.error) return <div className="pageBody"><ErrorNote message={incident.error} /></div>;
  if (!x) return <div className="pageBody">Loading…</div>;

  const r = report.data;
  const openTasks = x.post_incident_tasks.filter(t => t.status === "Open").length;

  return (
    <>
      <PageHeader
        icon="◆"
        eyebrow={`Incidents · ${x.reference}`}
        title={x.title}
        actions={
          <>
            <Link className="btn" to="/incidents">
              Back to incidents
            </Link>
            {profile && !x.participants.some(p => p.id === profile.id) && (
              <button
                className="btn"
                disabled={!!busy}
                onClick={() => run("join", () => addParticipant(x.id, profile.id))}
              >
                Join incident
              </button>
            )}
          </>
        }
      />

      <div className="incidentBar">
        <div className="row wrap">
          <LifecycleBar status={x.status} />
          <span className="spacer" style={{ marginLeft: "auto" }} />
          <select
            className="select"
            value={x.severity}
            disabled={!!busy}
            onChange={e =>
              run("severity", () => updateIncident(x.id, { severity: e.target.value as Severity }))
            }
          >
            {SEVERITIES.map(s => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <select
            className="select"
            value={x.status}
            disabled={!!busy}
            onChange={e =>
              run("status", () => updateIncident(x.id, { status: e.target.value as Status }))
            }
          >
            {LIFECYCLE.map(s => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <Pill>
            {x.fixed_at
              ? `Resolved in ${duration(x.impact_started_at, x.fixed_at)}`
              : `Ongoing for ${duration(x.impact_started_at, null)}`}
          </Pill>
        </div>
      </div>

      <div className="pageBody">
        <div className="split">
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
            <Card>
              <p>{x.summary || "No summary yet."}</p>
            </Card>

            <UpdateComposer incident={x} />

            <Card tight>
              <div className="tabs">
                {TABS.map(t => (
                  <button
                    key={t}
                    className={tab === t ? "active" : undefined}
                    onClick={() => setTab(t)}
                  >
                    {t}
                    {t === "Actions" && x.actions.filter(a => a.status === "Open").length > 0 && (
                      <span className="tabCount">
                        {x.actions.filter(a => a.status === "Open").length}
                      </span>
                    )}
                  </button>
                ))}
              </div>

              <div style={{ padding: 18 }}>
                {tab === "Updates" && (
                  <>
                    {!x.updates.length && <Empty>No updates shared yet.</Empty>}
                    {x.updates.map(u => (
                      <article className="update" key={u.id}>
                        <div className="meta">
                          <PersonChip name={u.author?.full_name ?? "AgentOps"} />
                          <span className="cardNote">{dateTime(u.created_at)}</span>
                          <span className="spacer" style={{ marginLeft: "auto" }} />
                          <SeverityBadge severity={u.severity} />
                          <StatusPill status={u.status} />
                        </div>
                        <p>{u.message}</p>
                        {u.next_update_in_minutes && (
                          <p className="cardNote" style={{ marginTop: 8 }}>
                            Next update in {u.next_update_in_minutes} minutes
                          </p>
                        )}
                      </article>
                    ))}
                  </>
                )}

                {tab === "Timeline" && (
                  <>
                    <p className="cardNote" style={{ marginBottom: 12 }}>
                      {day(x.timeline[0]?.occurred_at)} · times shown in your local zone
                    </p>
                    <div className="timeline">
                      {x.timeline.map(entry => (
                        <div className="tlItem" key={entry.id}>
                          <div className="when">{time(entry.occurred_at)}</div>
                          <div className="rail">
                            <span className="marker">{MARKER[entry.kind]}</span>
                            <span className="line" />
                          </div>
                          <div className="body">
                            <div className="head">{entry.title}</div>
                            {(entry.detail || entry.author) && (
                              <div className="detail">
                                {entry.detail}
                                {entry.author && (
                                  <div className="cardNote" style={{ marginTop: 6 }}>
                                    {entry.author.full_name}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                )}

                {tab === "Actions" && (
                  <>
                    <AddAction incidentId={x.id} people={people} />
                    {!x.actions.length && <Empty>No actions assigned.</Empty>}
                    {x.actions.map(a => (
                      <CheckLine
                        key={a.id}
                        done={a.status === "Done"}
                        onToggle={() =>
                          run("action", () =>
                            setTaskStatus("actions", a.id, a.status === "Done" ? "Open" : "Done")
                          )
                        }
                        right={
                          <span className="row">
                            <span className="cardNote">{a.owner?.full_name ?? "Unassigned"}</span>
                            <button
                              className="linkButton"
                              onClick={() => run("delete", () => deleteRow("actions", a.id))}
                            >
                              Remove
                            </button>
                          </span>
                        }
                      >
                        {a.description}
                      </CheckLine>
                    ))}
                  </>
                )}

                {tab === "Follow-ups" && (
                  <>
                    <AddFollowUp incidentId={x.id} people={people} />
                    {!x.follow_ups.length && <Empty>No follow-ups yet.</Empty>}
                    {x.follow_ups.map(f => (
                      <CheckLine
                        key={f.id}
                        done={f.status === "Done"}
                        onToggle={() =>
                          run("follow-up", () =>
                            setTaskStatus("follow_ups", f.id, f.status === "Done" ? "Open" : "Done")
                          )
                        }
                        right={
                          <span className="row">
                            <Pill>{f.priority}</Pill>
                            {f.due_on && <span className="cardNote">due {f.due_on}</span>}
                            <span className="cardNote">{f.owner?.full_name ?? "Unassigned"}</span>
                          </span>
                        }
                      >
                        {f.title}
                      </CheckLine>
                    ))}
                  </>
                )}

                {tab === "Evidence" && (
                  <>
                    <h3>Executive summary</h3>
                    <p className="cardNote" style={{ margin: "4px 0 10px" }}>
                      ERROR and CRITICAL events only. The filter runs in the database, in
                      <span className="mono"> agentops.incident_report()</span>.
                    </p>
                    {r?.evidence?.length ? (
                      <ul className="evidence">
                        {r.evidence.map((line, i) => (
                          <li className="mono" key={i}>
                            {line}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <Empty>No ERROR or CRITICAL evidence.</Empty>
                    )}

                    <h3 style={{ marginTop: 22 }}>Log timeline</h3>
                    <p className="cardNote" style={{ margin: "4px 0 6px" }}>
                      All events, including WARNING, for technical analysis.
                    </p>
                    {!x.logs.length && <Empty>No log events attached.</Empty>}
                    {x.logs.map(log => (
                      <div className="log" key={log.id}>
                        <span className="mono">{dateTime(log.occurred_at)}</span>
                        <SeverityBadge severity={log.level} />
                        <span>{log.message}</span>
                      </div>
                    ))}
                  </>
                )}
              </div>
            </Card>

            <EditableFindings incident={x} />
          </div>

          <aside className="card rail">
            <div className="railGroup">
              <div className="railRow">
                <span className="label">Incident lead</span>
                <PersonSelect
                  value={x.lead_id}
                  people={people}
                  onChange={id => run("lead", () => updateIncident(x.id, { lead_id: id }))}
                />
              </div>
              <div className="railRow">
                <span className="label">Reporter</span>
                <span>{x.reporter_name ?? "—"}</span>
              </div>
              <div className="railRow">
                <span className="label">Participants</span>
                <AvatarGroup names={x.participants.map(p => p.full_name)} />
              </div>
            </div>

            <div className="railGroup">
              <h3>Service</h3>
              <ServicePicker incident={x} onChange={id => updateIncident(x.id, { service_id: id })} />
              <div className="railRow">
                <span className="label">Team</span>
                <span>{x.team_name ?? "—"}</span>
              </div>
              <div className="railRow">
                <span className="label">Components</span>
                <span>{x.components.map(c => c.name).join(", ") || "—"}</span>
              </div>
            </div>

            <div className="railGroup">
              <h3>Timestamps</h3>
              {(
                [
                  ["Impact started", x.impact_started_at],
                  ["Declared", x.declared_at],
                  ["Identified", x.identified_at],
                  ["Fixed", x.fixed_at],
                  ["Closed", x.closed_at]
                ] as const
              ).map(([label, value]) => (
                <div className="railRow" key={label}>
                  <span className="label">{label}</span>
                  <span>{dateTime(value)}</span>
                </div>
              ))}
            </div>

            <div className="railGroup">
              <h3>Duration metrics</h3>
              <div className="railRow">
                <span className="label">Time to declare</span>
                <span>{duration(x.impact_started_at, x.declared_at)}</span>
              </div>
              <div className="railRow">
                <span className="label">Time to fix</span>
                <span>
                  {x.fixed_at ? duration(x.impact_started_at, x.fixed_at) : "Still open"}
                </span>
              </div>
            </div>

            <div className="railGroup">
              <h3>Post-incident</h3>
              {x.post_incident_tasks.length ? (
                <>
                  <p className="cardNote" style={{ marginBottom: 8 }}>
                    {openTasks} of {x.post_incident_tasks.length} tasks open
                  </p>
                  {x.post_incident_tasks.map(t => (
                    <CheckLine
                      key={t.id}
                      done={t.status === "Done"}
                      onToggle={() =>
                        run("task", () =>
                          setTaskStatus(
                            "post_incident_tasks",
                            t.id,
                            t.status === "Done" ? "Open" : "Done"
                          )
                        )
                      }
                    >
                      <span style={{ fontSize: 12.5 }}>{t.title}</span>
                    </CheckLine>
                  ))}
                </>
              ) : (
                <button
                  className="btn"
                  disabled={!!busy}
                  onClick={() => run("flow", () => startPostIncidentFlow(x.id, x.lead_id))}
                >
                  Start post-incident flow
                </button>
              )}
            </div>

            <div className="railGroup">
              <h3>Related incidents</h3>
              {x.related.length ? (
                x.related.map(rel => (
                  <div className="railRow" key={rel.id}>
                    <Link className="mono" to={`/incidents/${rel.reference}`}>
                      {rel.reference}
                    </Link>
                    <SeverityBadge severity={rel.severity} />
                  </div>
                ))
              ) : (
                <p className="cardNote">None linked.</p>
              )}
            </div>
          </aside>
        </div>
      </div>
    </>
  );
}

/* --------------------------------------------------------------- composer */

function UpdateComposer({ incident }: { incident: Incident }) {
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState<Status | "">("");
  const [nextUpdate, setNextUpdate] = useState("");

  const { onSubmit, pending, error } = useSubmit(
    async () => {
      await postUpdate({
        incidentId: incident.id,
        message,
        status: status || null,
        nextUpdateInMinutes: nextUpdate ? Number(nextUpdate) : null
      });
    },
    () => {
      setMessage("");
      setStatus("");
      setNextUpdate("");
    }
  );

  return (
    <Card title="Share an update" note="Posting an update can also move the incident forward.">
      <form onSubmit={onSubmit}>
        <FormError message={error} />
        <textarea
          className="input"
          style={{ width: "100%" }}
          rows={3}
          placeholder="What has changed since the last update?"
          value={message}
          onChange={e => setMessage(e.target.value)}
        />
        <div className="row wrap" style={{ marginTop: 10 }}>
          <select
            className="select"
            value={status}
            onChange={e => setStatus(e.target.value as Status | "")}
          >
            <option value="">Keep status at {incident.status}</option>
            {LIFECYCLE.filter(s => s !== incident.status).map(s => (
              <option key={s} value={s}>
                Move to {s}
              </option>
            ))}
          </select>
          <select
            className="select"
            value={nextUpdate}
            onChange={e => setNextUpdate(e.target.value)}
          >
            <option value="">No next update promised</option>
            {[15, 30, 60].map(m => (
              <option key={m} value={m}>
                Next update in {m} minutes
              </option>
            ))}
          </select>
          <button className="btn primary spacer" style={{ marginLeft: "auto" }} disabled={pending || !message.trim()}>
            {pending ? "Posting…" : "Post update"}
          </button>
        </div>
      </form>
    </Card>
  );
}

/* ------------------------------------------------------------ small forms */

function AddAction({ incidentId, people }: { incidentId: string; people: Person[] }) {
  const [description, setDescription] = useState("");
  const [ownerId, setOwnerId] = useState<string | null>(null);

  const { onSubmit, pending, error } = useSubmit(
    () => addAction(incidentId, description, ownerId),
    () => setDescription("")
  );

  return (
    <form onSubmit={onSubmit} className="inlineForm">
      <FormError message={error} />
      <div className="row wrap">
        <input
          className="input"
          style={{ flex: 1, minWidth: 200 }}
          placeholder="Add an action for this incident…"
          value={description}
          onChange={e => setDescription(e.target.value)}
        />
        <PersonSelect value={ownerId} onChange={setOwnerId} people={people} />
        <button className="btn" disabled={pending || !description.trim()}>
          Add
        </button>
      </div>
    </form>
  );
}

function AddFollowUp({ incidentId, people }: { incidentId: string; people: Person[] }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [ownerId, setOwnerId] = useState<string | null>(null);
  const [priority, setPriority] = useState<Priority>("Medium");
  const [dueOn, setDueOn] = useState("");

  const { onSubmit, pending, error } = useSubmit(
    () => addFollowUp({ incidentId, title, ownerId, priority, dueOn: dueOn || null }),
    () => {
      setOpen(false);
      setTitle("");
    }
  );

  return (
    <>
      <button className="btn" style={{ marginBottom: 12 }} onClick={() => setOpen(true)}>
        Add follow-up
      </button>
      {open && (
        <Modal title="Add a follow-up" onClose={() => setOpen(false)}>
          <form onSubmit={onSubmit}>
            <FormError message={error} />
            <Field label="What needs doing?">
              <input
                className="input"
                value={title}
                onChange={e => setTitle(e.target.value)}
                autoFocus
                required
              />
            </Field>
            <Field label="Owner">
              <PersonSelect value={ownerId} onChange={setOwnerId} people={people} />
            </Field>
            <div className="grid cols2">
              <Field label="Priority">
                <select
                  className="select"
                  value={priority}
                  onChange={e => setPriority(e.target.value as Priority)}
                >
                  {(["Low", "Medium", "High"] as Priority[]).map(p => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Due">
                <input
                  className="input"
                  type="date"
                  value={dueOn}
                  onChange={e => setDueOn(e.target.value)}
                />
              </Field>
            </div>
            <button className="btn primary" style={{ marginTop: 12 }} disabled={pending || !title.trim()}>
              {pending ? "Saving…" : "Add follow-up"}
            </button>
          </form>
        </Modal>
      )}
    </>
  );
}

function ServicePicker({
  incident,
  onChange
}: {
  incident: Incident;
  onChange: (id: string | null) => Promise<void>;
}) {
  const [services, setServices] = useState<{ id: string; slug: string; name: string }[]>([]);

  useEffect(() => {
    listServiceOptions().then(setServices).catch(() => setServices([]));
  }, []);

  const current = services.find(s => s.slug === incident.service_slug);

  return (
    <div className="railRow">
      <span className="label">Affected service</span>
      <select
        className="select"
        value={current?.id ?? ""}
        onChange={e => void onChange(e.target.value || null)}
      >
        <option value="">Unassigned</option>
        {services.map(s => (
          <option key={s.id} value={s.id}>
            {s.name}
          </option>
        ))}
      </select>
    </div>
  );
}

function EditableFindings({ incident }: { incident: Incident }) {
  const [cause, setCause] = useState(incident.probable_cause);
  const [action, setAction] = useState(incident.suggested_next_action);

  useEffect(() => {
    setCause(incident.probable_cause);
    setAction(incident.suggested_next_action);
  }, [incident.id, incident.probable_cause, incident.suggested_next_action]);

  const dirty =
    cause !== incident.probable_cause || action !== incident.suggested_next_action;

  const { onSubmit, pending, error } = useSubmit(() =>
    updateIncident(incident.id, { probable_cause: cause, suggested_next_action: action })
  );

  return (
    <Card title="Probable cause and next action" note="These two fields drive the executive summary.">
      <form onSubmit={onSubmit}>
        <FormError message={error} />
        <Field label="Probable cause">
          <textarea
            className="input"
            rows={2}
            value={cause}
            onChange={e => setCause(e.target.value)}
          />
        </Field>
        <Field label="Suggested next action">
          <textarea
            className="input"
            rows={2}
            value={action}
            onChange={e => setAction(e.target.value)}
          />
        </Field>
        <button className="btn" disabled={pending || !dirty}>
          {pending ? "Saving…" : dirty ? "Save findings" : "Saved"}
        </button>
      </form>
    </Card>
  );
}
