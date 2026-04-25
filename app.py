from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO

import folium
import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from shapely.geometry import LineString, shape
from shapely.ops import unary_union
from streamlit_autorefresh import st_autorefresh
from streamlit_folium import st_folium


st.set_page_config(page_title="Limburg FloodFarm Risk Mapper", layout="wide")

APP_TITLE = "Limburg FloodFarm Risk Mapper"
LIMBURG_BBOX = (5.5, 50.7, 6.3, 51.5)
LIMBURG_CENTER = (51.05, 5.95)
PHASES = ["Historic (2021)", "Current", "Forecast (+7d)"]

CROP_FACTORS = {
    "maize": 1.0,
    "potatoes": 1.0,
    "sugar beet": 0.9,
    "wheat": 0.7,
    "barley": 0.65,
    "grassland": 0.4,
    "other": 0.6,
}

MEUSE_POINTS = [
    (51.42, 5.79),
    (51.33, 5.82),
    (51.21, 5.86),
    (51.10, 5.90),
    (50.98, 5.95),
    (50.86, 6.00),
]

MEUSE_LINE = LineString([(lon, lat) for lat, lon in MEUSE_POINTS])
MEUSE_LINE_3857 = gpd.GeoSeries([MEUSE_LINE], crs="EPSG:4326").to_crs(3857).iloc[0]


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


def parse_features_to_gdf(features: list[dict], id_keys: list[str] | None = None) -> gpd.GeoDataFrame:
    rows = []
    id_keys = id_keys or ["id"]

    for idx, feature in enumerate(features):
        geom = feature.get("geometry")
        if geom is None:
            continue
        props = feature.get("properties", {})
        farm_id = None
        for key in id_keys:
            if props.get(key):
                farm_id = str(props[key])
                break
        if farm_id is None:
            farm_id = str(feature.get("id") or f"PARCEL-{idx + 1}")

        rows.append(
            {
                "farm_id": farm_id,
                "crop": normalize_crop(props.get("gewas") or props.get("gewas_omschrijving") or "other"),
                "year": props.get("jaar"),
                "area_ha": float(props.get("oppervlakte", 0.0)) / 10000.0,
                "geometry": shape(geom),
            }
        )

    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    if gdf.empty:
        return gdf

    gdf = gdf[gdf.geometry.is_valid]
    gdf = gdf[~gdf.geometry.is_empty]
    if gdf.empty:
        return gdf

    if (gdf["area_ha"] <= 0).all():
        gdf["area_ha"] = gdf.to_crs(3857).area / 10000.0

    return gdf


@st.cache_data(show_spinner=False, ttl=1800)
def fetch_brp_farms(limit: int = 300) -> gpd.GeoDataFrame:
    minx, miny, maxx, maxy = LIMBURG_BBOX
    bbox_str = f"{minx},{miny},{maxx},{maxy}"

    endpoints = [
        (
            "https://api.pdok.nl/rvo/gewaspercelen/ogc/v1/collections/brpgewas/items",
            {"bbox": bbox_str, "limit": str(limit), "f": "json"},
        ),
        (
            "https://service.pdok.nl/rvo/brpgewaspercelen/wfs/v1_0",
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": "brpgewaspercelen:brpgewaspercelen",
                "srsName": "EPSG:4326",
                "outputFormat": "application/json",
                "bbox": f"{bbox_str},EPSG:4326",
                "count": str(limit),
            },
        ),
    ]

    failures = []
    for url, params in endpoints:
        try:
            response = requests.get(url, params=params, timeout=45)
            response.raise_for_status()
            payload = response.json()
            features = payload.get("features", [])
            if not features:
                failures.append(f"{url}: no features")
                continue

            farms = parse_features_to_gdf(features, id_keys=["perceel_id", "identificatie", "id"])
            if farms.empty:
                failures.append(f"{url}: empty after parsing")
                continue
            return farms
        except Exception as exc:
            failures.append(f"{url}: {exc}")

    raise RuntimeError("Could not load PDOK BRP farm parcels. " + " | ".join(failures))


