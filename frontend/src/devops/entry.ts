// Mirrors aidevops/packages/adp-contracts/src/adp_contracts/entry.py.
//
// Duplicated deliberately: the shell renders the entry layer on first paint,
// before any session exists, so it cannot wait on /v1/entry/points. The
// duplication is held honest by test_entry_points.py::test_typescript_mirror_matches_python,
// which parses this literal and diffs it against the Python one -- a drifted label
// fails CI rather than shipping two names for the same door.

export type EntrySource =
  | "portal"
  | "databricks"
  | "vs-code"
  | "power-bi"
  | "teams"
  | "api-cli";

export interface EntryPointSpec {
  source: EntrySource;
  label: string;
  caption: string;
  /** False for API/CLI: automation arrives here, no human drives it. */
  interactive: boolean;
}

/** The six front doors, in diagram order. */
export const ENTRY_POINTS: readonly EntryPointSpec[] = [
  { source: "portal", label: "AI DevOps Portal", caption: "Single front door", interactive: true },
  { source: "databricks", label: "Databricks", caption: "Notebooks & Apps", interactive: true },
  { source: "vs-code", label: "VS Code", caption: "Development", interactive: true },
  { source: "power-bi", label: "Power BI", caption: "Analytics & BI", interactive: true },
  { source: "teams", label: "Microsoft Teams", caption: "Collaboration", interactive: true },
  { source: "api-cli", label: "APIs / CLI", caption: "Automation", interactive: false }
] as const;

export const ENTRY_POINTS_BY_SOURCE: Record<EntrySource, EntryPointSpec> = Object.fromEntries(
  ENTRY_POINTS.map(p => [p.source, p])
) as Record<EntrySource, EntryPointSpec>;

/** Source hues identify a door, not a status. The one place a non-semantic colour is allowed. */
export const SOURCE_HUES: Record<EntrySource, string> = {
  portal: "#1f8a4c",
  databricks: "#f25533",
  "vs-code": "#0f7bc4",
  "power-bi": "#e3a008",
  teams: "#5059c9",
  "api-cli": "#55525a"
};
