import { create } from "zustand"
import type { LayerVisibility, TimeView } from "@/types"

type FloodFarmState = {
  timeView: TimeView
  layerVisibility: LayerVisibility
  selectedFarmId: string | null
  setTimeView: (timeView: TimeView) => void
  setLayerVisibility: (next: Partial<LayerVisibility>) => void
  setSelectedFarmId: (farmId: string | null) => void
}

export const useFloodFarmStore = create<FloodFarmState>((set) => ({
  timeView: "current",
  layerVisibility: {
    farms: true,
    historic: true,
    current: true,
    forecast: true,
    emoji: true
  },
  selectedFarmId: null,
  setTimeView: (timeView) => set({ timeView }),
  setLayerVisibility: (next) =>
    set((state) => ({
      layerVisibility: {
        ...state.layerVisibility,
        ...next
      }
    })),
  setSelectedFarmId: (farmId) => set({ selectedFarmId: farmId })
}))
