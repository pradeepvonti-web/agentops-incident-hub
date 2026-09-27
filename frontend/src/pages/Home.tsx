import { Link, useNavigate } from "react-router-dom";
import { getBoard, getInsights, getPostIncident } from "../lib/data";
import { useAsync } from "../lib/useAsync";
import { useLiveTables } from "../lib/useLive";
import { duration, minutes } from "../lib/format";
import { SeverityBadge } from "../components/SeverityBadge";
import { Avatar, Card, Empty, ErrorNote, Metric, PageHeader } from "../components/ui";

export function Home() {
  const navigate = useNavigate();
  const tick = useLiveTables(["incidents", "follow_ups", "post_incident_tasks"]);

  const board = useAsync(getBoard, [tick]);
  const insights = useAsync(getInsights, [tick]);
  const post = useAsync(getPostIncident, [tick]);

  return (
    <>
      <PageHeader
        icon="◧"
        title="Home"
        actions={
          <>
            <Link className="btn" to="/insights">
              View insights
            </Link>
            <Link className="btn" to="/incidents">
              All incidents
            </Link>
          </>
        }
      />

      <div className="pageBody">
        {board.error && <ErrorNote message={board.error} />}

        <div className="grid cols4">
          <Metric
            label="Active incidents"
            value={board.data?.active_count ?? "—"}
            foot="Triage through Monitoring"
          />
          <Metric
            label="Critical and active"
            value={board.data?.critical_count ?? "—"}
            foot="Needs a lead right now"
          />
          <Metric
            label="Mean time to resolve"
            value={minutes(insights.data?.mean_minutes_to_fix ?? null)}
            foot="Impact started to fixed"
          />
          <Metric
            label="Open follow-ups"
            value={insights.data?.open_follow_ups ?? "—"}
            foot="Work created by incidents"
          />
        </div>

        <section>
          <div className="row" style={{ marginBottom: 12 }}>
            <h2>Active incidents</h2>
            <span className="cardNote">Grouped by lifecycle status, updating live</span>
          </div>

          {board.loading && !board.data && <Empty>Loading…</Empty>}

          {board.data && (
            <div className="board">
              {board.data.columns.map(column => (
                <div className="boardCol" key={column.status}>
                  <header>
                    <h3>{column.status}</h3>
                    <span className="count">{column.incidents.length}</span>
                  </header>
                  {!column.incidents.length && (
                    <p className="cardNote" style={{ padding: "8px 2px" }}>
                      Nothing here.
                    </p>
                  )}
                  {column.incidents.map(x => (
                    <button
                      key={x.id}
                      className="boardCard"
                      onClick={() => navigate(`/incidents/${x.reference}`)}
                    >
                      <div className="id mono">{x.reference}</div>
                      <div className="name">{x.title}</div>
                      <div className="row wrap" style={{ gap: 6 }}>
                        <SeverityBadge severity={x.severity} />
                        <span className="cardNote">{x.service_slug ?? "unassigned"}</span>
                      </div>
                      <div className="row" style={{ marginTop: 10, gap: 6 }}>
                        <Avatar name={x.lead_name ?? "Unassigned"} />
                        <span className="cardNote">
                          {duration(x.impact_started_at, null)} open
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              ))}
            </div>
          )}
        </section>

        <div className="grid cols2">
          <Card title="Outstanding post-incident tasks" note="Incidents still needing work">
            {post.data?.incidents.length ? (
              post.data.incidents.map(item => {
                const open = item.tasks.filter(t => t.status === "Open");
                if (!open.length) return null;
                return (
                  <div key={item.incident.id} style={{ marginBottom: 14 }}>
                    <Link to={`/incidents/${item.incident.reference}`} className="row">
                      <span className="mono">{item.incident.reference}</span>
                      <span className="title">{item.incident.title}</span>
                    </Link>
                    <ul className="evidence">
                      {open.map(t => (
                        <li key={t.id}>
                          {t.title}
                          <span className="cardNote"> · {t.owner?.full_name ?? "Unassigned"}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                );
              })
            ) : (
              <Empty>Nothing outstanding.</Empty>
            )}
          </Card>

          <Card title="Where incidents are coming from" note="Incidents by service">
            {insights.data ? (
              <ul className="evidence">
                {[...insights.data.by_service]
                  .sort((a, b) => b.count - a.count)
                  .slice(0, 6)
                  .map(s => (
                    <li key={s.name} className="row">
                      <Link className="mono" to={`/incidents?service=${s.name}`}>
                        {s.name}
                      </Link>
                      <span className="spacer cardNote" style={{ marginLeft: "auto" }}>
                        {s.count}
                      </span>
                    </li>
                  ))}
              </ul>
            ) : (
              <Empty>Loading…</Empty>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
