# Limburg FloodFarm Risk Mapper

Farm-level MVP for CASSINI "Space for Water" disaster risk monitoring, focused on Limburg (Meuse basin).

## What it does

- Loads BRP farm parcels from PDOK (real data only, no synthetic fallback).
- Shows toggleable layers for:
  - Historic flood risk zones from PDOK RWS
  - Current observed flood extent from Copernicus GFM WMS
  - Forecast outlook from EFAS WMS
- Computes per-farm scores:
  - Flood Risk Score (0-100)
  - Pollution Mobilization Score (0-100)
- Supports time views (Historic / Current / +7d), autoplay animation, and PDF farm risk export.

## Quickstart

```bash
python3 -m pip install -r requirements.txt
streamlit run app.py
```

## Data sources and integration points

- BRP parcels (PDOK):
  - `https://api.pdok.nl/rvo/gewaspercelen/ogc/v1`
  - Legacy WFS fallback: `https://service.pdok.nl/rvo/brpgewaspercelen/wfs/v1_0`
- Historic flood zones (PDOK RWS): `https://api.pdok.nl/rws/overstromingen-risicogebied/ogc/v1`
- Current flood extent layer (Copernicus GFM WMS): `https://geoserver.gfm.eodc.eu/geoserver/gfm/wms`
- Forecast outlook layer (EFAS WMS): `https://european-flood.emergency.copernicus.eu/api/wms/`
- River discharge (Open-Meteo Flood API, based on GloFAS): `https://flood-api.open-meteo.com/v1/flood`

## Scoring model

- `FloodRisk = 0.5 * flooded_area_pct + 0.3 * soil_saturation + 0.2 * historic_events`
- `PollutionMobilization = FloodRisk * crop_factor * (turbidity_potential / 100)`

Crop factors are hardcoded for MVP behavior (maize/potatoes high, grassland lower).

## Notes for submission demo

- Focus area is Limburg bbox: lat `50.7-51.5`, lon `5.5-6.3`.
- Use the right panel "Top At-Risk Farms" + PDF export for farmer-facing explainability.
- This build intentionally fails closed: if live sources are unavailable, the app shows an error instead of generating synthetic geometry.
