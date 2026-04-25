# Limburg FloodFarm Risk Mapper (MaasGuard) – Next.js 15

Production-style Next.js 15 rewrite of the original Streamlit/Folium prototype.

## Stack

- Next.js 15 (App Router) + React 19 + TypeScript strict
- MapLibre GL JS 5.x
- Tailwind CSS
- Zustand for UI/map state
- TanStack Query for data loading cache
- Turf for score/spatial utilities
- React PDF renderer for farm report export

## Project structure

```text
app/
  layout.tsx
  page.tsx
  globals.css
components/
  Map.tsx
  LayerControls.tsx
  TimeSlider.tsx
  Legend.tsx
  RiskScoreCard.tsx
  FarmPopup.tsx
lib/
  geo.ts
  pdok.ts
  pdf.tsx
  store.ts
public/data/
  flood-historic.geojson
  flood-current.geojson
  flood-forecast.geojson
scripts/
  sqlite_snapshot_json.py
tests/
  unit/geo.test.ts
  e2e/map.spec.ts
```

## Run locally

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Build and quality checks

```bash
npm run lint
npm run test
npm run build
```

## Notes

- Farms and historic risk zones are now loaded from `data/floodfarm_nl.sqlite` via `/api/snapshot`.
- Current and forecast masks still come from `public/data/flood-current.geojson` and `public/data/flood-forecast.geojson`.
- If the SQLite file changes, the API refreshes every ~5 minutes (in-memory cache TTL).
- Map component is GPU-accelerated and ready for larger datasets with simplification/tile strategy.
