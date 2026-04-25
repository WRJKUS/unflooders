# Netherlands FloodFarm Risk Mapper

Farm-level flood and nutrient mobilization MVP for CASSINI "Space for Water".

## Behavior

- Uses a **local SQLite snapshot** for data loading in the app.
- Loads **Netherlands-wide** farm parcels and flood risk polygons from SQLite at startup.
- Does **not** re-download parcels when you pan or zoom.
- Keeps Copernicus/EFAS layers as live WMS overlays on the map.

## Quickstart

1) Install dependencies

```bash
python3 -m pip install -r requirements.txt
```

2) Build/update the Netherlands SQLite snapshot

```bash
python3 scripts/download_nl_data.py
```

Optional caps for faster snapshot builds:

```bash
python3 scripts/download_nl_data.py --max-farms 50000 --max-risk-zones 20000
```

Use `0` for a full fetch on either cap.

3) Run app

```bash
streamlit run app.py
```

## SQLite snapshot

- File: `data/floodfarm_nl.sqlite`
- Created by: `scripts/download_nl_data.py`
- Tables:
  - `farms`
  - `risk_zones`
  - `discharge_points`
  - `meta`

## Data sources used by the download script

- BRP parcels (PDOK OGC API): `https://api.pdok.nl/rvo/gewaspercelen/ogc/v1`
- Flood risk zones (PDOK RWS): `https://api.pdok.nl/rws/overstromingen-risicogebied/ogc/v1`
- Discharge snapshot (Open-Meteo Flood API, GloFAS-based): `https://flood-api.open-meteo.com/v1/flood`

## Scoring model

- `FloodRisk = 0.5 * flooded_area_pct + 0.3 * soil_saturation + 0.2 * historic_events`
- `PollutionMobilization = FloodRisk * crop_factor * (turbidity_potential / 100)`
