import { useState } from "react";
import { Link } from "react-router-dom";
import { getPostIncident, setTaskStatus } from "../lib/data";
import { useAsync } from "../lib/useAsync";
import { useLiveTables } from "../lib/useLive";
import { SeverityBadge } from "../components/SeverityBadge";
import { StatusPill } from "../components/StatusPill";
import {
  Card,
  CheckLine,
  Empty,
  ErrorNote,
  Metric,
  PageHeader,
  Person,
  Pill,
  Progress
} from "../components/ui";

const TABS = ["Post-incident flow", "Follow-ups"] as const;

export function PostIncident() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Post-incident flow");
  const [openOnly, setOpenOnly] = useState(true);
  const [busy, setBusy] = useState("");
  const tick = useLiveTables(["post_incident_tasks", "follow_ups"]);
  const { data, loading, error } = useAsync(getPostIncident, [tick]);

  async function toggle(
    table: "follow_ups" | "post_incident_tasks",
    id: string,
    status: "Open" | "Done"
  ) {
    setBusy(id);
    try {
      await setTaskStatus(table, id, status === "Done" ? "Open" : "Done");
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "Could not update the task");
    } finally {
      setBusy("");
    }
  }

  const followUps = (data?.follow_ups ?? []).filter(f => !openOnly || f.status === "Open");

  return (
    <>
      <PageHeader icon="✓" title="Post-incident" />
      <div className="pageBody">
        {error && <ErrorNote message={error} />}
        {loading && !data && <Empty>Loading…</Empty>}

        {data && (
          <>
            <div className="grid cols3">
              <Metric
                label="Incidents in the flow"
                value={data.incidents.length}
                foot="With a post-incident checklist"
              />
              <Metric
                label="Outstanding tasks"
                value={data.outstanding_tasks}
                foot="Across all incidents"
              />
              <Metric
                label="Open follow-ups"
                value={data.follow_ups.filter(f => f.status === "Open").length}
                foot={`${data.follow_ups.length} total`}
              />
            </div>

            <Card tight>
              <div className="tabs">
                {TABS.map(t => (
                  <button
                    key={t}
                    className={tab === t ? "active" : undefined}
                    onClick={() => setTab(t)}
                  >
                    {t}
                  </button>
                ))}
              </div>

              <div style={{ padding: 18 }}>
                {tab === "Post-incident flow" && (
                  <>
                    <p className="cardNote" style={{ marginBottom: 14 }}>
                      Incidents that still have tasks to complete before they can be closed.
                      Tick one and it saves immediately.
                    </p>
                    {!data.incidents.length && <Empty>Nothing in the flow.</Empty>}
                    {data.incidents.map(item => {
                      const done = item.tasks.filter(t => t.status === "Done").length;
                      return (
                        <section className="flowCard" key={item.incident.id}>
                          <div className="row wrap" style={{ marginBottom: 10 }}>
                            <Link className="mono" to={`/incidents/${item.incident.reference}`}>
                              {item.incident.reference}
                            </Link>
                            <span className="title">{item.incident.title}</span>
                            <span className="spacer" style={{ marginLeft: "auto" }} />
                            <SeverityBadge severity={item.incident.severity} />
                            <StatusPill status={item.incident.status} />
                            {item.incident.lead && <Person name={item.incident.lead.full_name} />}
                          </div>
                          <Progress done={done} total={item.tasks.length} />
                          <div style={{ marginTop: 8 }}>
                            {item.tasks.map(t => (
                              <CheckLine
                                key={t.id}
                                done={t.status === "Done"}
                                onToggle={() =>
                                  busy || toggle("post_incident_tasks", t.id, t.status)
                                }
                                right={
                                  <span className="cardNote">
                                    {t.due_on ? `due ${t.due_on} · ` : ""}
                                    {t.owner?.full_name ?? "Unassigned"}
                                  </span>
                                }
                              >
                                {t.title}
                              </CheckLine>
                            ))}
                          </div>
                        </section>
                      );
                    })}
                  </>
                )}

                {tab === "Follow-ups" && (
                  <>
                    <div className="row" style={{ marginBottom: 12 }}>
                      <button
                        className={openOnly ? "filter active" : "filter"}
                        onClick={() => setOpenOnly(true)}
                      >
                        Open
                      </button>
                      <button
                        className={!openOnly ? "filter active" : "filter"}
                        onClick={() => setOpenOnly(false)}
                      >
                        All
                      </button>
                      <span className="spacer cardNote" style={{ marginLeft: "auto" }}>
                        Found {followUps.length}
                      </span>
                    </div>

                    {!followUps.length && <Empty>No follow-ups here.</Empty>}
                    {followUps.map(f => (
                      <CheckLine
                        key={f.id}
                        done={f.status === "Done"}
                        onToggle={() => busy || toggle("follow_ups", f.id, f.status)}
                        right={
                          <span className="row">
                            <Pill>{f.priority}</Pill>
                            {f.due_on && <span className="cardNote">due {f.due_on}</span>}
                            <span className="cardNote">{f.owner?.full_name ?? "Unassigned"}</span>
                          </span>
                        }
                      >
                        <span>
                          {f.title}
                          <span className="cardNote">
                            {" "}
                            ·{" "}
                            <Link className="mono" to={`/incidents/${f.incident.reference}`}>
                              {f.incident.reference}
                            </Link>
                          </span>
                        </span>
                      </CheckLine>
                    ))}
                  </>
                )}
              </div>
            </Card>
          </>
        )}
      </div>
    </>
  );
}
