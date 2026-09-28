/**
 * The AI DevOps control plane client.
 *
 * Unlike `data.ts`, nothing here touches Supabase tables directly: the control
 * plane's tables are deny-all to PostgREST on purpose (its migration 0003), and
 * tenant scoping happens server-side from the session. The browser sends the
 * Supabase access token; the control plane asks Supabase Auth who it belongs
 * to and looks up the tenant (ADR-0005).
 *
 * Everything returned is metadata tier. If you want a field that contains
 * customer code, a prompt or a diff, the answer is a deep link into the
 * customer's own workspace, not a new control plane field (ADR-0003).
 */
import { supabase } from "./supabase";
import type { EntrySource } from "../devops/entry";
import type {
  AgentType,
  Environment,
  RunDetail,
  RunStats,
  RunStatus,
  RunSummary
} from "../devops/types";

const BASE = (import.meta.env.VITE_CONTROL_PLANE_URL ?? "http://localhost:8010").replace(/\/$/, "");

export class ControlPlaneError extends Error {
  constructor(
    message: string,
    readonly status: number
  ) {
    super(message);
  }
}

async function token(): Promise<string> {
  const { data } = await supabase.auth.getSession();
  const access = data.session?.access_token;
  if (!access) throw new ControlPlaneError("Not signed in", 401);
  return access;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: {
        Authorization: `Bearer ${await token()}`,
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...(init.headers ?? {})
      }
    });
  } catch {
    // A network failure, or a 500 whose response carries no CORS headers and is
    // therefore invisible to the page; the control plane's log has the traceback.
    throw new ControlPlaneError(
      `No answer from the control plane at ${BASE}. If it is not running, start it with the "control-plane" launch configuration or set VITE_CONTROL_PLANE_URL; if it is, check its log for an error.`,
      0
    );
  }
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* not JSON */
    }
    throw new ControlPlaneError(detail, response.status);
  }
  return response.json() as Promise<T>;
}

export interface RunFilters {
  status?: RunStatus;
  agent_type?: AgentType;
  environment?: Environment;
  limit?: number;
}

export function listRuns(filters: RunFilters = {}): Promise<RunSummary[]> {
  const params = new URLSearchParams(
    Object.entries(filters)
      .filter(([, v]) => v !== undefined)
      .map(([k, v]) => [k, String(v)])
  );
  const qs = params.toString();
  return request<RunSummary[]>(`/v1/runs${qs ? `?${qs}` : ""}`);
}

export function getRun(runId: string): Promise<RunDetail> {
  return request<RunDetail>(`/v1/runs/${encodeURIComponent(runId)}`);
}

export function getRunStats(): Promise<RunStats> {
  return request<RunStats>("/v1/runs/stats");
}

export function getAdoption(): Promise<{ tenant_id: string; by_source: Record<EntrySource, number> }> {
  return request("/v1/entry/adoption");
}

/**
 * `artifact_digest` is what the reviewer actually saw on the run page. It is
 * passed through, never re-fetched here: refetching would re-bind the approval
 * to whatever the artifact is *now*, which is precisely the bug ADR-0002 §5 forbids.
 */
export function submitApproval(
  runId: string,
  decision: { approved: boolean; artifact_digest: string; comment?: string }
): Promise<{ status: RunStatus }> {
  return request(`/v1/runs/${encodeURIComponent(runId)}/approval`, {
    method: "POST",
    body: JSON.stringify(decision)
  });
}

export function submitRun(input: {
  agent_type: AgentType;
  environment: Environment;
  requirement: string;
  title?: string;
  target_catalog?: string;
  target_schema?: string;
}): Promise<{ run_id: string; status: RunStatus; entry_point: string; requires_approval: boolean }> {
  // The shell is the portal door. `source` is the only thing a door gets to vary.
  return request("/v1/entry/runs", {
    method: "POST",
    body: JSON.stringify({ source: "portal", ...input })
  });
}
