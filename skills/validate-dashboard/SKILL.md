# Skill: validate-dashboard

1. Read `evals/dashboard-eval.md`.
2. Start the backend (`cd backend && uvicorn app.main:app --port 8000`) and the
   frontend (`cd frontend && npm run dev`) if they are not already running.
3. Open the app with a browser-capable tool.
4. Execute each check in the eval, section by section.
5. Inspect console and network failures; ignore Vite HMR websocket noise.
6. Capture evidence into `screenshots/`.
7. If a check fails, fix the smallest relevant implementation and rerun it.
8. Produce a short validation report listing each section and what failed.