@st.cache_data(show_spinner=False, ttl=21600)
def fetch_pdok_flood_polygons(collection: str, limit: int = 2000) -> gpd.GeoDataFrame:
    minx, miny, maxx, maxy = LIMBURG_BBOX
    bbox_str = f"{minx},{miny},{maxx},{maxy}"
    url = f"https://api.pdok.nl/rws/{collection}/ogc/v1/collections/{'risk_zone' if collection == 'overstromingen-risicogebied' else 'observed_event'}/items"

    response = requests.get(url, params={"bbox": bbox_str, "limit": str(limit), "f": "json"}, timeout=45)
    response.raise_for_status()
    features = response.json().get("features", [])
    if not features:
        return gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs="EPSG:4326")

    rows = [{"geometry": shape(ft["geometry"])} for ft in features if ft.get("geometry")]
    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    gdf = gdf[gdf.geometry.is_valid]
    gdf = gdf[~gdf.geometry.is_empty]
    return gdf


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_openmeteo_discharge() -> pd.DataFrame:
    rows = []
    today = pd.Timestamp(date.today())

    for lat, lon in MEUSE_POINTS:
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "river_discharge,river_discharge_max,river_discharge_median,river_discharge_p75",
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

        current_score = np.clip((current_val / max(baseline, 1.0)) * 50, 0, 100)
        forecast_score = np.clip((next_week_max / max(p75, 1.0)) * 65, 0, 100)

        rows.append(
            {
                "lat": lat,
                "lon": lon,
                "baseline_m3s": baseline,
                "current_m3s": current_val,
                "forecast_peak_m3s": next_week_max,
                "current_score": current_score,
                "forecast_score": forecast_score,
            }
        )

    if not rows:
        raise RuntimeError("Open-Meteo flood API returned no discharge data for Limburg sample points")

    return pd.DataFrame(rows)


def compute_scores(
    farms: gpd.GeoDataFrame,
    selected_phase: str,
    risk_zones: gpd.GeoDataFrame,
    discharge_points: pd.DataFrame,
) -> gpd.GeoDataFrame:
    gdf = farms.copy()
    farm_area = gdf.to_crs(3857).area.clip(lower=1.0)

    if risk_zones.empty:
        historic_union = None
        historic_overlap_pct = np.zeros(len(gdf))
    else:
        historic_union = unary_union(risk_zones.geometry.tolist())
        overlap_area = gdf.geometry.intersection(historic_union).to_crs(3857).area
        historic_overlap_pct = ((overlap_area / farm_area) * 100).clip(0, 100)

    centroid_points_3857 = gdf.to_crs(3857).centroid
    dist_m = centroid_points_3857.distance(MEUSE_LINE_3857)
    proximity = np.exp(-dist_m / 7000.0)

    current_river_score = float(discharge_points["current_score"].mean())
    forecast_river_score = float(discharge_points["forecast_score"].mean())

    current_component = (proximity * current_river_score).clip(0, 100)
    forecast_component = (proximity * forecast_river_score).clip(0, 100)

    if selected_phase == "Historic (2021)":
        flooded_pct = historic_overlap_pct
    elif selected_phase == "Current":
        flooded_pct = (0.55 * historic_overlap_pct + 0.45 * current_component).clip(0, 100)
    else:
        flooded_pct = (0.35 * historic_overlap_pct + 0.65 * forecast_component).clip(0, 100)

    gdf["flooded_pct"] = flooded_pct
    gdf["historic_events"] = np.where(historic_overlap_pct > 1.0, 100, 15)
    gdf["forecast_prob"] = forecast_component.clip(0, 100)
    gdf["soil_saturation"] = (0.65 * current_component + 0.35 * historic_overlap_pct).clip(0, 100)
    gdf["turbidity_potential"] = (
        25
        + 0.40 * gdf["flooded_pct"]
        + 0.25 * gdf["forecast_prob"]
        + np.where(gdf["crop"].isin(["maize", "potatoes", "sugar beet"]), 15, 0)
    ).clip(0, 100)

    gdf["flood_risk_score"] = (
        0.5 * gdf["flooded_pct"] + 0.3 * gdf["soil_saturation"] + 0.2 * gdf["historic_events"]
    ).clip(0, 100)

    gdf["crop_factor"] = gdf["crop"].map(CROP_FACTORS).fillna(CROP_FACTORS["other"])
    gdf["pollution_mobilization_score"] = (
        gdf["flood_risk_score"] * gdf["crop_factor"] * (gdf["turbidity_potential"] / 100.0)
    ).clip(0, 100)

    return gdf


