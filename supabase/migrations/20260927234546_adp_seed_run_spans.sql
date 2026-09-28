-- Demo traces for the two seeded runs, so the run detail screen has a span tree
-- to render. Metadata tier only: digests, timing, decisions. No payloads.

insert into public.run_spans (
  span_id, parent_span_id, tenant_id, run_id, name, step, status, attempt,
  agent, agent_principal, environment, invoked_by,
  started_at, ended_at, duration_ms, error_class,
  tool_name, tool_decision, policy_reason, arguments_digest, result_digest,
  model, tokens_in, tokens_out, cost_usd, cache_hit
)
select s.span_id, s.parent_span_id, r.tenant_id, r.run_id, s.name, s.step::step_kind,
       s.status::step_status, 1, r.agent, r.agent_principal, r.environment, r.invoked_by,
       r.created_at + s.offset_s * interval '1 second',
       case when s.duration_ms is null then null
            else r.created_at + (s.offset_s * 1000 + s.duration_ms) * interval '1 millisecond' end,
       s.duration_ms, s.error_class,
       s.tool_name, s.tool_decision::tool_decision, s.policy_reason,
       s.arguments_digest, s.result_digest,
       s.model, s.tokens_in, s.tokens_out, s.cost_usd, s.cache_hit
from public.runs r
join (values
  -- run_acme_1: prod pipeline waiting on a human
  ('run_acme_1', 'sp_acme_1_plan', null, 'plan', 'plan', 'succeeded', 0, 6400, null,
     null, null, null, null, null, 'claude-sonnet-5', 3120, 640, 0.014200, false),
  ('run_acme_1', 'sp_acme_1_t1', 'sp_acme_1_plan', 'tool:uc_get_table_metadata', 'tool', 'succeeded', 7, 820, null,
     'uc_get_table_metadata', 'allow', null, 'sha256:4c1e9a7f0b2d', 'sha256:9d3b0c11aa42', null, null, null, null, null),
  ('run_acme_1', 'sp_acme_1_t2', 'sp_acme_1_plan', 'tool:uc_list_tables', 'tool', 'succeeded', 8, 410, null,
     'uc_list_tables', 'allow', null, 'sha256:11aa22bb33cc', 'sha256:0f0f1e1e2d2d', null, null, null, null, null),
  ('run_acme_1', 'sp_acme_1_gen', null, 'generate', 'generate', 'succeeded', 9, 21800, null,
     null, null, null, null, 'sha256:7a8e3c9b2f41d6e0', 'claude-sonnet-5', 5810, 2140, 0.039700, false),
  ('run_acme_1', 'sp_acme_1_val', null, 'validate', 'validate', 'succeeded', 31, 5300, null,
     'databricks_bundle_validate', 'allow', null, 'sha256:7a8e3c9b2f41d6e0', 'sha256:ok-0-diagnostics', null, null, null, null, null),
  ('run_acme_1', 'sp_acme_1_appr', null, 'approve', 'approve', 'awaiting_approval', 37, null, null,
     null, null, null, null, null, null, null, null, null, null),
  -- run_globex_1: dev data-quality run in progress, with one denied tool call
  ('run_globex_1', 'sp_globex_1_plan', null, 'plan', 'plan', 'succeeded', 0, 4100, null,
     null, null, null, null, null, 'claude-sonnet-5', 2210, 480, 0.009800, true),
  ('run_globex_1', 'sp_globex_1_t1', 'sp_globex_1_plan', 'tool:databricks_submit_job', 'tool', 'failed', 5, 12, null,
     'databricks_submit_job', 'deny_not_allowlisted', 'data-quality has no databricks_submit_job entry', 'sha256:d3adb33f0001', null, null, null, null, null, null),
  ('run_globex_1', 'sp_globex_1_t2', 'sp_globex_1_plan', 'tool:uc_get_table_metadata', 'tool', 'succeeded', 6, 730, null,
     'uc_get_table_metadata', 'allow', null, 'sha256:5e5e6f6f7a7a', 'sha256:8b8b9c9c0d0d', null, null, null, null, null),
  ('run_globex_1', 'sp_globex_1_gen', null, 'generate', 'generate', 'running', 7, null, null,
     null, null, null, null, null, 'claude-sonnet-5', null, null, null, null)
) as s(run_id, span_id, parent_span_id, name, step, status, offset_s, duration_ms, error_class,
       tool_name, tool_decision, policy_reason, arguments_digest, result_digest,
       model, tokens_in, tokens_out, cost_usd, cache_hit)
  on s.run_id = r.run_id
where not exists (select 1 from public.run_spans x where x.span_id = s.span_id);
