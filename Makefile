.PHONY: backend frontend test build triage db-types

backend:
	cd backend && uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

test:
	cd backend && pytest

build:
	cd frontend && npm run build

triage:
	python scripts/triage_pipeline.py INC-1042

# Requires the Supabase CLI and a linked project.
db-types:
	supabase gen types typescript --schema agentops > frontend/src/database.types.ts
