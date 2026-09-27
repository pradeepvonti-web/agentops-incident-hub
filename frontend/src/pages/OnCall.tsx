import { useEffect, useState } from "react";
import { addShiftOverride, getOnCall, listPeople } from "../lib/data";
import { useAsync } from "../lib/useAsync";
import { dateTime } from "../lib/format";
import { Field, FormError, Modal, PersonSelect, useSubmit } from "../components/forms";
import { Card, Empty, ErrorNote, PageHeader, Person, Pill } from "../components/ui";
import type { Person as PersonType, Schedule } from "../types";

function currentShift(schedule: Schedule, at = Date.now()) {
  return [...schedule.shifts]
    .filter(s => new Date(s.starts_at).getTime() <= at && new Date(s.ends_at).getTime() > at)
    .sort((a, b) => Number(b.is_override) - Number(a.is_override))[0];
}

function nextShift(schedule: Schedule, at = Date.now()) {
  return schedule.shifts.find(s => new Date(s.starts_at).getTime() > at);
}

export function OnCall() {
  const [refresh, setRefresh] = useState(0);
  const [people, setPeople] = useState<PersonType[]>([]);
  const [overriding, setOverriding] = useState<Schedule | null>(null);
  const { data, loading, error } = useAsync(getOnCall, [refresh]);

  useEffect(() => {
    listPeople().then(setPeople).catch(() => setPeople([]));
  }, []);

  return (
    <>
      <PageHeader icon="◔" title="On-call" />
      <div className="pageBody">
        {error && <ErrorNote message={error} />}
        {loading && !data && <Empty>Loading…</Empty>}

        {data && (
          <>
            <Card title="Schedules" note="Who is on call right now" tight>
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Schedule</th>
                      <th>On call now</th>
                      <th>Until</th>
                      <th>Up next</th>
                      <th>Rotation</th>
                      <th>Timezone</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {data.schedules.map(s => {
                      const now = currentShift(s);
                      const next = nextShift(s);
                      return (
                        <tr key={s.id}>
                          <td className="title">{s.name}</td>
                          <td>
                            {now ? (
                              <span className="row">
                                <Person name={now.user.full_name} />
                                {now.is_override && <Pill tone="open">override</Pill>}
                              </span>
                            ) : (
                              <span className="sub">Nobody scheduled</span>
                            )}
                          </td>
                          <td className="sub">{now ? dateTime(now.ends_at) : "—"}</td>
                          <td>{next ? <Person name={next.user.full_name} /> : <span className="sub">—</span>}</td>
                          <td className="sub">{s.rotation ?? "—"}</td>
                          <td className="sub mono">{s.timezone}</td>
                          <td>
                            <button className="btn ghost" onClick={() => setOverriding(s)}>
                              Add override
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Card>

            <div className="grid cols2">
              <Card title="Upcoming shifts" note="Next handovers per schedule">
                {data.schedules.map(s => (
                  <div key={s.id} style={{ marginBottom: 14 }}>
                    <h3>{s.name}</h3>
                    {s.shifts.slice(0, 5).map(shift => (
                      <div className="railRow" key={shift.id}>
                        <span className="row">
                          <Person name={shift.user.full_name} />
                          {shift.is_override && <Pill tone="open">override</Pill>}
                        </span>
                        <span className="cardNote">
                          {dateTime(shift.starts_at)} → {dateTime(shift.ends_at)}
                        </span>
                      </div>
                    ))}
                  </div>
                ))}
              </Card>

              <Card title="Escalation paths" note="Who gets paged, and when">
                {data.escalation_paths.map(p => (
                  <div key={p.id} style={{ marginBottom: 14 }}>
                    <h3>{p.name}</h3>
                    {p.levels.map(level => (
                      <div className="railRow" key={level.id}>
                        <span className="row">
                          <Pill>Level {level.level}</Pill>
                          <span>{level.notify}</span>
                        </span>
                        <span className="cardNote">
                          {level.after_minutes === 0
                            ? "immediately"
                            : `after ${level.after_minutes}m`}{" "}
                          · {level.method}
                        </span>
                      </div>
                    ))}
                  </div>
                ))}
              </Card>
            </div>
          </>
        )}
      </div>

      {overriding && (
        <OverrideDialog
          schedule={overriding}
          people={people}
          onClose={() => setOverriding(null)}
          onDone={() => {
            setOverriding(null);
            setRefresh(n => n + 1);
          }}
        />
      )}
    </>
  );
}

function OverrideDialog({
  schedule,
  people,
  onClose,
  onDone
}: {
  schedule: Schedule;
  people: PersonType[];
  onClose: () => void;
  onDone: () => void;
}) {
  const now = new Date();
  const later = new Date(now.getTime() + 4 * 60 * 60 * 1000);
  const local = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);

  const [userId, setUserId] = useState<string | null>(people[0]?.id ?? null);
  const [startsAt, setStartsAt] = useState(local(now));
  const [endsAt, setEndsAt] = useState(local(later));

  const { onSubmit, pending, error } = useSubmit(async () => {
    if (!userId) throw new Error("Pick who is covering");
    await addShiftOverride({
      scheduleId: schedule.id,
      userId,
      startsAt: new Date(startsAt).toISOString(),
      endsAt: new Date(endsAt).toISOString()
    });
  }, onDone);

  return (
    <Modal title={`Override ${schedule.name}`} onClose={onClose}>
      <form onSubmit={onSubmit}>
        <FormError message={error} />
        <p className="cardNote" style={{ marginBottom: 12 }}>
          An override takes precedence over the rotation for the window you choose.
        </p>
        <Field label="Who is covering?">
          <PersonSelect
            value={userId}
            onChange={setUserId}
            people={people}
            allowUnassigned={false}
          />
        </Field>
        <div className="grid cols2">
          <Field label="From">
            <input
              className="input"
              type="datetime-local"
              value={startsAt}
              onChange={e => setStartsAt(e.target.value)}
            />
          </Field>
          <Field label="Until">
            <input
              className="input"
              type="datetime-local"
              value={endsAt}
              onChange={e => setEndsAt(e.target.value)}
            />
          </Field>
        </div>
        <button className="btn primary" style={{ marginTop: 12 }} disabled={pending}>
          {pending ? "Saving…" : "Add override"}
        </button>
      </form>
    </Modal>
  );
}
