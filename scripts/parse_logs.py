import sys
from common import load_incident

incident = load_incident(sys.argv[1])
for event in incident["logs"]:
    print(f"{event['timestamp']} [{event['level']}] {event['message']}")
