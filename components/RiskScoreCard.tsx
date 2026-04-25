type RiskScoreCardProps = {
  floodRiskAverage: number
  pollutionAverage: number
  farmsCount: number
}

export default function RiskScoreCard({
  floodRiskAverage,
  pollutionAverage,
  farmsCount
}: RiskScoreCardProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white/90 p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-600">Overview</h3>
      <dl className="grid grid-cols-1 gap-2 text-sm text-slate-700">
        <div className="flex items-center justify-between">
          <dt>Farms</dt>
          <dd className="font-semibold">{farmsCount.toLocaleString()}</dd>
        </div>
        <div className="flex items-center justify-between">
          <dt>Avg flood risk</dt>
          <dd className="font-semibold">{floodRiskAverage.toFixed(1)}</dd>
        </div>
        <div className="flex items-center justify-between">
          <dt>Avg pollution score</dt>
          <dd className="font-semibold">{pollutionAverage.toFixed(1)}</dd>
        </div>
      </dl>
    </div>
  )
}
