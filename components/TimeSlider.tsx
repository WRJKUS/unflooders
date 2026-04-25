"use client"

import { useFloodFarmStore } from "@/lib/store"
import type { TimeView } from "@/types"

const OPTIONS: { label: string; value: TimeView }[] = [
  { label: "Historic", value: "historic" },
  { label: "Current", value: "current" },
  { label: "+7d Forecast", value: "forecast" }
]

export default function TimeSlider() {
  const { timeView, setTimeView } = useFloodFarmStore()

  return (
    <div className="rounded-xl border border-slate-200 bg-white/90 p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-600">Time View</h3>
      <div className="grid grid-cols-3 gap-2">
        {OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => setTimeView(option.value)}
            className={[
              "rounded-md px-2 py-2 text-xs font-semibold",
              timeView === option.value ? "bg-slate-800 text-white" : "bg-slate-100 text-slate-600"
            ].join(" ")}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  )
}
