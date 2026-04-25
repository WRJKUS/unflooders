from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from shapely import wkb
from shapely.geometry import mapping


DEFAULT_DB = Path("data/floodfarm_nl.sqlite")


def crop_factor(crop: str) -> float:
    factors = {
        "maize": 1.0,
        "potatoes": 1.0,
        "sugar_beet": 0.9,
        "wheat": 0.7,
        "barley": 0.65,
        "grassland": 0.4,
        "other": 0.6,
    }
    return factors.get((crop or "other").lower(), 0.6)


def turbidity_potential(crop: str) -> float:
    high = {"maize", "potatoes", "sugar_beet"}
    medium = {"wheat", "barley"}
    crop_norm = (crop or "other").lower()
    if crop_norm in high:
        return 72.0
    if crop_norm in medium:
        return 58.0
    if crop_norm == "grassland":
        return 40.0
    return 52.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Export floodfarm SQLite snapshot as JSON")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to sqlite snapshot")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite file not found: {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        meta_rows = conn.execute("SELECT key, value FROM meta").fetchall()
        meta = {k: v for k, v in meta_rows}

        farm_rows = conn.execute(
            "SELECT farm_id, crop, year, area_ha, historic_overlap_pct, geom_wkb FROM farms"
        ).fetchall()
        farms = []
        for farm_id, crop, year, area_ha, historic_overlap_pct, geom_blob in farm_rows:
            geom = wkb.loads(geom_blob)
            farms.append(
                {
                    "type": "Feature",
                    "properties": {
                        "farmId": str(farm_id),
                        "crop": str(crop or "other").lower(),
                        "year": str(year or ""),
                        "areaHa": float(area_ha or 0),
                        "cropFactor": float(crop_factor(crop or "other")),
                        "fertilizerFactor": float(crop_factor(crop or "other")),
                        "turbidityPotential": float(turbidity_potential(crop or "other")),
                        "historic_overlap_pct": float(historic_overlap_pct or 0),
                    },
                    "geometry": mapping(geom),
                }
            )

        risk_rows = conn.execute("SELECT geom_wkb FROM risk_zones").fetchall()
        risk_features = []
        for (geom_blob,) in risk_rows:
            geom = wkb.loads(geom_blob)
            risk_features.append(
                {
                    "type": "Feature",
                    "properties": {"period": "historic"},
                    "geometry": mapping(geom),
                }
            )

        discharge_rows = conn.execute(
            "SELECT lat, lon, baseline_m3s, current_m3s, forecast_peak_m3s, current_score, forecast_score FROM discharge_points"
        ).fetchall()
        discharge = [
            {
                "lat": float(lat),
                "lon": float(lon),
                "baseline_m3s": float(baseline_m3s),
                "current_m3s": float(current_m3s),
                "forecast_peak_m3s": float(forecast_peak_m3s),
                "current_score": float(current_score),
                "forecast_score": float(forecast_score),
            }
            for lat, lon, baseline_m3s, current_m3s, forecast_peak_m3s, current_score, forecast_score in discharge_rows
        ]

        payload = {
            "snapshotAt": meta.get("snapshot_at", "unknown"),
            "farms": {"type": "FeatureCollection", "features": farms},
            "riskZones": {"type": "FeatureCollection", "features": risk_features},
            "discharge": discharge,
            "meta": meta,
        }

        print(json.dumps(payload))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
