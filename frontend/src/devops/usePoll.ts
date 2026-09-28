import { useEffect, useState } from "react";

/**
 * A tick that advances every `ms`. The control plane has no realtime channel --
 * its tables are not readable from the browser by design -- so its screens poll
 * instead of subscribing. Pair with `useAsync(fn, [tick])`.
 */
export function usePoll(ms = 15000): number {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setTick(n => n + 1), ms);
    return () => window.clearInterval(id);
  }, [ms]);
  return tick;
}
