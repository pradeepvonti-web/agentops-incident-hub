// Run detail: the span tree, the approval decision, and what Restora did about it.
//
// Everything on this page is the metadata tier. Prompts, generated code and
// diffs live in the customer's own subscription (ADR-0003); the page shows
// digests and links out rather than proxying them.

import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getRun, submitApproval } from "../../lib/controlPlane";
import { getAlertsForRun } from "../../lib/data";
import { useAsync } from "../../lib/useAsync";
import { useLiveTable } from "../../lib/useLive";
import { dateTime } from "../../lib/format";
import { Field, FormError, useSubmit } from "../../components/forms";
import { Card, Empty, ErrorNote, PageHeader, Pill } from "../../components/ui";
import { ENTRY_POINTS_BY_SOURCE } from "../../devops/entry";
import { StatusPill, seconds } from "../../devops/RunRow";
import { usePoll } from "../../devops/usePoll";
import { AGENT_LABEL, type RunDetail as Detail, type Span } from "../../devops/types";

function ms(value: number | null): string {
  if (value === null) return "—";
  return value < 1000 ? `${value} ms` : `${(value / 1000).toFixed(1)} s`;
}

export function RunDetail() {
  const { runId = "" } = useParams();
  const tick = usePoll(10000);
  const [version, setVersion] = useState(0);
  const { data, loading, error } = useAsync(() => getRun(runId), [runId, tick, version]);

  const alertTick = useLiveTable("alerts");
  const alerts = useAsync(() => getAlertsForRun(runId), [runId, alertTick]);

  return (
    <>
      <PageHeader
        icon="▤"
        eyebrow={
          <span>
            <Link to="/devops/runs">Runs</Link> · <span className="mono">{runId}</span>
          </span>
        }
        title={data?.run.title ?? runId}
        actions={data && <StatusPill status={data.run.status} />}
      />
      <div className="pageBody">
        {error && <ErrorNote message={error} />}
        {loading && !data && <Empty>Loading…</Empty>}

        {data && (
          <div className="split">
            <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
              <SpanTree spans={data.spans} />

              <Card title="Alerts raised in Restora" note="The database raises one when a run fails or is rolled back" tight>
                {alerts.data && !alerts.data.length && <Empty>None. This run has not failed.</Empty>}
                {alerts.data?.map(a => (
                  <div className="railRow" key={a.id} style={{ padding: "10px 18px" }}>
                    <span>
                      <span className="title">{a.title}</span>
                      <div className="cardNote mono">{a.reference}</div>
                    </span>
                    <span className="row">
                      <Pill>{a.priority}</Pill>
                      <Pill tone={a.status === "Resolved" ? "done" : a.status === "Escalated" ? "open" : "neutral"}>{a.status}</Pill>
                      {a.incident ? (
                        <Link className="mono" to={`/incidents/${a.incident.reference}`}>
                          {a.incident.reference}
                        </Link>
                      ) : (
                        <Link className="btn ghost" to="/alerts">
                          Open in alerts
                        </Link>
                      )}
                    </span>
                  </div>
                ))}
              </Card>
            </div>

            <div className="rail">
              <Card title="Run">
                <Meta label="Agent" value={AGENT_LABEL[data.run.agent_type]} />
                <Meta label="Environment" value={data.run.environment} />
                <Meta label="Entry point" value={ENTRY_POINTS_BY_SOURCE[data.run.entry_source].label} />
                <Meta label="Invoked by" value={data.run.invoked_by} />
                <Meta label="Created" value={dateTime(data.run.created_at)} />
                <Meta label="Duration" value={seconds(data.run.duration_seconds)} />
              </Card>

              <ApprovalCard detail={data} onDecided={() => setVersion(v => v + 1)} />

              <Card title="Payloads" note="Prompts, generated code and the diff never leave the tenant">
                <p className="cardNote">
                  Open the pull request and the trace in your own workspace. The control plane stores digests only
                  (ADR-0003).
                </p>
              </Card>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="railRow">
      <span className="label">{label}</span>
      <span className="ellipsis" style={{ textAlign: "right" }}>
        {value}
      </span>
    </div>
  );
}

function SpanTree({ spans }: { spans: Span[] }) {
  // Children sit under their parent, in start order; everything else is a root.
  const roots = spans.filter(s => !s.parent_span_id || !spans.some(p => p.span_id === s.parent_span_id));
  const children = (id: string) => spans.filter(s => s.parent_span_id === id);

  return (
    <Card title="Trace" note="plan → tool → generate → validate → approve → deploy → monitor. Every step emits a span, including denials." tight>
      {!spans.length && <Empty>No spans yet. The execution plane has not claimed this run.</Empty>}
      {roots.map(span => (
        <div key={span.span_id}>
          <SpanRow span={span} />
          {children(span.span_id).map(child => (
            <SpanRow key={child.span_id} span={child} child />
          ))}
        </div>
      ))}
    </Card>
  );
}

function SpanRow({ span, child }: { span: Span; child?: boolean }) {
  const denied = !!span.tool_decision && span.tool_decision !== "allow";
  return (
    <div className={`spanRow${child ? " child" : ""}`}>
      <span>
        <span className={`stepTag${denied ? " denied" : ""}`}>{span.step}</span>
      </span>
      <span style={{ minWidth: 0 }}>
        <div className="title">{span.name}</div>
        {span.tool_name && (
          <div className="detail">
            {span.tool_name} · {span.tool_decision}
            {span.policy_reason && ` — ${span.policy_reason}`}
          </div>
        )}
        {span.model && (
          <div className="detail">
            {span.model}
            {span.tokens_in !== null && ` · ${span.tokens_in} in / ${span.tokens_out} out`}
            {span.cost_usd !== null && ` · $${Number(span.cost_usd).toFixed(4)}`}
            {span.cache_hit && " · cache hit"}
          </div>
        )}
        {span.error_class && <div className="detail" style={{ color: "var(--crit)" }}>{span.error_class}</div>}
        {(span.arguments_digest || span.result_digest) && (
          <div className="detail mono">
            {span.arguments_digest && `args ${span.arguments_digest}`}
            {span.arguments_digest && span.result_digest && " · "}
            {span.result_digest && `result ${span.result_digest}`}
          </div>
        )}
      </span>
      <span>
        <Pill tone={span.status === "succeeded" ? "done" : span.status === "failed" || span.status === "rejected" ? "open" : "neutral"}>
          {span.status.replace("_", " ")}
        </Pill>
      </span>
      <span className="cardNote mono" style={{ textAlign: "right" }}>
        {ms(span.duration_ms)}
      </span>
    </div>
  );
}

function ApprovalCard({ detail, onDecided }: { detail: Detail; onDecided: () => void }) {
  const [comment, setComment] = useState("");
  const [decision, setDecision] = useState<boolean | null>(null);
  const digest = detail.artifact_digest;
  const awaiting = detail.run.status === "awaiting_approval";

  const { onSubmit, pending, error } = useSubmit(async () => {
    if (decision === null || !digest) return;
    // The digest this page rendered is the one that gets approved. Never re-fetch.
    await submitApproval(detail.run.run_id, { approved: decision, artifact_digest: digest, comment: comment || undefined });
    setComment("");
    onDecided();
  });

  return (
    <Card title="Approval" note={awaiting ? "A human decides; the agent cannot approve its own work" : undefined}>
      {awaiting ? (
        digest ? (
          <form onSubmit={onSubmit}>
            <FormError message={error} />
            <Field label="Artifact you are approving" hint="If the agent regenerates, this changes and the decision is refused.">
              <div className="mono" style={{ wordBreak: "break-all" }}>{digest}</div>
            </Field>
            <Field label="Comment">
              <input className="input" value={comment} onChange={e => setComment(e.target.value)} placeholder="Optional" />
            </Field>
            <div className="row">
              <button className="btn primary" disabled={pending} onClick={() => setDecision(true)}>
                {pending && decision ? "Approving…" : "Approve"}
              </button>
              <button className="btn" disabled={pending} onClick={() => setDecision(false)}>
                {pending && decision === false ? "Rejecting…" : "Reject"}
              </button>
            </div>
          </form>
        ) : (
          <p className="cardNote">Waiting for the agent to produce an artifact. Nothing to decide on yet.</p>
        )
      ) : (
        <p className="cardNote">Not awaiting approval.</p>
      )}

      {detail.approvals.length > 0 && (
        <div style={{ marginTop: 12 }}>
          {detail.approvals.map(a => (
            <div className="railRow" key={a.approval_id}>
              <span>
                <Pill tone={a.approved ? "done" : "open"}>{a.approved ? "Approved" : "Rejected"}</Pill>
                <div className="cardNote">
                  {a.approved_by} · {dateTime(a.decided_at)}
                </div>
                {a.comment && <div className="cardNote">“{a.comment}”</div>}
              </span>
              <span className="cardNote mono ellipsis" style={{ maxWidth: 120 }} title={a.artifact_digest}>
                {a.artifact_digest}
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
