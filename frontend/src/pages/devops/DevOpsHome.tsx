// AI DevOps home.
//
// The front door is the composer at the top: the place a request actually gets
// written. Then what is blocked on you, because finished work waiting on a human
// is the most expensive state in the system. Then what is moving. Metrics sit
// between them as a strip rather than a dashboard -- context, not the job.

import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getRunStats, listRuns, submitRun } from "../../lib/controlPlane";
import { useAsync } from "../../lib/useAsync";
import { Field, FormError, useSubmit } from "../../components/forms";
import { Card, Empty, ErrorNote, Metric, PageHeader } from "../../components/ui";
import { RunRow } from "../../devops/RunRow";
import { usePoll } from "../../devops/usePoll";
import { AGENT_LABEL, type AgentType, type Environment } from "../../devops/types";

const AGENTS: AgentType[] = ["data-engineering", "data-quality"];
const ENVIRONMENTS: Environment[] = ["dev", "test", "prod"];

function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function DevOpsHome() {
  const tick = usePoll();
  const runs = useAsync(() => listRuns({ limit: 100 }), [tick]);
  const stats = useAsync(getRunStats, [tick]);

  const awaiting = (runs.data ?? []).filter(r => r.status === "awaiting_approval");
  const active = (runs.data ?? []).filter(r => r.status === "running" || r.status === "queued");
  const acceptance = stats.data?.acceptance;

  return (
    <>
      <PageHeader
        icon="◈"
        eyebrow="Agentic data engineering, with a human in the loop"
        title="AI DevOps"
        actions={
          <>
            <Link className="btn" to="/devops/runs">
              All runs
            </Link>
            <Link className="btn" to="/devops/entry-points">
              Entry points
            </Link>
          </>
        }
      />
      <div className="pageBody">
        {runs.error && <ErrorNote message={runs.error} />}

        <Composer />

        <div className="grid cols4">
          <Metric
            label="Acceptance rate"
            value={acceptance ? pct(acceptance.acceptance_rate) : "—"}
            foot={
              acceptance
                ? acceptance.meaningful
                  ? `n=${acceptance.n}, last 7 days`
                  : `n=${acceptance.n}: too few runs to mean anything yet`
                : "Merged without a human rewriting it"
            }
          />
          <Metric
            label="Merged without edit"
            value={acceptance ? pct(acceptance.clean_accept_rate) : "—"}
            foot={acceptance ? `median edit ratio ${acceptance.median_edit_ratio.toFixed(2)}` : "The honest headline number"}
          />
          <Metric label="Waiting on a human" value={runs.data ? awaiting.length : "—"} foot="Approvals bind to the exact artifact" />
          <Metric label="In flight" value={runs.data ? active.length : "—"} foot="Running or queued" />
        </div>

        <div className="grid cols2">
          <Card title="Waiting on you" note="Approving binds to the exact diff. If the agent regenerates, the approval is void." tight>
            {runs.loading && !runs.data && <Empty>Loading…</Empty>}
            {runs.data && !awaiting.length && <Empty>Nothing is blocked on you.</Empty>}
            {awaiting.map(run => (
              <RunRow key={run.run_id} run={run} />
            ))}
          </Card>
          <Card title="In flight" note="Runs the execution plane is working on" tight>
            {runs.loading && !runs.data && <Empty>Loading…</Empty>}
            {runs.data && !active.length && <Empty>Nothing is running. Start one above.</Empty>}
            {active.map(run => (
              <RunRow key={run.run_id} run={run} />
            ))}
          </Card>
        </div>
      </div>
    </>
  );
}

function Composer() {
  const navigate = useNavigate();
  const [requirement, setRequirement] = useState("");
  const [title, setTitle] = useState("");
  const [agent, setAgent] = useState<AgentType>("data-engineering");
  const [environment, setEnvironment] = useState<Environment>("dev");
  const [target, setTarget] = useState("silver.curated");

  const { onSubmit, pending, error } = useSubmit(async () => {
    const [catalog, schema] = target.split(".");
    const result = await submitRun({
      agent_type: agent,
      environment,
      requirement,
      title: title.trim() || undefined,
      target_catalog: catalog || undefined,
      target_schema: schema || undefined
    });
    navigate(`/devops/runs/${result.run_id}`);
  });

  return (
    <Card title="Start a run" note="Describe what you need built. The orchestrator picks the agent, the agent opens a pull request, and you review the diff.">
      <form onSubmit={onSubmit} className="composer">
        <FormError message={error} />
        <Field label="What should the agent build?" hint="Stays in your tenant. The control plane keeps only a digest of it.">
          <textarea
            className="input"
            value={requirement}
            onChange={e => setRequirement(e.target.value)}
            placeholder="Ingest SAP delivery notes into bronze, then build a Silver table keyed on delivery_id with null checks on the ship date…"
            required
          />
        </Field>
        <div className="grid cols4">
          <Field label="Label" hint="Shown in run lists">
            <input className="input" value={title} onChange={e => setTitle(e.target.value)} placeholder="Bronze to Silver: delivery_notes" maxLength={120} />
          </Field>
          <Field label="Agent">
            <select className="select" value={agent} onChange={e => setAgent(e.target.value as AgentType)}>
              {AGENTS.map(a => (
                <option key={a} value={a}>
                  {AGENT_LABEL[a]}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Target" hint="catalog.schema">
            <input className="input mono" value={target} onChange={e => setTarget(e.target.value)} />
          </Field>
          <Field label="Environment" hint={environment === "prod" ? "Prod writes need an approver" : "No approval needed"}>
            <select className="select" value={environment} onChange={e => setEnvironment(e.target.value as Environment)}>
              {ENVIRONMENTS.map(env => (
                <option key={env} value={env}>
                  {env}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <div className="row">
          <button className="btn primary" disabled={pending || !requirement.trim()}>
            {pending ? "Queuing…" : "Start run"}
          </button>
          <span className="cardNote">The agent proposes; a human merges. It cannot push to a default branch or merge its own pull request.</span>
        </div>
      </form>
    </Card>
  );
}
