import type { ReactNode } from "react";
import { initials } from "../lib/format";

export function Avatar({ name }: { name: string }) {
  return (
    <span className="avatar" title={name}>
      {initials(name)}
    </span>
  );
}

export function AvatarGroup({ names }: { names: string[] }) {
  return (
    <span className="avatars">
      {names.slice(0, 4).map(n => (
        <Avatar key={n} name={n} />
      ))}
    </span>
  );
}

export function Person({ name }: { name: string }) {
  return (
    <span className="row">
      <Avatar name={name} />
      <span>{name}</span>
    </span>
  );
}

export function Pill({
  children,
  tone = "neutral"
}: {
  children: ReactNode;
  tone?: "neutral" | "open" | "done" | "closed";
}) {
  return <span className={`pill ${tone}`}>{children}</span>;
}

export function PageHeader({
  icon,
  eyebrow,
  title,
  actions
}: {
  icon: string;
  eyebrow?: ReactNode;
  title: string;
  actions?: ReactNode;
}) {
  return (
    <header className="pageHead">
      <span className="icon" aria-hidden="true">
        {icon}
      </span>
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
      </div>
      {actions && <div className="spacer row">{actions}</div>}
    </header>
  );
}

export function Card({
  title,
  note,
  actions,
  children,
  tight
}: {
  title?: string;
  note?: string;
  actions?: ReactNode;
  children: ReactNode;
  tight?: boolean;
}) {
  if (!title) return <div className={`card${tight ? " tight" : ""}`}>{children}</div>;
  return (
    <section className={`card${tight ? " tight" : ""}`}>
      <div className={tight ? "cardHead" : "row"} style={tight ? undefined : { marginBottom: 12 }}>
        <div>
          <h2>{title}</h2>
          {note && <p className="cardNote">{note}</p>}
        </div>
        {actions && <div className="spacer row">{actions}</div>}
      </div>
      {tight ? children : <div>{children}</div>}
    </section>
  );
}

export function Metric({
  label,
  value,
  foot
}: {
  label: string;
  value: ReactNode;
  foot?: string;
}) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      {foot && <div className="foot">{foot}</div>}
    </div>
  );
}

export function BarList({
  rows,
  emptyLabel = "Nothing to show"
}: {
  rows: { name: string; count: number }[];
  emptyLabel?: string;
}) {
  const max = Math.max(1, ...rows.map(r => r.count));
  if (!rows.length) return <div className="empty">{emptyLabel}</div>;
  return (
    <div>
      {rows.map(row => (
        <div className="barRow" key={row.name}>
          <span>{row.name}</span>
          <span className="barTrack">
            <span
              className="barFill"
              style={{ width: `${Math.round((row.count / max) * 100)}%` }}
            />
          </span>
          <span className="value">{row.count}</span>
        </div>
      ))}
    </div>
  );
}

export function CheckLine({
  done,
  children,
  right,
  onToggle
}: {
  done: boolean;
  children: ReactNode;
  right?: ReactNode;
  onToggle?: () => void;
}) {
  return (
    <div className="checkline">
      {onToggle ? (
        <button
          className={`check${done ? " on" : ""}`}
          onClick={onToggle}
          aria-pressed={done}
          aria-label={done ? "Mark as open" : "Mark as done"}
        >
          ✓
        </button>
      ) : (
        <span className={`check${done ? " on" : ""}`}>✓</span>
      )}
      <span className={done ? "strike" : undefined}>{children}</span>
      {right && <span className="spacer" style={{ marginLeft: "auto" }}>{right}</span>}
    </div>
  );
}

export function Progress({ done, total }: { done: number; total: number }) {
  const pct = total ? Math.round((done / total) * 100) : 0;
  return (
    <div>
      <div className="progress">
        <div style={{ width: `${pct}%` }} />
      </div>
      <p className="cardNote" style={{ marginTop: 6 }}>
        {done} of {total} complete
      </p>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

export function ErrorNote({ message }: { message: string }) {
  return <div className="error">{message}</div>;
}
