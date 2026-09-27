# Skill: triage-incident

Parameter: `incident_id`

1. Confirm the incident exists.
2. Retrieve incident data.
3. Run `python scripts/triage_pipeline.py <incident_id>`.
4. Read the generated report.
5. Validate it against `docs/INCIDENT_RULES.md`.
6. Do not invent evidence or categories.
7. Return the report path and any validation failures.
