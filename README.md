# unflooders – Next.js 15


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
