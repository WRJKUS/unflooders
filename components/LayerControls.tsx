"use client"

import { useFloodFarmStore } from "@/lib/store"

export default function LayerControls() {
  const { layerVisibility, setLayerVisibility } = useFloodFarmStore()

  return (
    <div className="rounded-xl border border-slate-200 bg-white/90 p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-600">Layers</h3>
      <div className="space-y-2 text-sm">
        {(
          [
            ["farms", "Farm parcels"],
            ["historic", "Historic flood"],
            ["current", "Current flood"],
            ["forecast", "7-day forecast"],
            ["emoji", "Emoji markers"]
          ] as const
        ).map(([key, label]) => (
          <label key={key} className="flex items-center justify-between gap-3">
            <span>{label}</span>
            <input
              type="checkbox"
              className="h-4 w-4"
              checked={layerVisibility[key]}
              onChange={(event) => setLayerVisibility({ [key]: event.target.checked })}
            />
          </label>
        ))}
      </div>
    </div>
  )
}
