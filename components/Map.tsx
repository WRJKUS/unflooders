"use client"

import { useEffect, useMemo, useRef } from "react"
import maplibregl, { Popup } from "maplibre-gl"
import type { FarmCollection, FloodCollection } from "@/types"
import { riskColor, riskEmoji } from "@/lib/geo"
import { useFloodFarmStore } from "@/lib/store"

type MapProps = {
  farms: FarmCollection
  historic: FloodCollection
  current: FloodCollection
  forecast: FloodCollection
}

const SOURCE_IDS = {
  farms: "farms",
  historic: "historic",
  current: "current",
  forecast: "forecast",
  emojis: "emojis"
} as const

function popupHtml(properties: Record<string, unknown>): string {
  return [
    `<b>Farm:</b> ${properties.farmId}`,
    `<b>Crop:</b> ${properties.crop}`,
    `<b>Area:</b> ${Number(properties.areaHa || 0).toFixed(2)} ha`,
    `<b>Flood Risk Score:</b> ${Number(properties.floodRiskScore || 0).toFixed(1)}/100`,
    `<b>Pollution Score:</b> ${Number(properties.pollutionScore || 0).toFixed(1)}/100`,
    `<b>Flooded %:</b> ${Number(properties.floodedPct || 0).toFixed(1)}%`,
    `<b>Forecast %:</b> ${Number(properties.forecastProbability || 0).toFixed(1)}%`
  ].join("<br>")
}

function buildEmojiSource(farms: FarmCollection): GeoJSON.FeatureCollection<GeoJSON.Point> {
  return {
    type: "FeatureCollection",
    features: farms.features.map((feature) => {
      const geometry = feature.geometry
      const coords =
        geometry.type === "Polygon"
          ? geometry.coordinates[0][0]
          : geometry.type === "MultiPolygon"
            ? geometry.coordinates[0][0][0]
            : [5.95, 50.95]

      return {
        type: "Feature",
        geometry: {
          type: "Point",
          coordinates: coords
        },
        properties: {
          ...feature.properties,
          emoji: riskEmoji(Number(feature.properties.floodRiskScore ?? 0))
        }
      }
    })
  }
}

