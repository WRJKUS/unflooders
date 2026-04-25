import { computeRiskScores, riskEmoji } from "@/lib/geo"

describe("risk scoring", () => {
  it("computes flood and pollution scores", () => {
    const scores = computeRiskScores({
      floodedPct: 80,
      soilSaturation: 70,
      historicEvents: 40,
      forecastProbability: 65,
      crop: "maize",
      turbidityPotential: 75
    })

    expect(scores.floodRisk).toBeGreaterThan(0)
    expect(scores.floodRisk).toBeLessThanOrEqual(100)
    expect(scores.pollutionMobilization).toBeGreaterThan(0)
  })

  it("maps risk to emojis", () => {
    expect(riskEmoji(75)).toBe("🌊")
    expect(riskEmoji(55)).toBe("⚠️")
    expect(riskEmoji(20)).toBe("🚜")
  })
})
