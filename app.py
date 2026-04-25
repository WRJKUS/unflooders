from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
import sqlite3

import folium
import geopandas as gpd
import numpy as np
import pandas as pd
import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from shapely import wkb
from shapely.geometry import LineString
from streamlit_autorefresh import st_autorefresh
from streamlit_folium import st_folium


st.set_page_config(page_title="Netherlands FloodFarm Risk Mapper", layout="wide")

APP_TITLE = "Netherlands FloodFarm Risk Mapper"
NETHERLANDS_CENTER = (52.2, 5.3)
PHASES = ["Historic (2021)", "Current", "Forecast (+7d)"]
MAX_MAP_PARCELS = 2500
MAX_REPORT_PARCELS = 3000
DB_PATH = Path("data/floodfarm_nl.sqlite")

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


@st.cache_data(show_spinner=False)
def load_sqlite_data() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, pd.DataFrame, str]:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. Run: python3 scripts/download_nl_data.py"
        )

    conn = sqlite3.connect(DB_PATH)
    try:
        meta = pd.read_sql_query("SELECT key, value FROM meta", conn)
        meta_map = dict(zip(meta["key"], meta["value"])) if not meta.empty else {}
        snapshot_at = meta_map.get("snapshot_at", "unknown")

        farms_df = pd.read_sql_query(
            "SELECT farm_id, crop, year, area_ha, historic_overlap_pct, geom_wkb FROM farms",
            conn,
        )
        farms_df["geometry"] = farms_df["geom_wkb"].apply(wkb.loads)
        farms_df = farms_df.drop(columns=["geom_wkb"])
        farms = gpd.GeoDataFrame(farms_df, geometry="geometry", crs="EPSG:4326")

        risk_df = pd.read_sql_query("SELECT geom_wkb FROM risk_zones", conn)
        risk_df["geometry"] = risk_df["geom_wkb"].apply(wkb.loads)
        risk_df = risk_df.drop(columns=["geom_wkb"])
        risk_zones = gpd.GeoDataFrame(risk_df, geometry="geometry", crs="EPSG:4326")

        discharge = pd.read_sql_query(
            "SELECT lat, lon, baseline_m3s, current_m3s, forecast_peak_m3s, current_score, forecast_score FROM discharge_points",
            conn,
        )
    finally:
        conn.close()

    return farms, risk_zones, discharge, snapshot_at


def compute_scores(
    farms: gpd.GeoDataFrame,
    selected_phase: str,
    discharge_points: pd.DataFrame,
) -> gpd.GeoDataFrame:
    gdf = farms.copy()
    historic_overlap_pct = gdf.get("historic_overlap_pct", pd.Series(np.zeros(len(gdf)))).to_numpy()

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
    fmap = folium.Map(location=NETHERLANDS_CENTER, zoom_start=7, tiles="cartodbpositron", control_scale=True)

    farm_layer = folium.FeatureGroup(name="Farm parcels (SQLite snapshot)", show=True)
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


def build_pdf_report(farm_row: pd.Series, selected_phase: str, snapshot_at: str) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    _, page_h = A4

    y = page_h - 50
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, y, "Netherlands FloodFarm Risk Report")

    y -= 24
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, y, f"Generated: {date.today().isoformat()}")
    y -= 14
    pdf.drawString(50, y, f"Time view: {selected_phase}")
    y -= 14
    pdf.drawString(50, y, f"Snapshot source: SQLite ({snapshot_at})")

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
        "Static Netherlands snapshot from SQLite. Map pan/zoom does not trigger data re-download."
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
        with st.spinner("Loading Netherlands snapshot from SQLite..."):
            farms, risk_zones, discharge_points, snapshot_at = load_sqlite_data()
            scored_farms = compute_scores(farms, selected_phase, discharge_points)
    except Exception as exc:
        st.error("Failed to load SQLite snapshot data.")
        st.exception(exc)
        st.stop()

    map_farms = scored_farms.nlargest(MAX_MAP_PARCELS, "flood_risk_score").copy()
    map_col, panel_col = st.columns([2.0, 1.0], gap="large")

    with map_col:
        fmap = build_map(map_farms, risk_zones, show_historic, show_current, show_forecast)
        st_folium(fmap, use_container_width=True, height=740, returned_objects=[])

    with panel_col:
        st.markdown("### Live Indicators")
        st.metric("Parcels loaded (SQLite)", f"{len(scored_farms):,}")
        st.metric("Parcels on map", f"{len(map_farms):,}")
        st.metric("Avg Flood Risk", f"{scored_farms['flood_risk_score'].mean():.1f}")
        st.metric("Avg Pollution Score", f"{scored_farms['pollution_mobilization_score'].mean():.1f}")
        st.metric("Snapshot date", snapshot_at)

        st.markdown("### River Discharge Snapshot")
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
        report_farms = scored_farms.nlargest(MAX_REPORT_PARCELS, "flood_risk_score").copy()
        farm_choice = st.selectbox("Choose farm", options=report_farms["farm_id"].tolist())
        farm_row = report_farms.loc[report_farms["farm_id"] == farm_choice].iloc[0]
        report_pdf = build_pdf_report(farm_row, selected_phase, snapshot_at)
        st.download_button(
            label="Download PDF report",
            data=report_pdf,
            file_name=f"floodfarm_report_{farm_choice}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    st.markdown("---")
    st.markdown(
        "Data source mode: SQLite snapshot (`data/floodfarm_nl.sqlite`) for parcels, risk zones, and discharge points. "
        "Run `python3 scripts/download_nl_data.py` to refresh the snapshot."
    )


if __name__ == "__main__":
    main()
