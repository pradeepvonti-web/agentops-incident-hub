import json, sys
from common import load_incident

incident = load_incident(sys.argv[1])
events = [x for x in incident["logs"] if x["level"] in {"ERROR", "CRITICAL"}]
print(json.dumps(events, indent=2))
