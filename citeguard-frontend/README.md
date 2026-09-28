# CiteGuard React frontend

The active UI uses React 19, TypeScript, Tailwind CSS 4, and Vite 8. Use Node.js 22.12+.

From the repository root:

```sh
npm ci --prefix citeguard-frontend
npm run dev --prefix citeguard-frontend
npm run lint --prefix citeguard-frontend
npm run build --prefix citeguard-frontend
```

Run `uvicorn app.main:app --reload` in an activated Python environment for the API. Vite proxies `/api` to port 8000; production builds are served by FastAPI from `citeguard-frontend/dist`.

`ClaimCard` provides accessible animated explanations and shared-term highlighting. `DocumentSummary` renders the score gauge and enriched cited-reference badges. `Toast` displays global analysis notifications, and `ReportSkeleton` renders while analysis runs. Reduced-motion preferences are respected.

See the [master README](../README.md) for setup, optional Crossref/Groq services, API documentation, evaluation, and limitations. Backend secrets belong only in the repository-root `.env`, never in frontend variables or assets.
