import type { FarmCollection, FloodCollection, SnapshotPayload } from "@/types"

export async function loadSnapshot(): Promise<SnapshotPayload> {
  const response = await fetch("/api/snapshot")
  if (!response.ok) throw new Error("Failed to load sqlite snapshot API")
  return (await response.json()) as SnapshotPayload
}

export async function loadFarmParcels(): Promise<FarmCollection> {
  const snapshot = await loadSnapshot()
  return snapshot.farms
}

export async function loadHistoricFloods(): Promise<FloodCollection> {
  const snapshot = await loadSnapshot()
  return snapshot.riskZones
}

export async function loadCurrentFloods(): Promise<FloodCollection> {
  const response = await fetch("/data/flood-current.geojson")
  if (!response.ok) throw new Error("Failed to load current flood layer")
  return (await response.json()) as FloodCollection
}

export async function loadForecastFloods(): Promise<FloodCollection> {
  const response = await fetch("/data/flood-forecast.geojson")
  if (!response.ok) throw new Error("Failed to load forecast flood layer")
  return (await response.json()) as FloodCollection
}
