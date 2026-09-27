import { getInsights } from "../lib/data";
import { useAsync } from "../lib/useAsync";
import { useLiveTable } from "../lib/useLive";
import { minutes } from "../lib/format";
import { SeverityBadge } from "../components/SeverityBadge";
import { BarList, Card, Empty, ErrorNote, Metric, PageHeader } from "../components/ui";
import type { Severity } from "../types";

export function InsightsPage() {
  const tick = useLiveTable("incidents");
  const { data, loading, error } = useAsync(getInsights, [tick]);

  return (
    <>
      <PageHeader icon="▤" title="Insights" />
      <div className="pageBody">
        {error && <ErrorNote message={error} />}
        {loading && !data && <Empty>Loading…</Empty>}

        {data && (
          <>
            <div className="grid cols4">
              <Metric
                label="Incidents"
                value={data.total_incidents}
                foot={`${data.active_incidents} active`}
              />
              <Metric
                label="Mean time to declare"
                value={minutes(data.mean_minutes_to_declare)}
                foot="Impact started to declared"
              />
              <Metric
                label="Mean time to resolve"
                value={minutes(data.mean_minutes_to_fix)}
                foot="Impact started to fixed"
              />
              <Metric
                label="Open follow-ups"
                value={data.open_follow_ups}
                foot={`${data.open_tasks} post-incident tasks open`}
              />
            </div>

            <div className="grid cols2">
              <Card title="By severity" note="Every incident in the workspace">
                {data.by_severity.map(s => {
                  const max = Math.max(1, ...data.by_severity.map(v => v.count));
                  return (
                    <div className="barRow" key={s.name}>
                      <SeverityBadge severity={s.name as Severity} />
                      <span className="barTrack">
                        <span
                          className="barFill"
                          style={{ width: `${Math.round((s.count / max) * 100)}%` }}
                        />
                      </span>
                      <span className="value">{s.count}</span>
                    </div>
                  );
                })}
              </Card>

              <Card title="By lifecycle status" note="Where work is sitting">
                <BarList rows={data.by_status} />
              </Card>

              <Card title="By category" note="Canonical categories only">
                <BarList rows={data.by_category} />
              </Card>

              <Card title="By service" note="Which services generate incidents">
                <BarList rows={[...data.by_service].sort((a, b) => b.count - a.count)} />
              </Card>
            </div>
          </>
        )}
      </div>
    </>
  );
}
