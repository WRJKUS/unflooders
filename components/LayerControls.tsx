"use client"

import { useFloodFarmStore } from "@/lib/store"

export default function LayerControls() {
  const { layerVisibility, setLayerVisibility } = useFloodFarmStore()

  return (
    <div className="rounded-xl border border-slate-200 bg-white/90 p-4 shadow-sm">
      <h3 className="mb-3 font-semibold uppercase tracking-wide text-slate-600" style={{ fontSize: '2em' }}>Layers</h3>
      <div className="space-y-2" style={{ fontSize: '1.5em' }}>
        {(
          [
            ["farms", "Farm parcels"],
            ["historic", "Historic flood"],
            ["forecast", "7-day forecast"]
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
