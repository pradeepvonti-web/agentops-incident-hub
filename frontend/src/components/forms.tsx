import { useEffect, useState, type FormEvent, type ReactNode } from "react";

export function Modal({
  title,
  onClose,
  children,
  wide
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="paletteScrim" onClick={onClose}>
      <div
        className="palette"
        style={{ width: wide ? "min(720px, 94vw)" : "min(520px, 94vw)" }}
        onClick={e => e.stopPropagation()}
      >
        <div className="cardHead">
          <h2>{title}</h2>
          <button className="btn ghost spacer" style={{ marginLeft: "auto" }} onClick={onClose}>
            Close
          </button>
        </div>
        <div style={{ padding: 18 }}>{children}</div>
      </div>
    </div>
  );
}

export function Field({
  label,
  hint,
  children
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span className="fieldLabel">{label}</span>
      {children}
      {hint && <span className="cardNote">{hint}</span>}
    </label>
  );
}

/** Wraps a submit handler with pending and error state so forms behave consistently. */
export function useSubmit(action: () => Promise<void>, onDone?: () => void) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setPending(true);
    setError("");
    try {
      await action();
      onDone?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setPending(false);
    }
  }

  return { onSubmit, pending, error };
}

export function FormError({ message }: { message: string }) {
  if (!message) return null;
  return (
    <div className="error" style={{ marginBottom: 12 }}>
      {message}
    </div>
  );
}

export function PersonSelect({
  value,
  onChange,
  people,
  allowUnassigned = true
}: {
  value: string | null;
  onChange: (id: string | null) => void;
  people: { id: string; full_name: string }[];
  allowUnassigned?: boolean;
}) {
  return (
    <select
      className="select"
      value={value ?? ""}
      onChange={e => onChange(e.target.value || null)}
    >
      {allowUnassigned && <option value="">Unassigned</option>}
      {people.map(p => (
        <option key={p.id} value={p.id}>
          {p.full_name}
        </option>
      ))}
    </select>
  );
}
