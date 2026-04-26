# Unflooders – Next.js 15

MapLibre-based flood risk mapper for Netherlands agriculture, built with Next.js App Router.

## Current implementation

- UI and map are rendered in Next.js (`app/page.tsx`) with a client MapLibre component.
- Farm parcels and historic risk zones come from SQLite via `/api/snapshot`.
- Forecast layer is loaded from `public/data/flood-forecast.geojson`.
- Flood/pollution scores are computed in `lib/geo.ts` and used to color fields.
- Large datasets automatically switch to point rendering mode in `components/Map.tsx` for performance.

## Tech stack

- Next.js 15 (App Router) + React 19 + TypeScript (strict)
- MapLibre GL JS 5.x
- Tailwind CSS
- Zustand (layer visibility state)
- TanStack Query (data fetching/cache)
- Turf (geo helpers)
- Jest + Playwright scaffolding

## Project structure

```text
app/
  layout.tsx
  page.tsx
  globals.css
  api/
    snapshot/route.ts

components/
  Map.tsx
  LayerControls.tsx
  Legend.tsx
  TimeSlider.tsx
  RiskScoreCard.tsx
  FarmPopup.tsx

lib/
  geo.ts
  pdok.ts
  store.ts
  pdf.tsx

public/data/
  brp-limburg-simplified.geojson
  flood-historic.geojson
  flood-current.geojson
  flood-forecast.geojson

scripts/
  sqlite_snapshot_json.py
  download_nl_data.py

tests/
  unit/geo.test.ts
  e2e/map.spec.ts

types/
  index.ts
```

## Run locally

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Verify

```bash
npm run lint
npm run test
npm run build
```
