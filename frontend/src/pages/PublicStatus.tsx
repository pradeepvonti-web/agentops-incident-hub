import { getStatusPage } from "../lib/data";
import { useAsync } from "../lib/useAsync";
import { useLiveTables } from "../lib/useLive";
import { dateTime } from "../lib/format";
import { uptimeCells } from "./StatusPageView";
import { Pill } from "../components/ui";
import { Logo } from "../components/Logo";

/**
 * The customer-facing page. No account required: anonymous readers are allowed
 * to select from status_page, status_components and status_updates by RLS, and
 * nothing else in the schema.
 */
export function PublicStatus() {
  const tick = useLiveTables(["status_updates", "status_components"]);
  const { data, loading, error } = useAsync(getStatusPage, [tick]);
  const degraded = data && data.overall !== "All systems operational";

  return (
    <div className="publicShell">
      <div className="publicPage">
        <header className="row" style={{ marginBottom: 24 }}>
          <Logo size={20} />
          <div>
            <h1 style={{ fontSize: 14, color: "var(--muted)", fontFamily: "var(--font-ui)", fontWeight: 600, letterSpacing: ".06em", textTransform: "uppercase" }}>
              Status
            </h1>
            <p className="cardNote">{data?.url}</p>
          </div>
        </header>

        {loading && <p className="cardNote">Loading…</p>}
        {error && (
          <div className="error">
            Status is unavailable right now. ({error})
          </div>
        )}

        {data && (
          <>
            <div className={`statusHero ${degraded ? "degraded" : "ok"}`}>
              <h2>{data.overall}</h2>
              <p className="cardNote">
                Updated {dateTime(data.updates[0]?.published_at ?? new Date().toISOString())}
              </p>
            </div>

            <section className="card" style={{ marginTop: 18 }}>
              <h2 style={{ marginBottom: 14 }}>Current status by component</h2>
              {data.components.map(c => (
                <div key={c.id} style={{ marginBottom: 14 }}>
                  <div className="railRow">
                    <span className="title">{c.name}</span>
                    <span className="row">
                      <span className="cardNote">{Number(c.uptime_90d).toFixed(2)}% uptime</span>
                      <Pill tone={c.status === "Operational" ? "done" : "open"}>{c.status}</Pill>
                    </span>
                  </div>
                  <div className="uptimeBar">
                    {uptimeCells(Number(c.uptime_90d)).map((cls, i) => (
                      <i key={i} className={cls} />
                    ))}
                  </div>
                </div>
              ))}
            </section>

            <section className="card" style={{ marginTop: 18 }}>
              <h2 style={{ marginBottom: 14 }}>Recent updates</h2>
              {!data.updates.length && <p className="cardNote">No incidents reported.</p>}
              {data.updates.map(u => (
                <article className="update" key={u.id}>
                  <div className="meta">
                    <Pill>{u.status}</Pill>
                    <span className="cardNote">{dateTime(u.published_at)}</span>
                  </div>
                  <p>{u.message}</p>
                </article>
              ))}
            </section>

            <p className="cardNote" style={{ marginTop: 20, textAlign: "center" }}>
              Powered by Restora
            </p>
          </>
        )}
      </div>
    </div>
  );
}
