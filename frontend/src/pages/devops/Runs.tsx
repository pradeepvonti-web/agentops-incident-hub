// Runs list, grouped by status.
//
// The Linear pattern this copies: dense rows, grouped by status with a count in
// each header, status carried by a coloured glyph rather than a row background.
// Empty groups are hidden -- an "Awaiting approval (0)" header every day trains
// people to stop reading the headers.

import { Link, useSearchParams } from "react-router-dom";
import { listRuns } from "../../lib/controlPlane";
import { useAsync } from "../../lib/useAsync";
import { Card, Empty, ErrorNote, PageHeader } from "../../components/ui";
import { RunRow, StatusGlyph } from "../../devops/RunRow";
import { usePoll } from "../../devops/usePoll";
import {
  AGENT_LABEL,
  STATUS_DISPLAY,
  STATUS_GROUP_ORDER,
  type AgentType,
  type Environment,
  type RunStatus
} from "../../devops/types";

const AGENTS: AgentType[] = ["data-engineering", "data-quality", "orchestrator"];
const ENVIRONMENTS: Environment[] = ["dev", "test", "prod"];

export function Runs({ only }: { only?: RunStatus }) {
  const [params, setParams] = useSearchParams();
  const status = only ?? ((params.get("status") as RunStatus | null) ?? undefined);
  const agent = (params.get("agent") as AgentType | null) ?? undefined;
  const environment = (params.get("env") as Environment | null) ?? undefined;

  const tick = usePoll();
  const { data, loading, error } = useAsync(
    () => listRuns({ status, agent_type: agent, environment, limit: 200 }),
    [tick, status, agent, environment]
  );

  function set(key: string, value: string | undefined) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  }

  const groups = STATUS_GROUP_ORDER.map(s => ({
    status: s,
    runs: (data ?? []).filter(r => r.status === s)
  })).filter(g => g.runs.length);

  return (
    <>
      <PageHeader
        icon={only === "awaiting_approval" ? "✓" : "▤"}
        eyebrow="AI DevOps"
        title={only === "awaiting_approval" ? "Approvals" : "Runs"}
        actions={
          <Link className="btn" to="/devops">
            Start a run
          </Link>
        }
      />
      <div className="pageBody">
        {error && <ErrorNote message={error} />}

        <div className="row wrap">
          {!only && (
            <div className="filters">
              <button className={!status ? "filter active" : "filter"} onClick={() => set("status", undefined)}>
                All
              </button>
              {STATUS_GROUP_ORDER.map(s => (
                <button key={s} className={status === s ? "filter active" : "filter"} onClick={() => set("status", s)}>
                  {STATUS_DISPLAY[s].label}
                </button>
              ))}
            </div>
          )}
          <span className="spacer" style={{ marginLeft: "auto" }} />
          <select className="select" value={agent ?? ""} onChange={e => set("agent", e.target.value || undefined)}>
            <option value="">Any agent</option>
            {AGENTS.map(a => (
              <option key={a} value={a}>
                {AGENT_LABEL[a]}
              </option>
            ))}
          </select>
          <select className="select" value={environment ?? ""} onChange={e => set("env", e.target.value || undefined)}>
            <option value="">Any environment</option>
            {ENVIRONMENTS.map(env => (
              <option key={env} value={env}>
                {env}
              </option>
            ))}
          </select>
        </div>

        <Card tight>
          {loading && !data && <Empty>Loading…</Empty>}
          {data && !groups.length && (
            <Empty>
              No runs match these filters. <Link to="/devops">Start a run</Link>
            </Empty>
          )}
          {groups.map(group => (
            <section className="runGroup" key={group.status}>
              <header>
                <StatusGlyph status={group.status} />
                {STATUS_DISPLAY[group.status].label}
                <span className="count">{group.runs.length}</span>
              </header>
              {group.runs.map(run => (
                <RunRow key={run.run_id} run={run} />
              ))}
            </section>
          ))}
        </Card>
      </div>
    </>
  );
}