def risk_color(score: float) -> str:
    if score < 30:
        return "#2e8b57"
    if score < 60:
        return "#f2b134"
    return "#c43302"


def add_legend(map_obj: folium.Map) -> None:
    legend_html = """
    <div style="
        position: fixed;
        bottom: 30px;
        left: 30px;
        z-index: 9999;
        background: rgba(255,255,255,0.95);
        border: 1px solid #bbb;
        border-radius: 8px;
        padding: 10px 12px;
        font-size: 13px;
        color: #111;
    ">
      <b>Risk Legend</b><br>
      <span style="color:#2e8b57">&#9679;</span> Flood risk &lt; 30<br>
      <span style="color:#f2b134">&#9679;</span> Flood risk 30-59<br>
      <span style="color:#c43302">&#9679;</span> Flood risk 60-100<br>
      <hr style="margin:6px 0;">
      <span style="color:#ca3a3a">&#9632;</span> PDOK flood risk zones<br>
      <span style="color:#1f78b4">&#9632;</span> Copernicus GFM observed flood extent<br>
      <span style="color:#ff8c00">&#9632;</span> EFAS sub-seasonal outlook
    </div>
    """
    map_obj.get_root().html.add_child(folium.Element(legend_html))


def build_map(
    farms: gpd.GeoDataFrame,
    risk_zones: gpd.GeoDataFrame,
    show_historic: bool,
    show_current: bool,
    show_forecast: bool,
) -> folium.Map:
    fmap = folium.Map(location=LIMBURG_CENTER, zoom_start=9, tiles="cartodbpositron", control_scale=True)

    farm_layer = folium.FeatureGroup(name="Farm parcels (PDOK BRP)", show=True)
    for _, row in farms.iterrows():
        popup_html = (
            f"<b>Farm:</b> {row['farm_id']}<br>"
            f"<b>Crop:</b> {row['crop']}<br>"
            f"<b>Area:</b> {row['area_ha']:.2f} ha<br>"
            f"<b>Flood Risk Score:</b> {row['flood_risk_score']:.1f}/100<br>"
            f"<b>Pollution Mobilization:</b> {row['pollution_mobilization_score']:.1f}/100<br>"
            f"<b>Flooded Area Proxy:</b> {row['flooded_pct']:.1f}%<br>"
            f"<b>Forecast Prob Proxy:</b> {row['forecast_prob']:.1f}%"
        )

        folium.GeoJson(
            row.geometry.__geo_interface__,
            style_function=lambda _x, score=row["flood_risk_score"]: {
                "fillColor": risk_color(score),
                "color": "#242424",
                "weight": 0.5,
                "fillOpacity": 0.72,
            },
            tooltip=folium.Tooltip(f"{row['farm_id']} | {row['crop']} | Risk {row['flood_risk_score']:.0f}"),
            popup=folium.Popup(popup_html, max_width=320),
        ).add_to(farm_layer)
    farm_layer.add_to(fmap)

    if show_historic and not risk_zones.empty:
        folium.GeoJson(
            risk_zones.__geo_interface__,
            name="Historic flood risk zones (PDOK)",
            style_function=lambda _x: {
                "fillColor": "#ca3a3a",
                "color": "#8f2020",
                "weight": 0.7,
                "fillOpacity": 0.16,
            },
        ).add_to(fmap)

    if show_current:
        folium.raster_layers.WmsTileLayer(
            url="https://geoserver.gfm.eodc.eu/geoserver/gfm/wms",
            layers="observed_flood_extent_group_layer",
            name="Current observed flood (Copernicus GFM)",
            fmt="image/png",
            transparent=True,
            overlay=True,
            control=True,
            opacity=0.6,
        ).add_to(fmap)

    if show_forecast:
        folium.raster_layers.WmsTileLayer(
            url="https://european-flood.emergency.copernicus.eu/api/wms/",
            layers="mapserver:SubSeasonalOutlookUnion",
            name="Forecast outlook (EFAS)",
            fmt="image/png",
            transparent=True,
            overlay=True,
            control=True,
            opacity=0.45,
        ).add_to(fmap)

    folium.LayerControl(collapsed=False).add_to(fmap)
    add_legend(fmap)
    return fmap


