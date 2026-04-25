export default function Legend() {
  return (
    <div className="rounded-xl border border-slate-200 bg-white/90 p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-600">Legend</h3>
      <ul className="space-y-2 text-sm text-slate-700">
        <li><span className="mr-2 inline-block h-3 w-3 rounded-full bg-[#2e8b57]" /> Low risk (&lt;40)</li>
        <li><span className="mr-2 inline-block h-3 w-3 rounded-full bg-[#f2b134]" /> Medium risk (40–70)</li>
        <li><span className="mr-2 inline-block h-3 w-3 rounded-full bg-[#c43302]" /> High risk (&gt;70)</li>
        <li>🌊 high flood warning</li>
        <li>⚠️ medium warning</li>
        <li>🚜 low-risk farm</li>
      </ul>
    </div>
  )
}
