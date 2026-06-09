import React from 'react'

export function AgentNode({ node, status = 'idle', isHovered, onHover, onClick }) {
  const { x, y, label, isHub } = node

  // Determine colors based on status
  const isBlocked = status === 'blocked' || status === 'pending'
  const isRunning = status === 'active' || status === 'running'

  let nodeColor = '#38bdf8' // Default cyan
  let pulseClass = ''

  if (isHub) {
    nodeColor = '#ffb830' // Hermes Gold
    pulseClass = 'constellation-node'
  } else if (isBlocked) {
    nodeColor = '#f59e0b' // amber
    pulseClass = 'constellation-node'
  } else if (isRunning) {
    nodeColor = '#10b981' // emerald
    pulseClass = 'constellation-node'
  } else {
    nodeColor = '#475569' // slate grey (idle)
  }

  return (
    <g 
      className="cursor-pointer select-none"
      onMouseEnter={() => onHover(node.id)}
      onMouseLeave={() => onHover(null)}
      onClick={onClick}
    >
      {/* Invisible larger hover trigger area */}
      <circle
        cx={x}
        y={y}
        r={isHub ? 32 : 24}
        fill="transparent"
      />

      {/* Pulsing glow ring */}
      {(isHub || isBlocked || isRunning || isHovered) && (
        <circle
          cx={x}
          y={y}
          r={isHub ? 24 : 16}
          fill="transparent"
          stroke={nodeColor}
          strokeWidth="1.5"
          opacity={isHovered ? 0.8 : 0.4}
          className={pulseClass}
        />
      )}

      {/* Core Node Circle */}
      <circle
        cx={x}
        y={y}
        r={isHub ? 14 : 9}
        fill="#07090f"
        stroke={nodeColor}
        strokeWidth={isHub || isHovered ? 2.5 : 1.5}
        className="transition-all duration-300"
      />

      {/* Center dot */}
      <circle
        cx={x}
        y={y}
        r={isHub ? 5 : 3}
        fill={nodeColor}
      />

      {/* Label Text */}
      <text
        x={x}
        y={y + (isHub ? 36 : 24)}
        textAnchor="middle"
        className="font-mono text-[9px] font-semibold tracking-wider transition-colors"
        fill={isHovered ? '#f8fafc' : isHub ? '#ffb830' : '#94a3b8'}
      >
        {isHub ? 'HERMES' : `@${label}`}
      </text>
    </g>
  )
}
