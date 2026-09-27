import json, sys
from collections import Counter
from common import load_incident

x = load_incident(sys.argv[1])
print(json.dumps({
    "incident_id": x["id"],
    "service": x["service"],
    "severity_counts": Counter(e["level"] for e in x["logs"])
}, indent=2))
