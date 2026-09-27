import { useEffect, useState } from "react";
import { supabase } from "./supabase";

const SCHEMA = import.meta.env.VITE_SUPABASE_SCHEMA ?? "agentops";

/**
 * Returns a counter that increments whenever the given table changes.
 * Pass it into a `useAsync` dependency list to refetch on every write,
 * from this tab or anyone else's.
 */
export function useLiveTable(table: string, filter?: string): number {
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const channel = supabase
      .channel(`live:${table}:${filter ?? "all"}`)
      .on(
        "postgres_changes",
        { event: "*", schema: SCHEMA, table, ...(filter ? { filter } : {}) },
        () => setTick(n => n + 1)
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [table, filter]);

  return tick;
}

/** Watches several tables at once; any change bumps the counter. */
export function useLiveTables(tables: string[]): number {
  const [tick, setTick] = useState(0);
  const key = tables.join(",");

  useEffect(() => {
    const channel = supabase.channel(`live-multi:${key}`);
    for (const table of key.split(",")) {
      channel.on("postgres_changes", { event: "*", schema: SCHEMA, table }, () =>
        setTick(n => n + 1)
      );
    }
    channel.subscribe();
    return () => {
      supabase.removeChannel(channel);
    };
  }, [key]);

  return tick;
}
