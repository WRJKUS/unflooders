import { bbox, centroid } from "@turf/turf"
import type { FarmCollection, FarmFeature, RiskScores, TimeView } from "@/types"

const CROP_FACTORS: Record<string, number> = {
  maize: 1.0,
  potatoes: 1.0,
  sugar_beet: 0.9,
  wheat: 0.7,
  barley: 0.65,
  grassland: 0.4,
  other: 0.6
}

export function cropFactor(crop: string): number {
  return CROP_FACTORS[crop] ?? CROP_FACTORS.other
}

export function clampScore(value: number): number {
  return Math.max(0, Math.min(100, value))
}

export function computeRiskScores(input: {
  floodedPct: number
  soilSaturation: number
  historicEvents: number
  forecastProbability: number
  crop: string
  turbidityPotential: number
}): RiskScores {
  const floodRisk = clampScore(
    input.floodedPct * 0.5 + input.soilSaturation * 0.3 + input.historicEvents * 0.2
  )

  const pollutionMobilization = clampScore(
    floodRisk * cropFactor(input.crop) * (clampScore(input.turbidityPotential) / 100)
  )

  return {
    floodRisk,
    pollutionMobilization,
    floodedPct: clampScore(input.floodedPct),
    soilSaturation: clampScore(input.soilSaturation),
    historicEvents: clampScore(input.historicEvents),
    forecastProbability: clampScore(input.forecastProbability)
  }
}

export function riskColor(score: number): string {
  if (score > 70) return "#c43302"
  if (score > 40) return "#f2b134"
  return "#2e8b57"
}

export function riskEmoji(score: number): string {
  if (score > 70) return "🌊"
  if (score > 40) return "⚠️"
  return "🚜"
}

export function scoreFarmFeatureFast(
  farm: FarmFeature,
  view: TimeView,
  dischargeCurrentScore: number,
  dischargeForecastScore: number
): FarmFeature {
  const historicEvents = clampScore(Number(farm.properties.historic_overlap_pct ?? 0))
  const currentFlooded = clampScore(historicEvents * 0.7 + dischargeCurrentScore * 0.3)
  const forecastProbability = clampScore(historicEvents * 0.45 + dischargeForecastScore * 0.55)
  const soilSaturation = clampScore(currentFlooded * 0.7 + historicEvents * 0.3)

  const floodedPct =
    view === "historic"
      ? historicEvents
      : view === "current"
        ? clampScore(currentFlooded * 0.7 + historicEvents * 0.3)
        : clampScore(forecastProbability * 0.65 + historicEvents * 0.35)

  const scores = computeRiskScores({
    floodedPct,
    soilSaturation,
    historicEvents,
    forecastProbability,
    crop: farm.properties.crop,
    turbidityPotential: farm.properties.turbidityPotential
  })

  return {
    ...farm,
    properties: {
      ...farm.properties,
      floodedPct: scores.floodedPct,
      soilSaturation: scores.soilSaturation,
      historicEvents: scores.historicEvents,
      forecastProbability: scores.forecastProbability,
      floodRiskScore: scores.floodRisk,
      pollutionScore: scores.pollutionMobilization
    }
  }
}

export function scoreFarmCollection(
  farms: FarmCollection,
  view: TimeView,
  dischargeCurrentScore: number,
  dischargeForecastScore: number
): FarmCollection {
  return {
    ...farms,
    features: farms.features.map((farm) =>
      scoreFarmFeatureFast(
        farm as FarmFeature,
        view,
        dischargeCurrentScore,
        dischargeForecastScore
      )
    )
  }
}

export function farmCenter(feature: FarmFeature): [number, number] {
  const c = centroid(feature)
  return c.geometry.coordinates as [number, number]
}

export function farmBounds(feature: FarmFeature): [number, number, number, number] {
  return bbox(feature) as [number, number, number, number]
}
