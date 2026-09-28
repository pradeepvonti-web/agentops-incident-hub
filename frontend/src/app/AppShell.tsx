import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { getAlerts, getBoard } from "../lib/data";
import { getRunStats } from "../lib/controlPlane";
import { useLiveTable } from "../lib/useLive";
import { usePoll } from "../devops/usePoll";
import { useAuth } from "./AuthProvider";
import { CommandPalette } from "./CommandPalette";
import { DeclareIncidentDialog } from "./DeclareIncidentDialog";
import { Avatar } from "../components/ui";
import { Logo } from "../components/Logo";

type NavItem = { to: string; label: string; color: string; end?: boolean; section?: string };

/**
 * One shell, two products. Incident response is the top group; the AI DevOps
 * control plane (aidevops/) is the second. Both read the same Supabase project
 * and the same session, so a failed agent run shows up under Alerts without
 * anyone switching apps.
 */
export const NAV: NavItem[] = [
  { to: "/", label: "Home", color: "#6e8cff", end: true },
  { to: "/incidents", label: "Incidents", color: "#e0625b" },
  { to: "/alerts", label: "Alerts", color: "#e0a03c" },
  { to: "/on-call", label: "On-call", color: "#4fb286" },
  { to: "/status-page", label: "Status page", color: "#7c9cf5" },
  { to: "/post-incident", label: "Post-incident", color: "#c084d8" },
  { to: "/insights", label: "Insights", color: "#57b5c9" },
  { to: "/catalog", label: "Catalog", color: "#8fa0b8" },
  { to: "/workflows", label: "Workflows", color: "#d08a5e" },
  { to: "/devops", label: "AI DevOps", color: "#1f8a4c", end: true, section: "AI DevOps" },
  { to: "/devops/runs", label: "Runs", color: "#3aa76d", section: "AI DevOps" },
  { to: "/devops/approvals", label: "Approvals", color: "#f25533", section: "AI DevOps" },
  { to: "/devops/entry-points", label: "Entry points", color: "#8fa0b8", section: "AI DevOps" }
];

export function AppShell() {
  const navigate = useNavigate();
  const { profile, signOut } = useAuth();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [declareOpen, setDeclareOpen] = useState(false);
  const [activeCount, setActiveCount] = useState<number | null>(null);
  const [openAlerts, setOpenAlerts] = useState<number | null>(null);
  const [awaitingRuns, setAwaitingRuns] = useState<number | null>(null);

  // The sidebar counters are the one thing on screen everywhere, so they follow
  // the database rather than whatever page happened to load them.
  const incidentTick = useLiveTable("incidents");
  const alertTick = useLiveTable("alerts");
  // The control plane has no realtime channel, so its counter polls. When the
  // control plane is down the counter simply stays hidden; the pages say why.
  const runTick = usePoll(20000);

  useEffect(() => {
    getBoard()
      .then(b => setActiveCount(b.active_count))
      .catch(() => setActiveCount(null));
  }, [incidentTick]);

  useEffect(() => {
    getAlerts()
      .then(a => setOpenAlerts(a.recent.filter(x => x.status === "Open").length))
      .catch(() => setOpenAlerts(null));
  }, [alertTick]);

  useEffect(() => {
    getRunStats()
      .then(s => setAwaitingRuns(s.by_status.awaiting_approval ?? 0))
      .catch(() => setAwaitingRuns(null));
  }, [runTick]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen(open => !open);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="shell">
      <nav className="sidebar">
        <div className="brand">
          <Logo tone="light" size={20} />
          <span className="env">Production workspace</span>
        </div>

        <button className="searchTrigger" onClick={() => setPaletteOpen(true)}>
          <span>Search or jump to…</span>
          <kbd>⌘K</kbd>
        </button>

        <button className="btn primary declareBtn" onClick={() => setDeclareOpen(true)}>
          Declare incident
        </button>

        <div className="nav">
          {NAV.map((item, i) => (
            <div key={item.to}>
              {item.section && NAV[i - 1]?.section !== item.section && (
                <div className="navLabel">{item.section}</div>
              )}
              <NavLink
                to={item.to}
                end={item.end}
                className={({ isActive }) => (isActive ? "active" : undefined)}
              >
                <span className="dot" style={{ background: item.color }} />
                {item.label}
                {item.label === "Incidents" && activeCount !== null && (
                  <span className="count">{activeCount}</span>
                )}
                {item.label === "Alerts" && !!openAlerts && (
                  <span className="count">{openAlerts}</span>
                )}
                {item.label === "Approvals" && !!awaitingRuns && (
                  <span className="count">{awaitingRuns}</span>
                )}
              </NavLink>
            </div>
          ))}
        </div>

        <div className="sidebarFoot">
          {profile ? (
            <div className="row">
              <Avatar name={profile.full_name} />
              <div style={{ minWidth: 0 }}>
                <strong>{profile.full_name}</strong>
                <span className="ellipsis">{profile.job_title ?? profile.email}</span>
              </div>
              <button
                className="linkButton spacer"
                style={{ marginLeft: "auto" }}
                onClick={() => signOut()}
              >
                Sign out
              </button>
            </div>
          ) : (
            <span>Loading profile…</span>
          )}
        </div>
      </nav>

      <main className="stage">
        <div className="panel">
          <Outlet />
        </div>
      </main>

      {paletteOpen && <CommandPalette onClose={() => setPaletteOpen(false)} />}
      {declareOpen && (
        <DeclareIncidentDialog
          onClose={() => setDeclareOpen(false)}
          onDeclared={reference => {
            setDeclareOpen(false);
            navigate(`/incidents/${reference}`);
          }}
        />
      )}
    </div>
  );
}
