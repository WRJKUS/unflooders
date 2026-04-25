import { Document, Page, StyleSheet, Text, View, pdf } from "@react-pdf/renderer"
import type { FarmFeature } from "@/types"

const styles = StyleSheet.create({
  page: { padding: 24, fontSize: 11, color: "#1f2937" },
  title: { fontSize: 18, marginBottom: 10 },
  row: { marginBottom: 6 },
  sectionTitle: { marginTop: 14, marginBottom: 6, fontSize: 13 }
})

function FarmReportDoc({ farm }: { farm: FarmFeature }) {
  const p = farm.properties

  return (
    <Document>
      <Page size="A4" style={styles.page}>
        <Text style={styles.title}>Limburg FloodFarm Risk Report</Text>
        <Text style={styles.row}>Farm: {p.farmId}</Text>
        <Text style={styles.row}>Crop: {p.crop}</Text>
        <Text style={styles.row}>Area: {p.areaHa.toFixed(2)} ha</Text>
        <Text style={styles.row}>Flood Risk: {(p.floodRiskScore ?? 0).toFixed(1)} / 100</Text>
        <Text style={styles.row}>Pollution Mobilization: {(p.pollutionScore ?? 0).toFixed(1)} / 100</Text>

        <View>
          <Text style={styles.sectionTitle}>Inputs</Text>
          <Text style={styles.row}>Flooded %: {(p.floodedPct ?? 0).toFixed(1)}%</Text>
          <Text style={styles.row}>Soil Saturation: {(p.soilSaturation ?? 0).toFixed(1)}%</Text>
          <Text style={styles.row}>Historic Events: {(p.historicEvents ?? 0).toFixed(1)}%</Text>
          <Text style={styles.row}>Forecast Probability: {(p.forecastProbability ?? 0).toFixed(1)}%</Text>
        </View>
      </Page>
    </Document>
  )
}

export async function buildFarmPdfBlob(farm: FarmFeature): Promise<Blob> {
  return pdf(<FarmReportDoc farm={farm} />).toBlob()
}
