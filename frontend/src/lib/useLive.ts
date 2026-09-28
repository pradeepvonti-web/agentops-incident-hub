import { useEffect, useId, useState } from "react";
import { supabase } from "./supabase";

const SCHEMA = import.meta.env.VITE_SUPABASE_SCHEMA ?? "agentops";

/**
 * Returns a counter that increments whenever the given table changes.
 * Pass it into a `useAsync` dependency list to refetch on every write,
 * from this tab or anyone else's.
 *
 * Every subscriber gets its own channel. supabase-js returns the existing
 * channel for a repeated topic name, and adding a `postgres_changes` callback
 * to a channel that has already subscribed throws -- which is what happened
 * when the shell and a page both watched `alerts`. The React id makes the
 * topic unique per mounted hook.
 */
export function useLiveTable(table: string, filter?: string): number {
  const [tick, setTick] = useState(0);
  const id = useId();

  useEffect(() => {
    const channel = supabase
      .channel(`live:${table}:${filter ?? "all"}:${id}`)
      .on(
        "postgres_changes",
        { event: "*", schema: SCHEMA, table, ...(filter ? { filter } : {}) },
        () => setTick(n => n + 1)
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [table, filter, id]);

  return tick;
}

/** Watches several tables at once; any change bumps the counter. */
export function useLiveTables(tables: string[]): number {
  const [tick, setTick] = useState(0);
  const id = useId();
  const key = tables.join(",");

  useEffect(() => {
    const channel = supabase.channel(`live-multi:${key}:${id}`);
    for (const table of key.split(",")) {
      channel.on("postgres_changes", { event: "*", schema: SCHEMA, table }, () =>
        setTick(n => n + 1)
      );
    }
    channel.subscribe();
    return () => {
      supabase.removeChannel(channel);
    };
  }, [key, id]);

  return tick;
}
