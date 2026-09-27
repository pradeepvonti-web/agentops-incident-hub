import sys
from common import ROOT, load_incident

if len(sys.argv) != 2:
    raise SystemExit("Usage: python scripts/triage_pipeline.py <incident-id>")

x = load_incident(sys.argv[1])
evidence = [
    f"- {e['timestamp']} [{e['level']}] {e['message']}"
    for e in x["logs"] if e["level"] in {"ERROR", "CRITICAL"}
]

report = (
    f"# Incident {x['id']} — {x['title']}\n\n"
    "## Executive summary\n\n"
    f"- **Service:** {x['service']}\n"
    f"- **Severity:** {x['severity']}\n"
    f"- **Category:** {x['category']}\n"
    f"- **Status:** {x['status']}\n"
    f"- **First occurrence:** {x['first_occurrence']}\n"
    f"- **Latest occurrence:** {x['latest_occurrence']}\n\n"
    "## Probable cause\n\n"
    f"{x['probable_cause']}\n\n"
    "## Suggested next action\n\n"
    f"{x['suggested_next_action']}\n\n"
    "## Evidence\n\n"
    + ("\n".join(evidence) if evidence else "- No ERROR/CRITICAL evidence")
    + "\n"
)

out = ROOT / "artifacts"
out.mkdir(exist_ok=True)
path = out / f"{x['id']}-report.md"
path.write_text(report, encoding="utf-8")
print(f"Wrote {path}")
