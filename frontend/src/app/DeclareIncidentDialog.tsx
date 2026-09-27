import { useEffect, useState } from "react";
import { declareIncident, listServiceOptions } from "../lib/data";
import { CATEGORIES, LIFECYCLE, SEVERITIES, type Category, type Severity, type Status } from "../types";
import { Field, FormError, Modal, useSubmit } from "../components/forms";

export function DeclareIncidentDialog({
  onClose,
  onDeclared
}: {
  onClose: () => void;
  onDeclared: (reference: string) => void;
}) {
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [severity, setSeverity] = useState<Severity>("ERROR");
  const [category, setCategory] = useState<Category>("Availability");
  const [status, setStatus] = useState<Status>("Triage");
  const [serviceId, setServiceId] = useState("");
  const [services, setServices] = useState<{ id: string; name: string }[]>([]);

  useEffect(() => {
    listServiceOptions().then(setServices).catch(() => setServices([]));
  }, []);

  const { onSubmit, pending, error } = useSubmit(async () => {
    const incident = await declareIncident({
      title,
      summary,
      severity,
      category,
      status,
      serviceId: serviceId || null
    });
    onDeclared(incident.reference);
  });

  return (
    <Modal title="Declare an incident" onClose={onClose} wide>
      <form onSubmit={onSubmit}>
        <FormError message={error} />

        <Field label="What is happening?">
          <input
            className="input"
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="Checkout API returning 500s"
            autoFocus
            required
          />
        </Field>

        <Field label="Summary" hint="One or two sentences the whole response team will read first.">
          <textarea
            className="input"
            rows={3}
            value={summary}
            onChange={e => setSummary(e.target.value)}
            placeholder="Customers cannot complete checkout. Errors started after the 17:50 deploy."
          />
        </Field>

        <div className="grid cols2">
          <Field label="Severity">
            <select
              className="select"
              value={severity}
              onChange={e => setSeverity(e.target.value as Severity)}
            >
              {SEVERITIES.map(s => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Category">
            <select
              className="select"
              value={category}
              onChange={e => setCategory(e.target.value as Category)}
            >
              {CATEGORIES.map(c => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Affected service">
            <select className="select" value={serviceId} onChange={e => setServiceId(e.target.value)}>
              <option value="">Not sure yet</option>
              {services.map(s => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Starting status">
            <select
              className="select"
              value={status}
              onChange={e => setStatus(e.target.value as Status)}
            >
              {LIFECYCLE.filter(s => s !== "Closed").map(s => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <div className="row" style={{ marginTop: 16 }}>
          <button className="btn primary" disabled={pending || !title.trim()}>
            {pending ? "Declaring…" : "Declare incident"}
          </button>
          <button type="button" className="btn ghost" onClick={onClose}>
            Cancel
          </button>
          <span className="cardNote spacer" style={{ marginLeft: "auto" }}>
            You become the lead and reporter.
          </span>
        </div>
      </form>
    </Modal>
  );
}
