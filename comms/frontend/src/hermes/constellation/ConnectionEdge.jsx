import React from 'react'

export function ConnectionEdge({ fromNode, toNode, active }) {
  if (!fromNode || !toNode) return null

  return (
    <g>
      {/* Glow path */}
      <line
        x1={fromNode.x}
        y1={fromNode.y}
        x2={toNode.x}
        y2={toNode.y}
        stroke={active ? 'url(#edge-active-grad)' : 'rgba(100, 180, 255, 0.08)'}
        strokeWidth={active ? 2.5 : 1}
        className={active ? 'stream-line' : ''}
        style={{
          animationDuration: '10s',
        }}
      />
    </g>
  )
}