def build_pdf_report(farm_row: pd.Series, selected_phase: str) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    _, page_h = A4

    y = page_h - 50
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, y, "Limburg FloodFarm Risk Report")

    y -= 24
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, y, f"Generated: {date.today().isoformat()}")
    y -= 14
    pdf.drawString(50, y, f"Time view: {selected_phase}")
    y -= 14
    pdf.drawString(50, y, "Data mode: real sources (PDOK + Copernicus + Open-Meteo/GloFAS)")

    y -= 28
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, y, f"Farm {farm_row['farm_id']}")

    y -= 18
    pdf.setFont("Helvetica", 11)
    lines = [
        f"Crop type: {farm_row['crop']}",
        f"Area: {farm_row['area_ha']:.2f} ha",
        f"Flood Risk Score: {farm_row['flood_risk_score']:.1f}/100",
        f"Pollution Mobilization Score: {farm_row['pollution_mobilization_score']:.1f}/100",
        f"Flooded area proxy: {farm_row['flooded_pct']:.1f}%",
        f"Soil saturation proxy: {farm_row['soil_saturation']:.1f}%",
        f"Historic exposure: {farm_row['historic_events']:.0f}%",
        f"7-day forecast probability proxy: {farm_row['forecast_prob']:.1f}%",
        f"Turbidity potential proxy: {farm_row['turbidity_potential']:.1f}%",
    ]
    for line in lines:
        pdf.drawString(60, y, line)
        y -= 16

    y -= 10
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, "Interpretation")
    y -= 16
    pdf.setFont("Helvetica", 10)
    pdf.drawString(60, y, "Flood Risk combines parcel overlap with PDOK flood zones and river discharge pressure.")
    y -= 14
    pdf.drawString(60, y, "Pollution Mobilization links flood risk with crop sensitivity and turbidity potential.")

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()


def phase_from_autoplay(default_phase: str) -> str:
    if "autoplay" not in st.session_state:
        st.session_state.autoplay = False

    if st.session_state.autoplay:
        tick = st_autorefresh(interval=1700, key="phase_anim_timer")
        return PHASES[tick % len(PHASES)]
    return default_phase


