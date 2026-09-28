// Mirrors aidevops/packages/adp-contracts. Keep in sync -- a mismatch here shows
// up as a silently empty column in the runs list rather than a type error.

import type { EntrySource } from "./entry";

export type AgentType = "data-engineering" | "data-quality" | "orchestrator";

export type Environment = "dev" | "test" | "prod";

export type RunStatus =
  | "queued"
  | "running"
  | "awaiting_approval"
  | "succeeded"
  | "failed"
  | "rejected"
  | "cancelled"
  | "rolled_back";

export type StepKind = "plan" | "tool" | "generate" | "validate" | "approve" | "deploy" | "monitor";

export interface RunSummary {
  run_id: string;
  agent_type: AgentType;
  environment: Environment;
  status: RunStatus;
  entry_source: EntrySource;
  title: string;
  invoked_by: string;
  created_at: string;
  duration_seconds: number | null;
  awaiting_approval: boolean;
}

/** One row of `public.run_spans`. Metadata tier only: digests, timing, decisions.
 *  Payload fields are absent by design (ADR-0003); do not add them here. */
export interface Span {
  span_id: string;
  parent_span_id: string | null;
  name: string;
  step: StepKind;
  status: string;
  attempt: number;
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
  error_class: string | null;
  tool_name: string | null;
  tool_decision: string | null;
  policy_reason: string | null;
  arguments_digest: string | null;
  result_digest: string | null;
  model: string | null;
  tokens_in: number | null;
  tokens_out: number | null;
  cost_usd: number | null;
  cache_hit: boolean | null;
}

export interface Approval {
  approval_id: number;
  approved: boolean;
  artifact_digest: string;
  approved_by: string;
  comment: string | null;
  decided_at: string;
}

export interface RunDetail {
  run: RunSummary;
  spans: Span[];
  artifact_digest: string | null;
  approvals: Approval[];
}

export interface RunStats {
  by_status: Partial<Record<RunStatus, number>>;
  acceptance: {
    n: number;
    accepted: number;
    clean_accepted: number;
    median_edit_ratio: number;
    acceptance_rate: number;
    clean_accept_rate: number;
    meaningful: boolean;
  };
}

export const AGENT_LABEL: Record<AgentType, string> = {
  "data-engineering": "Data Engineering",
  "data-quality": "Data Quality",
  orchestrator: "Orchestrator"
};

/** Status display. Colour carries meaning; row background never does. */
export const STATUS_DISPLAY: Record<RunStatus, { label: string; tone: "open" | "done" | "neutral" | "closed" }> = {
  queued: { label: "Queued", tone: "neutral" },
  running: { label: "Running", tone: "neutral" },
  awaiting_approval: { label: "Awaiting approval", tone: "open" },
  succeeded: { label: "Succeeded", tone: "done" },
  failed: { label: "Failed", tone: "open" },
  rejected: { label: "Rejected", tone: "closed" },
  cancelled: { label: "Cancelled", tone: "closed" },
  rolled_back: { label: "Rolled back", tone: "open" }
};

/** Order groups the way an engineer triages: what needs me, then what is live. */
export const STATUS_GROUP_ORDER: RunStatus[] = [
  "awaiting_approval",
  "running",
  "queued",
  "failed",
  "rolled_back",
  "rejected",
  "succeeded",
  "cancelled"
];

export const STEP_ORDER: StepKind[] = ["plan", "tool", "generate", "validate", "approve", "deploy", "monitor"];
