import React, { useState, useMemo } from 'react'
import { AgentNode } from './AgentNode'
import { ConnectionEdge } from './ConnectionEdge'

const ROLE_DESCRIPTIONS = {
  spec: 'Spec & requirements writer. Writes specification documents based on user goals.',
  architect: 'Systems & files architect. Decides file structures, tech stack, and module boundaries.',
  planner: 'Task planner & executor. Breaks tasks down and coordinates coding sequences.',
  backend_dev: 'Writes backend code. Focuses on logic, database models, and API handlers.',
  test_dev: 'Writes automated unit tests. Validates code syntax and functionality.',
  config_agent: 'Manages dependencies & configs. Installs third-party libraries and settings.',
  docs_agent: 'Writes technical documents. Creates READMEs and API documentation.',
  reviewer: 'Reviews pull requests & specs. Validates architectural constraints.',
  integration_test: 'Performs end-to-end testing. Runs test suites and flags syntax errors.',
  cicd: 'Configures build pipelines. Prepares production deployment scripts.',
  hermes: 'Divine central coordinator. Human interface and orchestrator of the developer fleet.',
}

export function ConstellationView({ statuses = {}, busMessages = [], onClickNode }) {
  const [hoveredNodeId, setHoveredNodeId] = useState(null)

  // Pre-calculate node coordinates
  const Center = { x: 400, y: 260 }
  const Radius = 195
  const specialistIds = [
    'spec', 'architect', 'planner', 'backend_dev', 'test_dev',
    'config_agent', 'docs_agent', 'reviewer', 'integration_test', 'cicd'
  ]

  const nodes = useMemo(() => {
    return [
      { id: 'hermes', label: 'Hermes', x: Center.x, y: Center.y, isHub: true },
      ...specialistIds.map((id, i) => {
        // Offset starting angle so it points top-center
        const angle = (i * 2 * Math.PI) / specialistIds.length - Math.PI / 2
        return {
          id,
          label: id,
          x: Math.round(Center.x + Radius * Math.cos(angle)),
          y: Math.round(Center.y + Radius * Math.sin(angle)),
          isHub: false,
        }
      })
    ]
  }, [])

  // Create node lookup map for coordinate retrieval
  const nodeMap = useMemo(() => {
    const map = {}
    nodes.forEach(n => {
      map[n.id] = n
    })
    return map
  }, [nodes])

  // Extract active connections from the last 15 bus messages
  const activeConnections = useMemo(() => {
    const connections = new Set()
    busMessages.slice(0, 20).forEach(msg => {
      if (msg.sender && msg.receiver) {
        const key = [msg.sender, msg.receiver].sort().join('-')
        connections.add(key)
      }
    })
    return connections
  }, [busMessages])

  // Get description for the hovered node
  const hoveredNodeInfo = useMemo(() => {
    if (!hoveredNodeId) return null
    return {
      id: hoveredNodeId,
      desc: ROLE_DESCRIPTIONS[hoveredNodeId] || 'Specialist fleet agent',
      status: statuses[hoveredNodeId] || 'idle'
    }
  }, [hoveredNodeId, statuses])

  return (
    <div className="relative w-full h-full flex items-center justify-center p-6">
      {/* SVG Canvas */}
      <svg 
        viewBox="0 0 800 520" 
        className="w-full max-w-4xl aspect-[800/520] bg-[#090d16]/30 backdrop-blur border border-slate-800/80 rounded-2xl shadow-2xl relative z-10"
      >
        <defs>
          {/* Active cyan-gold stream edge gradient */}
          <linearGradient id="edge-active-grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#ffb830" />
            <stop offset="100%" stopColor="#00d4ff" />
          </linearGradient>
        </defs>

        {/* 1. Base Star topology connections (Specialists -> Hermes Hub) */}
        {specialistIds.map(id => {
          const node = nodeMap[id]
          const isMsgActive = activeConnections.has(`hermes-${id}`) || activeConnections.has(`${id}-hermes`)
          const status = statuses[id] || 'idle'
          const isAgentActive = status === 'active' || status === 'running' || status === 'blocked'
          
          return (
            <ConnectionEdge
              key={`hub-${id}`}
              fromNode={nodeMap['hermes']}
              toNode={node}
              active={isMsgActive || isAgentActive}
            />
          )
        })}

        {/* 2. Direct agent-to-agent communication lines based on active messages */}
        {Array.from(activeConnections).map(key => {
          const [idA, idB] = key.split('-')
          const nodeA = nodeMap[idA]
          const nodeB = nodeMap[idB]
          
          // Skip if nodes are invalid or it's already a hub link
          if (!nodeA || !nodeB || idA === 'hermes' || idB === 'hermes') return null
          
          return (
            <ConnectionEdge
              key={`peer-${key}`}
              fromNode={nodeA}
              toNode={nodeB}
              active={true}
            />
          )
        })}

        {/* 3. Render Node Circles & Labels */}
        {nodes.map(node => (
          <AgentNode
            key={node.id}
            node={node}
            status={statuses[node.id] || 'idle'}
            isHovered={hoveredNodeId === node.id}
            onHover={setHoveredNodeId}
            onClick={() => onClickNode(node.id)}
          />
        ))}
      </svg>

      {/* Floating details overlay on hover */}
      {hoveredNodeInfo && (
        <div 
          className="absolute bottom-12 left-1/2 -translate-x-1/2 bg-[#0c1220] border border-slate-800 rounded-xl p-4 w-80 shadow-2xl z-20 pointer-events-none animate-[message-fly_0.15s_ease-out]"
          style={{ textShadow: 'none' }}
        >
          <div className="flex items-center justify-between gap-2 mb-1.5">
            <span className="font-mono font-bold text-xs text-amber-400 capitalize">
              @{hoveredNodeInfo.id}
            </span>
            <span className={`text-[9px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded ${
              hoveredNodeInfo.status === 'blocked' || hoveredNodeInfo.status === 'pending'
                ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                : hoveredNodeInfo.status === 'active' || hoveredNodeInfo.status === 'running'
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                  : 'bg-slate-800 text-slate-400'
            }`}>
              {hoveredNodeInfo.status}
            </span>
          </div>
          <p className="text-slate-300 text-xs leading-normal">
            {hoveredNodeInfo.desc}
          </p>
        </div>
      )}
    </div>
  )
}
