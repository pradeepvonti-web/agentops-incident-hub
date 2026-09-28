// Entry points: the six front doors, as an operations surface rather than a launcher.
//
// Every one of them goes through the same orchestrator, the same approval gate
// and the same trace, so a request from Teams is governed exactly like one from
// the CLI. What a platform team needs from this screen is which doors carry the
// workload and which are a maintenance cost nobody uses.

import { getAdoption } from "../../lib/controlPlane";
import { useAsync } from "../../lib/useAsync";
import { Card, Empty, ErrorNote, Metric, PageHeader, Pill } from "../../components/ui";
import { ENTRY_POINTS, SOURCE_HUES } from "../../devops/entry";
import { usePoll } from "../../devops/usePoll";

export function EntryPoints() {
  const tick = usePoll(30000);
  const { data, loading, error } = useAsync(getAdoption, [tick]);
  const counts = data?.by_source;
  const total = counts ? Object.values(counts).reduce((n, c) => n + c, 0) : 0;
  const busiest = counts
    ? ENTRY_POINTS.reduce((best, ep) => (counts[ep.source] > (counts[best.source] ?? 0) ? ep : best), ENTRY_POINTS[0])
    : null;

  return (
    <>
      <PageHeader icon="⌂" eyebrow="AI DevOps" title="Entry points" />
      <div className="pageBody">
        {error && <ErrorNote message={error} />}

        <div className="grid cols4">
          <Metric label="Front doors" value={ENTRY_POINTS.length} foot="Fixed by the architecture; a seventh is a product decision" />
          <Metric label="Runs submitted" value={counts ? total : "—"} foot="All time, this tenant" />
          <Metric label="Busiest" value={busiest && total ? busiest.label : "—"} foot={busiest && total ? `${counts![busiest.source]} runs` : "No runs yet"} />
          <Metric label="Unattended" value={ENTRY_POINTS.filter(ep => !ep.interactive).length} foot="Doors with no invoking human; capped by the schedule owner" />
        </div>

        <Card title="Where runs came from" note="Proportion, not six numbers: which doors carry the workload">
          {loading && !counts && <Empty>Loading…</Empty>}
          {counts && (
            <>
              <div className="volBar">
                {ENTRY_POINTS.map(ep => (
                  <span
                    key={ep.source}
                    style={{ width: `${total ? (counts[ep.source] / total) * 100 : 0}%`, background: SOURCE_HUES[ep.source] }}
                    title={`${ep.label}: ${counts[ep.source]}`}
                  />
                ))}
              </div>
              <div className="volLegend">
                {ENTRY_POINTS.map(ep => (
                  <span key={ep.source}>
                    <span className="swatch" style={{ background: SOURCE_HUES[ep.source] }} />
                    {ep.label} <b>{counts[ep.source]}</b>
                  </span>
                ))}
              </div>
            </>
          )}
        </Card>

        <Card title="The six doors" note="Same object, same authorisation, same trace, whichever door a request came through" tight>
          <div className="tableWrap">
            <table>
              <thead>
                <tr>
                  <th>Entry point</th>
                  <th>How it is used</th>
                  <th>Invoking human</th>
                  <th style={{ textAlign: "right" }}>Runs</th>
                </tr>
              </thead>
              <tbody>
                {ENTRY_POINTS.map(ep => (
                  <tr key={ep.source}>
                    <td>
                      <span className="row">
                        <span className="swatch" style={{ background: SOURCE_HUES[ep.source] }} />
                        <span>
                          <div className="title">{ep.label}</div>
                          <div className="cardNote mono">{ep.source}</div>
                        </span>
                      </span>
                    </td>
                    <td>{ep.caption}</td>
                    <td>{ep.interactive ? <Pill tone="done">Required</Pill> : <Pill>Idempotency key instead</Pill>}</td>
                    <td className="mono" style={{ textAlign: "right" }}>
                      {counts ? counts[ep.source] : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="cardNote" style={{ padding: "12px 18px" }}>
            An entry point records where a run came from; it never affects what that run is allowed to do. Permissions are
            the agent's, intersected with the invoking user's (ADR-0002).
          </p>
        </Card>
      </div>
    </>
  );
}
