-- The idempotency constraint was written as UNIQUE NULLS NOT DISTINCT, which
-- treats two NULL keys as equal: only one run per tenant could ever lack a key.
-- Interactive doors (portal, Teams, VS Code) do not send one -- a human's second
-- submission is a second pipeline, not a retry -- so the second portal run in a
-- tenant failed with a duplicate-key error. It did not surface earlier because
-- the seed has exactly one keyless run per tenant.
--
-- The intent, one run per *supplied* key per tenant, is a partial unique index.

alter table public.runs drop constraint runs_tenant_id_idempotency_key_key;

create unique index runs_tenant_idempotency_key
  on public.runs (tenant_id, idempotency_key)
  where idempotency_key is not null;

comment on index public.runs_tenant_idempotency_key is
  'One run per idempotency key per tenant. Runs without a key (interactive doors) are unconstrained; the key is how unattended doors make a retry a no-op.';
