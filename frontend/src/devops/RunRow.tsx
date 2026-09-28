import { Link } from "react-router-dom";
import { ENTRY_POINTS_BY_SOURCE } from "./entry";
import { AGENT_LABEL, STATUS_DISPLAY, type RunStatus, type RunSummary } from "./types";
import { Pill } from "../components/ui";

export function seconds(value: number | null): string {
  if (value === null) return "—";
  if (value < 60) return `${value}s`;
  if (value < 3600) return `${Math.floor(value / 60)}m`;
  return `${(value / 3600).toFixed(1)}h`;
}

export function StatusGlyph({ status }: { status: RunStatus }) {
  return <span className={`glyph ${status}`} aria-label={STATUS_DISPLAY[status].label} />;
}

export function StatusPill({ status }: { status: RunStatus }) {
  const meta = STATUS_DISPLAY[status];
  return <Pill tone={meta.tone}>{meta.label}</Pill>;
}

/**
 * One run, in the Linear idiom: dense, left-aligned into implicit columns,
 * status carried by a glyph rather than a row background. An engineer triaging
 * twenty runs should see all of them without scrolling.
 */
export function RunRow({ run }: { run: RunSummary }) {
  const door = ENTRY_POINTS_BY_SOURCE[run.entry_source];
  return (
    <Link className="runRow" to={`/devops/runs/${run.run_id}`}>
      <StatusGlyph status={run.status} />
      <span style={{ minWidth: 0 }}>
        <span className="title ellipsis" style={{ display: "block" }}>
          {run.title}
        </span>
        <span className="cardNote mono">{run.run_id}</span>
      </span>
      <span className="cardNote">{AGENT_LABEL[run.agent_type]}</span>
      <span className={`envTag${run.environment === "prod" ? " prod" : ""}`}>{run.environment}</span>
      <span className="cardNote ellipsis" title={`Submitted from ${door.label}`}>
        {door.label}
      </span>
      <span className="cardNote ellipsis">{run.invoked_by}</span>
      <span className="cardNote mono" style={{ textAlign: "right" }}>
        {seconds(run.duration_seconds)}
      </span>
    </Link>
  );
}
