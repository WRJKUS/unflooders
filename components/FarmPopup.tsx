import type { FarmFeature } from "@/types"

type FarmPopupProps = {
  farm: FarmFeature
}

export default function FarmPopup({ farm }: FarmPopupProps) {
  const p = farm.properties

  return (
    <div className="space-y-1 text-xs">
      <div><b>Farm:</b> {p.farmId}</div>
      <div><b>Crop:</b> {p.crop}</div>
      <div><b>Area:</b> {p.areaHa.toFixed(2)} ha</div>
      <div><b>Flood Risk:</b> {(p.floodRiskScore ?? 0).toFixed(1)}/100</div>
      <div><b>Pollution:</b> {(p.pollutionScore ?? 0).toFixed(1)}/100</div>
    </div>
  )
}
