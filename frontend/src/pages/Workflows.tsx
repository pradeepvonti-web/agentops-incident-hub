import { useState } from "react";
import { getWorkflows, runWorkflow, setWorkflowEnabled } from "../lib/data";
import { useAsync } from "../lib/useAsync";
import { useLiveTable } from "../lib/useLive";
import { Card, Empty, ErrorNote, PageHeader, Pill } from "../components/ui";

export function Workflows() {
  const tick = useLiveTable("workflows");
  const { data, loading, error } = useAsync(getWorkflows, [tick]);
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
      <PageHeader icon="⇉" title="Workflows" />
      <div className="pageBody">
        {error && <ErrorNote message={error} />}
        {loading && !data && <Empty>Loading…</Empty>}

        {data?.map(w => (
          <Card key={w.id}>
            <div className="row wrap" style={{ marginBottom: 12 }}>
              <h2>{w.name}</h2>
              <span className="spacer row" style={{ marginLeft: "auto" }}>
                <span className="cardNote">{w.runs_7d} runs in 7 days</span>
                <button
                  className="btn"
                  disabled={busy === w.id || !w.enabled}
                  onClick={() => run(w.id, () => runWorkflow(w.id, "Ran manually from the console"))}
                >
                  Run now
                </button>
                <button
                  className={w.enabled ? "filter active" : "filter"}
                  disabled={busy === w.id}
                  onClick={() => run(w.id, () => setWorkflowEnabled(w.id, !w.enabled))}
                >
                  {w.enabled ? "Live" : "Paused"}
                </button>
              </span>
            </div>

            <div className="grid cols3">
              <div>
                <h3>When</h3>
                <p className="cardNote">{w.trigger}</p>
              </div>
              <div>
                <h3>And these conditions are met</h3>
                {w.conditions.map(c => (
                  <p className="cardNote mono" key={c}>
                    {c}
                  </p>
                ))}
              </div>
              <div>
                <h3>Then</h3>
                {w.steps.map(s => (
                  <p className="cardNote" key={s}>
                    {s}
                  </p>
                ))}
              </div>
            </div>
          </Card>
        ))}
      </div>
    </>
  );
}
