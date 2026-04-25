from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from shapely import wkb
from shapely.geometry import shape
from shapely.ops import unary_union


NETHERLANDS_BBOX = (3.2, 50.7, 7.3, 53.7)
DB_PATH = Path("data/floodfarm_nl.sqlite")

MEUSE_POINTS = [
    (51.42, 5.79),
    (51.33, 5.82),
    (51.21, 5.86),
    (51.10, 5.90),
    (50.98, 5.95),
    (50.86, 6.00),
]


def normalize_crop(raw_crop: str) -> str:
    crop = str(raw_crop).lower()
    if "ma" in crop:
        return "maize"
    if "aard" in crop or "potato" in crop:
        return "potatoes"
    if "gras" in crop:
        return "grassland"
    if "biet" in crop or "beet" in crop:
        return "sugar beet"
    if "tarwe" in crop or "wheat" in crop:
        return "wheat"
    if "gerst" in crop or "barley" in crop:
        return "barley"
    return "other"


def fetch_all_features(url: str, params: dict[str, str], max_features: int | None = None) -> list[dict]:
    all_features: list[dict] = []
    next_url = url
    next_params = dict(params)
    page = 0

    while True:
        page += 1
        response = requests.get(next_url, params=next_params, timeout=60)
        response.raise_for_status()
        payload = response.json()
        features = payload.get("features", [])
        if not features:
            break

        all_features.extend(features)
        if max_features is not None and len(all_features) >= max_features:
            all_features = all_features[:max_features]
            print(f"  reached max feature cap ({max_features:,})")
            break

        if page % 20 == 0:
            print(f"  fetched pages: {page}, features: {len(all_features):,}")

        next_link = next((lnk.get("href") for lnk in payload.get("links", []) if lnk.get("rel") == "next"), None)
        if not next_link:
            break

        next_url = next_link
        next_params = None

    return all_features


def fetch_nl_farms(max_features: int | None) -> gpd.GeoDataFrame:
    minx, miny, maxx, maxy = NETHERLANDS_BBOX
    bbox_str = f"{minx},{miny},{maxx},{maxy}"
    url = "https://api.pdok.nl/rvo/gewaspercelen/ogc/v1/collections/brpgewas/items"
    features = fetch_all_features(url, {"bbox": bbox_str, "limit": "1000", "f": "json"}, max_features=max_features)

    rows = []
    seen = set()
    for idx, feature in enumerate(features):
        geom = feature.get("geometry")
        if geom is None:
            continue
        props = feature.get("properties", {})
        farm_id = str(props.get("perceel_id") or props.get("identificatie") or feature.get("id") or f"F-{idx + 1}")
        if farm_id in seen:
            continue
        seen.add(farm_id)
        rows.append(
            {
                "farm_id": farm_id,
                "crop": normalize_crop(props.get("gewas") or props.get("gewas_omschrijving") or "other"),
                "year": props.get("jaar"),
                "area_ha": float(props.get("oppervlakte", 0.0)) / 10000.0,
                "geometry": shape(geom),
            }
        )

    farms = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    farms = farms[farms.geometry.is_valid]
    farms = farms[~farms.geometry.is_empty]
    if (farms["area_ha"] <= 0).all():
        farms["area_ha"] = farms.to_crs(3857).area / 10000.0
    return farms


def fetch_nl_risk_zones(max_features: int | None) -> gpd.GeoDataFrame:
    minx, miny, maxx, maxy = NETHERLANDS_BBOX
    bbox_str = f"{minx},{miny},{maxx},{maxy}"
    url = "https://api.pdok.nl/rws/overstromingen-risicogebied/ogc/v1/collections/risk_zone/items"
    features = fetch_all_features(url, {"bbox": bbox_str, "limit": "1000", "f": "json"}, max_features=max_features)

    rows = [{"geometry": shape(ft["geometry"])} for ft in features if ft.get("geometry")]
    risk = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    risk = risk[risk.geometry.is_valid]
    risk = risk[~risk.geometry.is_empty]
    return risk


def compute_historic_overlap_and_display_risk(
    farms: gpd.GeoDataFrame,
    risk: gpd.GeoDataFrame,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    if risk.empty:
        farms = farms.copy()
        farms["historic_overlap_pct"] = 0.0
        display_risk = gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs="EPSG:4326")
        return farms, display_risk

    risk_union = unary_union(risk.geometry.tolist())
    farms_out = farms.copy()
    farm_area = farms_out.to_crs(3857).area.clip(lower=1.0)
    overlap_area = farms_out.geometry.intersection(risk_union).to_crs(3857).area
    farms_out["historic_overlap_pct"] = ((overlap_area / farm_area) * 100).clip(0, 100)

    display_risk = gpd.GeoDataFrame([{"geometry": risk_union}], geometry="geometry", crs="EPSG:4326")
    return farms_out, display_risk


