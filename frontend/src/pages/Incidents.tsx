import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { listIncidents } from "../lib/data";
import { useAsync } from "../lib/useAsync";
import { useLiveTable } from "../lib/useLive";
import { IncidentTable } from "../components/IncidentTable";
import { Card, Empty, ErrorNote, PageHeader } from "../components/ui";
import { LIFECYCLE, SEVERITIES, type Severity, type Status } from "../types";

function toCsv(rows: Record<string, unknown>[]): string {
  if (!rows.length) return "";
  const headers = Object.keys(rows[0]);
  const escape = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  return [headers.join(","), ...rows.map(r => headers.map(h => escape(r[h])).join(","))].join("\n");
}

export function Incidents() {
  const [params, setParams] = useSearchParams();
  const service = params.get("service") ?? "";
  const [severity, setSeverity] = useState<"ALL" | Severity>("ALL");
  const [status, setStatus] = useState("all");
  const [q, setQ] = useState("");
  const tick = useLiveTable("incidents");

  const query = useMemo(
    () => ({
      severity: severity === "ALL" ? undefined : severity,
      status: (status === "all" ? undefined : status) as Status | "active" | undefined,
      service: service || undefined,
      q: q.trim() || undefined
    }),
    [severity, status, service, q]
  );

  const { data, loading, error } = useAsync(() => listIncidents(query), [
    query.severity,
    query.status,
    query.service,
    query.q,
    tick
  ]);

  const filtersApplied = severity !== "ALL" || status !== "all" || q.trim().length > 0 || !!service;

  function clearFilters() {
    setSeverity("ALL");
    setStatus("all");
    setQ("");
    setParams({});
  }

  function exportCsv() {
    const csv = toCsv(
      (data ?? []).map(x => ({
        id: x.reference,
        title: x.title,
        service: x.service_slug,
        category: x.category,
        severity: x.severity,
        status: x.status,
        lead: x.lead_name,
        declared_at: x.declared_at,
        fixed_at: x.fixed_at
      }))
    );
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "incidents.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <>
      <PageHeader
        icon="◆"
        title="Incidents"
        actions={
          <button className="btn" onClick={exportCsv} disabled={!data?.length}>
            Export CSV
          </button>
        }
      />

      <div className="pageBody">
        <Card tight>
          <div className="cardHead">
            <input
              className="input"
              style={{ width: 240 }}
              placeholder="Search incidents…"
              value={q}
              onChange={e => setQ(e.target.value)}
            />
            <select className="select" value={status} onChange={e => setStatus(e.target.value)}>
              <option value="all">Any status</option>
              <option value="active">Active only</option>
              {LIFECYCLE.map(s => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
            <div className="filters">
              {(["ALL", ...SEVERITIES] as const).map(s => (
                <button
                  key={s}
                  className={severity === s ? "filter active" : "filter"}
                  onClick={() => setSeverity(s as "ALL" | Severity)}
                >
                  {s}
                </button>
              ))}
            </div>
            {service && (
              <button className="filter active" onClick={() => setParams({})}>
                service is {service} ✕
              </button>
            )}
            <div className="spacer row">
              <span className="cardNote" data-testid="result-count">
                {data ? `Found ${data.length}` : "…"}
              </span>
              {filtersApplied && (
                <button className="btn ghost" onClick={clearFilters}>
                  Clear all filters
                </button>
              )}
            </div>
          </div>

          {error && (
            <div style={{ padding: 18 }}>
              <ErrorNote message={error} />
            </div>
          )}
          {loading && !data && <Empty>Loading…</Empty>}
          {!error && data && <IncidentTable incidents={data} />}
        </Card>
      </div>
    </>
  );
}
