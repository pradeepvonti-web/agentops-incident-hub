import type { Severity } from "../types";

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <span className={`badge badge-${severity.toLowerCase()}`}>{severity}</span>;
}
