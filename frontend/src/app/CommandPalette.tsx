import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listIncidents } from "../lib/data";
import type { IncidentRow } from "../types";
import { NAV } from "./AppShell";

type Item = { group: string; label: string; hint?: string; to: string };

export function CommandPalette({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const [incidents, setIncidents] = useState<IncidentRow[]>([]);

  useEffect(() => {
    inputRef.current?.focus();
    listIncidents().then(setIncidents).catch(() => setIncidents([]));
  }, []);

  const items = useMemo<Item[]>(() => {
    const needle = query.trim().toLowerCase();
    const pages: Item[] = NAV.map(n => ({
      group: "Go to",
      label: n.label,
      to: n.to
    }));
    const incidentItems: Item[] = incidents.map(x => ({
      group: "Incidents",
      label: `${x.reference} ${x.title}`,
      hint: `${x.severity} · ${x.status}`,
      to: `/incidents/${x.reference}`
    }));
    const all = [...pages, ...incidentItems];
    if (!needle) return all.slice(0, 12);
    return all.filter(i => i.label.toLowerCase().includes(needle)).slice(0, 12);
  }, [query, incidents]);

  useEffect(() => setCursor(0), [query]);

  function go(item: Item | undefined) {
    if (!item) return;
    navigate(item.to);
    onClose();
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") return onClose();
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setCursor(c => Math.min(c + 1, items.length - 1));
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setCursor(c => Math.max(c - 1, 0));
    }
    if (e.key === "Enter") {
      e.preventDefault();
      go(items[cursor]);
    }
  }

  let lastGroup = "";

  return (
    <div className="paletteScrim" onClick={onClose}>
      <div className="palette" onClick={e => e.stopPropagation()}>
        <input
          ref={inputRef}
          value={query}
          placeholder="Search incidents or jump to a page…"
          onChange={e => setQuery(e.target.value)}
          onKeyDown={onKeyDown}
        />
        <div className="paletteList">
          {!items.length && <div className="empty">No matches.</div>}
          {items.map((item, i) => {
            const header = item.group !== lastGroup ? item.group : null;
            lastGroup = item.group;
            return (
              <div key={`${item.to}-${i}`}>
                {header && <div className="paletteGroup">{header}</div>}
                <button
                  className={`paletteItem${i === cursor ? " active" : ""}`}
                  onMouseEnter={() => setCursor(i)}
                  onClick={() => go(item)}
                >
                  <span>{item.label}</span>
                  {item.hint && <span className="hint">{item.hint}</span>}
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
