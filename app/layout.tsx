import type { Metadata } from "next"
import type { ReactNode } from "react"
import "maplibre-gl/dist/maplibre-gl.css"
import "./globals.css"

export const metadata: Metadata = {
  title: "Limburg FloodFarm Risk Mapper",
  description: "Farm-level flood and pollution mobilization intelligence for Limburg."
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
