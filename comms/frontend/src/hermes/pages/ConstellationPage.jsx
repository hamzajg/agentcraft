import React from 'react'
import { useNavigate } from 'react-router-dom'
import { ConstellationView } from '../constellation/ConstellationView'
import { useHermesData } from '../hooks/useHermesData'

export function ConstellationPage() {
  const { statuses, busMessages } = useHermesData()
  const navigate = useNavigate()

  const handleNodeClick = (agentId) => {
    // Navigate to workspace tab and tell it to select this specific agent
    navigate('/hermes/workspace', { state: { selectAgent: agentId } })
  }

  return (
    <div className="h-full flex flex-col bg-[#07090f] overflow-hidden select-none">
      {/* Title Header */}
      <div className="p-6 border-b border-slate-900 bg-[#090d16]/30 flex flex-col gap-1.5 flex-shrink-0">
        <h2 className="text-xl font-bold text-white font-serif tracking-wider" style={{ fontFamily: 'var(--font-hermes)' }}>
          Agent Constellation Map
        </h2>
        <p className="text-xs text-slate-400">
          Visualize real-time status transitions and communication flow over the AgentBus. Click any node to open its communication panel.
        </p>
      </div>

      {/* Constellation view wrapper */}
      <div className="flex-1 overflow-hidden relative flex items-center justify-center bg-radial-dots">
        <div 
          className="absolute inset-0 pointer-events-none opacity-25"
          style={{
            backgroundImage: 'radial-gradient(circle, rgba(255, 184, 48, 0.08) 1px, transparent 1px)',
            backgroundSize: '30px 30px',
          }}
        />
        <ConstellationView
          statuses={statuses}
          busMessages={busMessages}
          onClickNode={handleNodeClick}
        />
      </div>
    </div>
  )
}
