export type TimeView = "historic" | "current" | "forecast"

export type RiskScores = {
  floodRisk: number
  pollutionMobilization: number
  floodedPct: number
  soilSaturation: number
  historicEvents: number
  forecastProbability: number
}

export type FarmProperties = {
  farmId: string
  crop: string
  areaHa: number
  cropFactor: number
  fertilizerFactor: number
  turbidityPotential: number
  floodedPct?: number
  soilSaturation?: number
  historicEvents?: number
  historic_overlap_pct?: number
  forecastProbability?: number
  floodRiskScore?: number
  pollutionScore?: number
}

export type FarmFeature = GeoJSON.Feature<GeoJSON.Polygon | GeoJSON.MultiPolygon, FarmProperties>

export type FloodFeature = GeoJSON.Feature<GeoJSON.Geometry, { period: string; probability?: number }>

export type FarmCollection = GeoJSON.FeatureCollection<GeoJSON.Polygon | GeoJSON.MultiPolygon, FarmProperties>

export type FloodCollection = GeoJSON.FeatureCollection<GeoJSON.Geometry, { period: string; probability?: number }>

export type SnapshotPayload = {
  snapshotAt: string
  farms: FarmCollection
  riskZones: FloodCollection
  discharge: Array<{
    lat: number
    lon: number
    baseline_m3s: number
    current_m3s: number
    forecast_peak_m3s: number
    current_score: number
    forecast_score: number
  }>
  meta: Record<string, string>
}

export type LayerVisibility = {
  farms: boolean
  historic: boolean
  forecast: boolean
}
