import { useNavigate } from "react-router-dom";
import type { IncidentRow } from "../types";
import { SeverityBadge } from "./SeverityBadge";
import { StatusPill } from "./StatusPill";
import { Avatar, Empty } from "./ui";
import { dateTime } from "../lib/format";

export function IncidentTable({ incidents }: { incidents: IncidentRow[] }) {
  const navigate = useNavigate();
  if (!incidents.length) return <Empty>No incidents match these filters.</Empty>;

  return (
    <div className="tableWrap">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Incident</th>
            <th>Service</th>
            <th>Category</th>
            <th>Severity</th>
            <th>Status</th>
            <th>Lead</th>
            <th>Latest</th>
          </tr>
        </thead>
        <tbody>
          {incidents.map(x => (
            <tr
              key={x.id}
              className="clickable"
              onClick={() => navigate(`/incidents/${x.reference}`)}
            >
              <td className="mono">{x.reference}</td>
              <td className="incidentCell">
                <div className="title">{x.title}</div>
                <div className="sub">{x.summary}</div>
              </td>
              <td className="mono">{x.service_slug ?? "—"}</td>
              <td>{x.category}</td>
              <td>
                <SeverityBadge severity={x.severity} />
              </td>
              <td>
                <StatusPill status={x.status} />
              </td>
              <td>
                <span className="row">
                  <Avatar name={x.lead_name ?? "Unassigned"} />
                  <span className="sub">{x.lead_name ?? "Unassigned"}</span>
                </span>
              </td>
              <td className="sub">{dateTime(x.latest_occurrence ?? x.updated_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
