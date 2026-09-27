import { LIFECYCLE, type Status } from "../types";

const TONE: Record<Status, string> = {
  Triage: "#7b8798",
  Investigating: "#b3261e",
  Fixing: "#a4501a",
  Monitoring: "#18558e",
  Documenting: "#4a5568",
  Reviewing: "#4a5568",
  Closed: "#1a7f52"
};

/** A single status, used wherever a full lifecycle would be too wide. */
export function StatusPill({ status }: { status: Status }) {
  return (
    <span className="pill" style={{ color: TONE[status] }}>
      <span className="dot" />
      {status}
    </span>
  );
}

/**
 * The full incident lifecycle with the current status highlighted.
 * Mirrors docs/INCIDENT_RULES.md: statuses are ordered and an incident
 * only moves forward through them.
 */
export function LifecycleBar({ status }: { status: Status }) {
  const current = LIFECYCLE.indexOf(status);
  return (
    <div className="lifecycle">
      {LIFECYCLE.map((step, i) => (
        <span key={step} className="row" style={{ gap: 4 }}>
          {i > 0 && <span className="sep">›</span>}
          <span
            className={
              i === current ? "step current" : i < current ? "step done" : "step"
            }
          >
            {step}
          </span>
        </span>
      ))}
    </div>
  );
}