def main() -> None:
    st.title(APP_TITLE)
    st.caption(
        "Real-data build: PDOK BRP parcels + PDOK flood-risk zones + Copernicus GFM observed flood WMS "
        "+ EFAS outlook WMS + Open-Meteo flood API (GloFAS-based river discharge)."
    )

    with st.sidebar:
        st.subheader("Controls")
        play_col, stop_col = st.columns(2)
        if play_col.button("Play"):
            st.session_state.autoplay = True
        if stop_col.button("Pause"):
            st.session_state.autoplay = False

        selected_phase = st.select_slider("Time View", options=PHASES, value=phase_from_autoplay("Current"))
        show_historic = st.checkbox("Show historic flood zones (PDOK)", value=True)
        show_current = st.checkbox("Show current flood extent (Copernicus GFM)", value=True)
        show_forecast = st.checkbox("Show +7d forecast outlook (EFAS)", value=True)
        farm_limit = st.slider("Farm sample size", min_value=100, max_value=1200, value=350, step=50)

        today = date.today()
        acquisition_dates = [today - timedelta(days=6 * i) for i in range(6)][::-1]
        selected_acq = st.selectbox(
            "Sentinel-1 cadence reference",
            acquisition_dates,
            index=len(acquisition_dates) - 1,
            format_func=lambda d: d.isoformat(),
        )
        st.caption(f"Reference date: {selected_acq.isoformat()}")

    try:
        with st.spinner("Loading real data from PDOK/Copernicus/Open-Meteo..."):
            farms = fetch_brp_farms(limit=farm_limit)
            risk_zones = fetch_pdok_flood_polygons("overstromingen-risicogebied", limit=3000)
            discharge_points = fetch_openmeteo_discharge()
            scored_farms = compute_scores(farms, selected_phase, risk_zones, discharge_points)
    except Exception as exc:
        st.error("Real data loading failed. No synthetic fallback is used in this mode.")
        st.exception(exc)
        st.stop()

    map_col, panel_col = st.columns([2.0, 1.0], gap="large")

    with map_col:
        fmap = build_map(scored_farms, risk_zones, show_historic, show_current, show_forecast)
        st_folium(fmap, use_container_width=True, height=740)

    with panel_col:
        st.markdown("### Live Indicators")
        st.metric("Parcels loaded", f"{len(scored_farms):,}")
        st.metric("Avg Flood Risk", f"{scored_farms['flood_risk_score'].mean():.1f}")
        st.metric("Avg Pollution Score", f"{scored_farms['pollution_mobilization_score'].mean():.1f}")
        st.metric("PDOK risk polygons", f"{len(risk_zones):,}")

        st.markdown("### River Discharge (Open-Meteo/GloFAS)")
        discharge_table = discharge_points.copy()
        for col in ["baseline_m3s", "current_m3s", "forecast_peak_m3s", "current_score", "forecast_score"]:
            discharge_table[col] = discharge_table[col].round(1)
        st.dataframe(discharge_table, use_container_width=True, height=190)

        st.markdown("### Top At-Risk Farms")
        top_risk = scored_farms.nlargest(10, "flood_risk_score")[
            ["farm_id", "crop", "area_ha", "flood_risk_score", "pollution_mobilization_score"]
        ].copy()
        top_risk["area_ha"] = top_risk["area_ha"].round(2)
        top_risk["flood_risk_score"] = top_risk["flood_risk_score"].round(1)
        top_risk["pollution_mobilization_score"] = top_risk["pollution_mobilization_score"].round(1)
        st.dataframe(top_risk, use_container_width=True, height=230)

        st.markdown("### Farm Report Export")
        farm_choice = st.selectbox("Choose farm", options=scored_farms["farm_id"].tolist())
        farm_row = scored_farms.loc[scored_farms["farm_id"] == farm_choice].iloc[0]
        report_pdf = build_pdf_report(farm_row, selected_phase)

        st.download_button(
            label="Download PDF report",
            data=report_pdf,
            file_name=f"floodfarm_report_{farm_choice}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    st.markdown("---")
    st.markdown(
        "Data sources: `api.pdok.nl/rvo/gewaspercelen` (BRP parcels), `api.pdok.nl/rws/overstromingen-risicogebied` "
        "(flood risk zones), `geoserver.gfm.eodc.eu` (Copernicus GFM observed flood extent WMS), "
        "`european-flood.emergency.copernicus.eu` (EFAS outlook WMS), and `flood-api.open-meteo.com` "
        "(GloFAS-based river discharge time series)."
    )


if __name__ == "__main__":
    main()
