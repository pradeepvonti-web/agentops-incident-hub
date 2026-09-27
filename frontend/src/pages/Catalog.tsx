import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getCatalog, listPeople, updateService } from "../lib/data";
import { useAsync } from "../lib/useAsync";
import { PersonSelect } from "../components/forms";
import {
  AvatarGroup,
  Card,
  Empty,
  ErrorNote,
  PageHeader,
  Pill
} from "../components/ui";
import type { Person } from "../types";

const TIERS = ["Tier 1", "Tier 2", "Tier 3"];

export function Catalog() {
  const [refresh, setRefresh] = useState(0);
  const [people, setPeople] = useState<Person[]>([]);
  const [busy, setBusy] = useState("");
  const { data, loading, error } = useAsync(getCatalog, [refresh]);

  useEffect(() => {
    listPeople().then(setPeople).catch(() => setPeople([]));
  }, []);

  async function run(id: string, fn: () => Promise<unknown>) {
    setBusy(id);
    try {
      await fn();
      setRefresh(n => n + 1);
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "Could not save");
    } finally {
      setBusy("");
    }
  }

  return (
    <>
      <PageHeader
        icon="▣"
        title="Catalog"
        actions={<span className="cardNote">Services, owners, escalation paths</span>}
      />
      <div className="pageBody">
        {error && <ErrorNote message={error} />}
        {loading && !data && <Empty>Loading…</Empty>}

        {data && (
          <>
            <Card
              title="Services"
              note="Every service an incident can be filed against. Owner and tier are editable."
              tight
            >
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Service</th>
                      <th>Team</th>
                      <th>Tier</th>
                      <th>Owner</th>
                      <th>Escalation path</th>
                      <th>Open incidents</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.services.map(s => (
                      <tr key={s.id}>
                        <td>
                          <div className="title">{s.name}</div>
                          <div className="sub mono">{s.slug}</div>
                        </td>
                        <td>{s.team?.name ?? "—"}</td>
                        <td>
                          <select
                            className="select"
                            value={s.tier}
                            disabled={busy === s.id}
                            onChange={e =>
                              run(s.id, () => updateService(s.id, { tier: e.target.value }))
                            }
                          >
                            {TIERS.map(t => (
                              <option key={t} value={t}>
                                {t}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td>
                          <PersonSelect
                            value={s.owner?.id ?? null}
                            people={people}
                            onChange={id => run(s.id, () => updateService(s.id, { owner_id: id }))}
                          />
                        </td>
                        <td className="sub">{s.escalation_path?.name ?? "—"}</td>
                        <td>
                          {s.open_incidents ? (
                            <Link to={`/incidents?service=${s.slug}`}>
                              <Pill tone="open">{s.open_incidents} open</Pill>
                            </Link>
                          ) : (
                            <Pill tone="done">None</Pill>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>

            <Card title="Teams" note="Who owns what">
              <div className="grid cols3">
                {data.teams.map(t => (
                  <div key={t.id} className="flowCard">
                    <div className="row" style={{ marginBottom: 8 }}>
                      <h3>{t.name}</h3>
                      <span className="spacer" style={{ marginLeft: "auto" }}>
                        <AvatarGroup names={t.members.map(m => m.full_name)} />
                      </span>
                    </div>
                    <p className="cardNote mono">{t.slack_channel}</p>
                    <p className="cardNote" style={{ marginTop: 6 }}>
                      {t.services.join(", ") || "No services yet"}
                    </p>
                  </div>
                ))}
              </div>
            </Card>
          </>
        )}
      </div>
    </>
  );
}
