export function time(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit"
  });
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString([], {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit"
  });
}

export function day(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString([], {
    weekday: "long",
    day: "numeric",
    month: "long"
  });
}

export function minutes(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (value < 60) return `${Math.round(value)}m`;
  const h = Math.floor(value / 60);
  const m = Math.round(value % 60);
  return m ? `${h}h ${m}m` : `${h}h`;
}

/** Elapsed time between two instants, or from `from` until now when `to` is null. */
export function duration(from: string | null, to: string | null): string {
  if (!from) return "—";
  const start = new Date(from).getTime();
  const end = to ? new Date(to).getTime() : Date.now();
  return minutes(Math.max(0, (end - start) / 60000));
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map(part => part[0]?.toUpperCase() ?? "")
    .join("");
}
