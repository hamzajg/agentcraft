/**
 * Sparkline SVG chart for metric history.
 * Pure SVG — no chart library needed.
 */
export function MiniChart({ data, color = '#10b981', height = 40 }) {
  if (!data || data.length < 2) return null

  const w = 260, h = height
  const max = 100
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w
    const y = h - (Math.max(0, Math.min(100, v)) / max) * h
    return `${x},${y}`
  }).join(' ')

  // Fill polygon
  const fill = [
    `0,${h}`,
    ...data.map((v, i) => {
      const x = (i / (data.length - 1)) * w
      const y = h - (Math.max(0, Math.min(100, v)) / max) * h
      return `${x},${y}`
    }),
    `${w},${h}`,
  ].join(' ')

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ height }}>
      <polygon points={fill} fill={color} fillOpacity={0.12} />
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5"
                strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  )
}