def fetch_discharge_snapshot() -> pd.DataFrame:
    rows = []
    today = pd.Timestamp(datetime.now(timezone.utc).date())

    for lat, lon in MEUSE_POINTS:
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "river_discharge,river_discharge_max,river_discharge_p75",
            "past_days": 7,
            "forecast_days": 8,
            "timezone": "UTC",
        }
        resp = requests.get("https://flood-api.open-meteo.com/v1/flood", params=params, timeout=30)
        resp.raise_for_status()
        daily = resp.json().get("daily", {})
        times = pd.to_datetime(daily.get("time", []))
        if len(times) == 0:
            continue

        discharge = np.asarray(daily.get("river_discharge", []), dtype=float)
        discharge_max = np.asarray(daily.get("river_discharge_max", []), dtype=float)
        discharge_p75 = np.asarray(daily.get("river_discharge_p75", []), dtype=float)

        df = pd.DataFrame(
            {
                "time": times,
                "river_discharge": discharge,
                "river_discharge_max": discharge_max,
                "river_discharge_p75": discharge_p75,
            }
        )

        historic = df[df["time"] < today].tail(7)
        forecast = df[df["time"] >= today].head(8)

        baseline = float(historic["river_discharge"].median()) if not historic.empty else float(df["river_discharge"].median())
        current_val = float(forecast["river_discharge"].iloc[0]) if not forecast.empty else baseline
        next_week_max = float(forecast["river_discharge_max"].max()) if not forecast.empty else current_val
        p75 = float(forecast["river_discharge_p75"].replace(0, np.nan).median()) if not forecast.empty else baseline
        if np.isnan(p75) or p75 <= 0:
            p75 = max(baseline, 1.0)

        rows.append(
            {
                "lat": lat,
                "lon": lon,
                "baseline_m3s": baseline,
                "current_m3s": current_val,
                "forecast_peak_m3s": next_week_max,
                "current_score": float(np.clip((current_val / max(baseline, 1.0)) * 50, 0, 100)),
                "forecast_score": float(np.clip((next_week_max / max(p75, 1.0)) * 65, 0, 100)),
            }
        )

    return pd.DataFrame(rows)


def write_sqlite(
    farms: gpd.GeoDataFrame,
    risk_display: gpd.GeoDataFrame,
    discharge: pd.DataFrame,
    farm_cap: int | None,
    raw_risk_count: int,
) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.executescript(
            """
            DROP TABLE IF EXISTS meta;
            DROP TABLE IF EXISTS farms;
            DROP TABLE IF EXISTS risk_zones;
            DROP TABLE IF EXISTS discharge_points;

            CREATE TABLE meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE farms (
                farm_id TEXT PRIMARY KEY,
                crop TEXT,
                year TEXT,
                area_ha REAL,
                historic_overlap_pct REAL,
                geom_wkb BLOB NOT NULL
            );

            CREATE TABLE risk_zones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                geom_wkb BLOB NOT NULL
            );

            CREATE TABLE discharge_points (
                lat REAL,
                lon REAL,
                baseline_m3s REAL,
                current_m3s REAL,
                forecast_peak_m3s REAL,
                current_score REAL,
                forecast_score REAL
            );
            """
        )

        snapshot_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        cur.execute("INSERT INTO meta(key, value) VALUES(?, ?)", ("snapshot_at", snapshot_at))
        cur.execute("INSERT INTO meta(key, value) VALUES(?, ?)", ("scope", "Netherlands"))
        cur.execute("INSERT INTO meta(key, value) VALUES(?, ?)", ("farms_count", str(len(farms))))
        cur.execute("INSERT INTO meta(key, value) VALUES(?, ?)", ("risk_zones_count", str(raw_risk_count)))
        cur.execute("INSERT INTO meta(key, value) VALUES(?, ?)", ("risk_display_count", str(len(risk_display))))
        cur.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?)",
            ("farm_cap", "all" if farm_cap is None else str(farm_cap)),
        )

        farm_rows = [
            (
                str(row.farm_id),
                str(row.crop),
                str(row.year) if row.year is not None else None,
                float(row.area_ha),
                float(row.historic_overlap_pct),
                sqlite3.Binary(wkb.dumps(row.geometry)),
            )
            for row in farms.itertuples(index=False)
        ]
        cur.executemany(
            "INSERT INTO farms(farm_id, crop, year, area_ha, historic_overlap_pct, geom_wkb) VALUES (?, ?, ?, ?, ?, ?)",
            farm_rows,
        )

        risk_rows = [(sqlite3.Binary(wkb.dumps(geom)),) for geom in risk_display.geometry]
        cur.executemany("INSERT INTO risk_zones(geom_wkb) VALUES (?)", risk_rows)

        discharge_rows = [tuple(row) for row in discharge.itertuples(index=False, name=None)]
        cur.executemany(
            "INSERT INTO discharge_points(lat, lon, baseline_m3s, current_m3s, forecast_peak_m3s, current_score, forecast_score) VALUES (?, ?, ?, ?, ?, ?, ?)",
            discharge_rows,
        )

        cur.execute("CREATE INDEX idx_farms_crop ON farms(crop)")
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Netherlands floodfarm SQLite snapshot")
    parser.add_argument(
        "--max-farms",
        type=int,
        default=50000,
        help="Maximum number of farm parcels to store (default: 50000, use 0 for all)",
    )
    parser.add_argument(
        "--max-risk-zones",
        type=int,
        default=0,
        help="Maximum number of flood risk polygons to store (default: 0 = all)",
    )
    args = parser.parse_args()

    farm_cap = None if args.max_farms == 0 else max(args.max_farms, 1)
    risk_cap = None if args.max_risk_zones == 0 else max(args.max_risk_zones, 1)

    print("Downloading Netherlands BRP farm parcels...")
    farms = fetch_nl_farms(farm_cap)
    print(f"Fetched farms: {len(farms):,}")

    print("Downloading Netherlands flood risk zones...")
    risk = fetch_nl_risk_zones(risk_cap)
    print(f"Fetched risk zones: {len(risk):,}")

    print("Computing historic overlap and compact risk geometry...")
    farms, risk_display = compute_historic_overlap_and_display_risk(farms, risk)
    print(f"Prepared compact risk geometries: {len(risk_display):,}")

    print("Downloading discharge snapshot...")
    discharge = fetch_discharge_snapshot()
    print(f"Fetched discharge points: {len(discharge):,}")

    print(f"Writing SQLite snapshot: {DB_PATH}")
    write_sqlite(farms, risk_display, discharge, farm_cap=farm_cap, raw_risk_count=len(risk))
    print("Done.")


if __name__ == "__main__":
    main()
