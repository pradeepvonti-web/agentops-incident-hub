import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL;
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;
const schema = import.meta.env.VITE_SUPABASE_SCHEMA ?? "agentops";

if (!url || !key) {
  throw new Error(
    "Missing VITE_SUPABASE_URL or VITE_SUPABASE_PUBLISHABLE_KEY. Copy frontend/.env.example to frontend/.env.local."
  );
}

/**
 * Every table in this app lives in the `agentops` schema, which must be listed
 * under Project Settings → API → Exposed schemas for PostgREST to serve it.
 */
export const supabase = createClient(url, key, {
  db: { schema },
  auth: { persistSession: true, autoRefreshToken: true }
});

export function unwrap<T>(result: { data: T | null; error: { message: string } | null }): T {
  if (result.error) throw new Error(result.error.message);
  if (result.data === null) throw new Error("No data returned");
  return result.data;
}
