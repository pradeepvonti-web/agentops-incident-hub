import sys
from common import load_incident

KEYWORDS = {
    "Security": ("auth", "unauthorized", "forbidden", "token", "credential"),
    "Performance": ("timeout", "latency", "slow", "saturation"),
    "Availability": ("unavailable", "connection refused", "health check", "outage"),
    "Data": ("schema", "duplicate", "corruption", "malformed"),
    "Integration": ("webhook", "upstream", "downstream", "external api"),
}

incident = load_incident(sys.argv[1])
text = " ".join(x["message"].lower() for x in incident["logs"])
scores = [(sum(k in text for k in keys), category) for category, keys in KEYWORDS.items()]
scores.sort(reverse=True)
print(scores[0][1] if scores and scores[0][0] else incident["category"])
