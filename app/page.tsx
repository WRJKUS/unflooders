"use client"

import dynamic from "next/dynamic"
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query"
import { useMemo } from "react"
import LayerControls from "@/components/LayerControls"
import Legend from "@/components/Legend"
import { scoreFarmCollection } from "@/lib/geo"
import {
  loadCurrentFloods,
  loadForecastFloods,
  loadSnapshot
} from "@/lib/pdok"
import type { FarmCollection } from "@/types"

const Map = dynamic(() => import("@/components/Map"), { ssr: false })

const queryClient = new QueryClient()

function MainPage() {
  const timeView = "current" as const

  const snapshotQuery = useQuery({ queryKey: ["snapshot"], queryFn: loadSnapshot })
  const currentQuery = useQuery({ queryKey: ["current"], queryFn: loadCurrentFloods })
  const forecastQuery = useQuery({ queryKey: ["forecast"], queryFn: loadForecastFloods })

  const loading = snapshotQuery.isLoading || currentQuery.isLoading || forecastQuery.isLoading
  const hasError = snapshotQuery.error || currentQuery.error || forecastQuery.error

  const scoredFarms = useMemo<FarmCollection | null>(() => {
    if (!snapshotQuery.data || !currentQuery.data || !forecastQuery.data) return null

    const dischargeCurrentScore =
      snapshotQuery.data.discharge.length > 0
        ? snapshotQuery.data.discharge.reduce((acc, point) => acc + point.current_score, 0) /
          snapshotQuery.data.discharge.length
        : 50
    const dischargeForecastScore =
      snapshotQuery.data.discharge.length > 0
        ? snapshotQuery.data.discharge.reduce((acc, point) => acc + point.forecast_score, 0) /
          snapshotQuery.data.discharge.length
        : 55

    return scoreFarmCollection(
      snapshotQuery.data.farms,
      timeView,
      dischargeCurrentScore,
      dischargeForecastScore
    )
  }, [currentQuery.data, forecastQuery.data, snapshotQuery.data, timeView])

  if (loading) {
    return <div className="p-8 text-sm text-slate-600">Loading map and flood layers...</div>
  }

  if (hasError || !scoredFarms || !currentQuery.data || !forecastQuery.data || !snapshotQuery.data) {
    return (
      <div className="p-8 text-sm text-red-600">
        Failed to load map data. Check `public/data/*.geojson` and network connectivity.
      </div>
    )
  }

  return (
    <main className="min-h-screen p-4 md:p-6">
      <div className="mb-4 flex flex-col gap-2">
        <h1 className="text-2xl font-bold text-slate-900">Limburg FloodFarm Risk Mapper (MaasGuard)</h1>
        <p className="text-sm text-slate-600">
          Next.js + MapLibre refactor for farm-level flood and pollution mobilization intelligence.
        </p>
        <p className="text-xs text-slate-500">SQLite snapshot: {snapshotQuery.data.snapshotAt}</p>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <LayerControls />
          <Legend />
        </aside>

        <section>
          <Map
            farms={scoredFarms}
            historic={snapshotQuery.data.riskZones}
            current={currentQuery.data}
            forecast={forecastQuery.data}
          />
        </section>
      </div>
    </main>
  )
}

export default function Page() {
  return (
    <QueryClientProvider client={queryClient}>
      <MainPage />
    </QueryClientProvider>
  )
}