export default function Map({ farms, historic, current, forecast }: MapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const popupRef = useRef<Popup | null>(null)

  const { layerVisibility } = useFloodFarmStore()

  const pointMode = farms.features.length > 12000

  const farmData = useMemo(() => {
    return {
      ...farms,
      features: farms.features.map((feature) => ({
        ...feature,
        properties: {
          ...feature.properties,
          color: riskColor(Number(feature.properties.floodRiskScore ?? 0))
        }
      }))
    }
  }, [farms])

  const farmPoints = useMemo<GeoJSON.FeatureCollection<GeoJSON.Point>>(() => {
    return {
      type: "FeatureCollection",
      features: farmData.features.map((feature) => {
        const geometry = feature.geometry
        const coordinates =
          geometry.type === "Polygon"
            ? geometry.coordinates[0][0]
            : geometry.type === "MultiPolygon"
              ? geometry.coordinates[0][0][0]
              : [5.95, 50.95]

        return {
          type: "Feature",
          geometry: {
            type: "Point",
            coordinates
          },
          properties: feature.properties
        }
      })
    }
  }, [farmData])

  const emojiData = useMemo(() => buildEmojiSource(farmData), [farmData])

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "© OpenStreetMap contributors"
          }
        },
        layers: [{ id: "osm", type: "raster", source: "osm" }]
      },
      center: [5.95, 50.95],
      zoom: 9,
      maxPitch: 65
    })

    map.addControl(new maplibregl.NavigationControl(), "top-right")
    popupRef.current = new Popup({ closeButton: true, closeOnClick: true })

    map.on("load", () => {
      map.addSource(SOURCE_IDS.farms, {
        type: "geojson",
        data: pointMode ? farmPoints : (farmData as GeoJSON.FeatureCollection)
      })
      if (pointMode) {
        map.addLayer({
          id: "farms-fill",
          type: "circle",
          source: SOURCE_IDS.farms,
          paint: {
            "circle-color": ["get", "color"],
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 6, 1.5, 10, 4.5, 13, 7],
            "circle-opacity": 0.85,
            "circle-stroke-width": 0.4,
            "circle-stroke-color": "#1e293b"
          }
        })
      } else {
        map.addLayer({
          id: "farms-fill",
          type: "fill",
          source: SOURCE_IDS.farms,
          paint: {
            "fill-color": ["get", "color"],
            "fill-opacity": 0.62
          }
        })
        map.addLayer({
          id: "farms-outline",
          type: "line",
          source: SOURCE_IDS.farms,
          paint: {
            "line-color": "#263238",
            "line-width": 0.6
          }
        })
      }

      map.addSource(SOURCE_IDS.historic, { type: "geojson", data: historic as GeoJSON.FeatureCollection })
      map.addLayer({
        id: "historic-fill",
        type: "fill",
        source: SOURCE_IDS.historic,
        paint: {
          "fill-color": "#ca3a3a",
          "fill-opacity": 0.15
        }
      })

      map.addSource(SOURCE_IDS.current, { type: "geojson", data: current as GeoJSON.FeatureCollection })
      map.addLayer({
        id: "current-fill",
        type: "fill",
        source: SOURCE_IDS.current,
        paint: {
          "fill-color": "#1f78b4",
          "fill-opacity": 0.2
        }
      })



      map.addSource("efas-forecast-wms", {
        type: "raster",
        tiles: [
          "https://european-flood.emergency.copernicus.eu/api/wms/?service=WMS&version=1.1.1&request=GetMap&layers=mapserver:SubSeasonalOutlookUnion&styles=&format=image/png&transparent=true&srs=EPSG:3857&bbox={bbox-epsg-3857}&width=256&height=256"
        ],
        tileSize: 256
      })
      map.addLayer({
        id: "forecast-efas-raster",
        type: "raster",
        source: "efas-forecast-wms",
        paint: {
          "raster-opacity": 0.34
        }
      })

      map.addSource(SOURCE_IDS.emojis, {
        type: "geojson",
        data: emojiData,
        cluster: true,
        clusterMaxZoom: 9,
        clusterRadius: 46
      })
      map.addLayer({
        id: "emoji-clusters",
        type: "circle",
        source: SOURCE_IDS.emojis,
        filter: ["has", "point_count"],
        paint: {
          "circle-color": "#204a69",
          "circle-opacity": 0.84,
          "circle-radius": ["step", ["get", "point_count"], 14, 25, 18, 80, 24]
        }
      })
      map.addLayer({
        id: "emoji-cluster-count",
        type: "symbol",
        source: SOURCE_IDS.emojis,
        filter: ["has", "point_count"],
        layout: {
          "text-field": ["get", "point_count_abbreviated"],
          "text-size": 12,
          "text-font": ["Open Sans Bold"]
        },
        paint: { "text-color": "#fff" }
      })
      map.addLayer({
        id: "emoji-symbol",
        type: "symbol",
        source: SOURCE_IDS.emojis,
        filter: ["!", ["has", "point_count"]],
        layout: {
          "text-field": ["get", "emoji"],
          "text-size": 22,
          "text-allow-overlap": true,
          "icon-allow-overlap": true
        }
      })

      map.on("click", "farms-fill", (event) => {
        const properties = (event.features?.[0]?.properties ?? {}) as Record<string, unknown>
        popupRef.current?.setLngLat(event.lngLat).setHTML(popupHtml(properties)).addTo(map)
      })

      map.on("click", "emoji-clusters", (event) => {
        const features = map.queryRenderedFeatures(event.point, { layers: ["emoji-clusters"] })
        if (!features.length) return
        const clusterId = features[0].properties?.cluster_id
        const source = map.getSource(SOURCE_IDS.emojis) as maplibregl.GeoJSONSource & {
          getClusterExpansionZoom: (id: number, cb: (err: Error | null, zoom: number) => void) => void
        }
        source.getClusterExpansionZoom(clusterId, (err, zoom) => {
          if (err) return
          map.easeTo({
            center: (features[0].geometry as GeoJSON.Point).coordinates as [number, number],
            zoom
          })
        })
      })
    })

    mapRef.current = map

    return () => {
      popupRef.current?.remove()
      map.remove()
      mapRef.current = null
    }
  }, [current, emojiData, farmData, farmPoints, forecast, historic, pointMode])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.isStyleLoaded()) return

    const setVisibility = (id: string, visible: boolean) => {
      if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", visible ? "visible" : "none")
    }

    setVisibility("farms-fill", layerVisibility.farms)
    setVisibility("farms-outline", layerVisibility.farms)
    setVisibility("historic-fill", layerVisibility.historic)
    setVisibility("current-fill", layerVisibility.current)
    setVisibility("forecast-efas-raster", layerVisibility.forecast)
    setVisibility("emoji-symbol", layerVisibility.emoji)
    setVisibility("emoji-clusters", layerVisibility.emoji)
    setVisibility("emoji-cluster-count", layerVisibility.emoji)
  }, [layerVisibility])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.isStyleLoaded()) return

    const farmsSource = map.getSource(SOURCE_IDS.farms) as maplibregl.GeoJSONSource | undefined
    farmsSource?.setData(pointMode ? farmPoints : (farmData as GeoJSON.FeatureCollection))

    const emojisSource = map.getSource(SOURCE_IDS.emojis) as maplibregl.GeoJSONSource | undefined
    emojisSource?.setData(emojiData)
  }, [emojiData, farmData, farmPoints, pointMode])

  return (
    <div className="space-y-2">
      {pointMode ? (
        <div className="text-xs text-slate-600">
          Rendering optimized point mode for large dataset ({farms.features.length.toLocaleString()} farms).
        </div>
      ) : null}
      <div ref={containerRef} className="h-[calc(100vh-120px)] w-full rounded-xl border border-slate-200 shadow" />
    </div>
  )
}
